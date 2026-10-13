#!/usr/bin/env -S uv run
# (c) Martin Erzberger 2024-2026
# Install the various certificates to their target servers / locations
#
# This file is highly specific to a specific home lab setup.
# Use it as an example for your own servers and services.

import argparse
import functools
import hashlib
import io
import os
import shlex
import socket
import ssl
import subprocess
import sys
import tarfile
import time

from lib import common, expiry, onepassword, openssl, synology, unifi
from lib.common import HomeCAError, ISSUING_CERT, ROOT_CERT, cert_path, config

KEYSTORE = ['-cacerts', '-storepass', 'changeit']   # the JDK truststore and its default password


def _run(*args):
    """Print and execute a command, raising CalledProcessError on failure."""
    print(' '.join(str(a) for a in args))
    subprocess.run(args, check=True)


def _section(name):
    """A deployment section of lib/defaults.yaml (synology, proxmox, unifi)."""
    section = getattr(config(), name)
    if not section:
        raise HomeCAError(f'No {name} section in lib/defaults.yaml.')
    return section


@functools.cache
def _key_pem(cert_name):
    """Decrypt the certificate's private key in memory, once per run."""
    return openssl.decrypted_key(cert_name, onepassword.read_password(cert_name))


def _ssh_with_files(host, command, files):
    """Run command on host with files ({name: (text, mode)}) as a tar stream on its stdin,
    over one connection; returns the command's stdout."""
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w') as tar:
        for name, (content, mode) in files.items():
            data = content.encode()
            info = tarfile.TarInfo(name)
            info.size, info.mode, info.mtime = len(data), mode, int(time.time())
            tar.addfile(info, io.BytesIO(data))
    print(f'ssh {host} {command}')
    return subprocess.run(['ssh', host, command], input=stream.getvalue(), stdout=subprocess.PIPE,
                          check=True).stdout.decode()


def install_docker_certs():
    """Copy wildcard certificate and key to the Docker host."""
    c = config()
    fqdn = f'{c.dockerhost}.{c.domain}'
    certs_dir = shlex.quote(f'{c.dockerdir}/certs')
    with open(cert_path(c.domain)) as f:
        cert_pem = f.read()

    print(f'Installing wildcard certificate to {fqdn}:{c.dockerdir}/certs ...')
    _ssh_with_files(fqdn, f'rm -rf {certs_dir} && mkdir -p {certs_dir} && tar -xpf - -C {certs_dir}',
                    {f'{c.domain}.cert': (cert_pem, 0o444), f'{c.domain}.key': (_key_pem(c.domain), 0o400)})
    print('Done.')


def install_java_ca():
    """Add the root CA certificate to the Java truststore."""
    java_home = os.environ.get('JAVA_HOME')
    if not java_home:
        print('JAVA_HOME is not set — skipping Java keystore update.')
        return

    keytool = os.path.join(java_home, 'bin', 'keytool')
    alias   = config().domainalias

    print(f'Updating Java keystore (alias: {alias}) ...')
    # Replace an existing entry; a fresh truststore (e.g. after a JDK upgrade) has none
    if subprocess.run([keytool, '-list', '-alias', alias, *KEYSTORE], capture_output=True).returncode == 0:
        _run(keytool, '-delete', '-alias', alias, *KEYSTORE)
    _run(keytool, '-importcert', '-alias', alias, '-trustcacerts', '-noprompt', *KEYSTORE, '-file', ROOT_CERT)
    print('Done.')


def _synology_login():
    """Log in to DSM with the account from 1Password; the OTP comes from the same item."""
    section = _section('synology')
    username, password, otp = onepassword.read_login(section['login'])
    dsm = synology.DSM(section['host'], section.get('port', 5001))
    dsm.login(username, password, lambda: otp or input('DSM one-time password: ').strip())
    return dsm


def list_synology_certs():
    """Print the certificates DSM knows, with the services that use them."""
    dsm = _synology_login()
    try:
        for cert in dsm.certificates():
            services = ', '.join(s.get('display_name', s.get('service', '?')) for s in cert.get('services', []))
            print(f'{cert.get("desc") or "(no description)"}{"  [default]" if cert.get("is_default") else ""}')
            print(f'  CN {cert["subject"].get("common_name")}, '
                  f'SANs {", ".join(cert["subject"].get("sub_alt_name", []))}')
            print(f'  valid until {cert.get("valid_till")}, used by: {services or "-"}')
    finally:
        dsm.logout()


def install_synology_certs():
    """Replace each configured certificate in DSM, matched by its common name."""
    section = _section('synology')
    print(f'Installing certificates to DSM on {section["host"]} ...')
    dsm = _synology_login()
    try:
        installed = dsm.certificates()
        for cert_name in section['certificates']:
            _install_synology_cert(dsm, installed, cert_name)
    finally:
        dsm.logout()


def _install_synology_cert(dsm, installed, cert_name):
    path = cert_path(cert_name)
    cn = openssl.subject_cn(path)

    matches = [c for c in installed if c['subject'].get('common_name') == cn]
    if len(matches) != 1:
        raise HomeCAError(f'Expected one DSM certificate with CN {cn}, found {len(matches)}.\n'
                          'Import it once in the DSM GUI, then re-run. List: uv run installcerts.py --list-synology')
    existing = matches[0]

    with open(ISSUING_CERT) as f:
        chain_pem = f.read()
    # DSM wants leaf and issuing CA separately
    result = dsm.import_certificate(existing['id'], existing.get('desc', ''), _key_pem(cert_name),
                                    openssl.leaf_pem(path), chain_pem, existing.get('is_default', False))
    print(f'  {cn}: replaced (was valid until {existing.get("valid_till")})'
          + (', DSM restarts its web server' if result.get('restart_httpd') else ''))


def install_proxmox_certs():
    """Install the configured certificate as pveproxy certificate on each Proxmox VE node."""
    section = _section('proxmox')
    cert_name = section['certificate']
    with open(cert_path(cert_name)) as f:
        files = {'cert.pem': (f.read(), 0o600), 'key.pem': (_key_pem(cert_name), 0o600)}
    # pvenode cert set is the supported way; it writes /etc/pve/nodes/<node>/pveproxy-ssl.{pem,key}.
    # The temporary copies go away even if a step fails; stdout only carries the node's FQDN.
    command = ('t=$(mktemp -d) && trap \'rm -rf "$t"\' EXIT && tar -xf - -C "$t" && '
               'pvenode cert set "$t/cert.pem" "$t/key.pem" --force 1 --restart 1 >&2 && hostname -f')

    for node in section['nodes']:
        print(f'Installing {cert_name} to Proxmox VE node {node} ...')
        fqdn = _ssh_with_files(node, command, files).strip()
        _verify_served(fqdn, 8006, cert_path(cert_name))


def _verify_served(host, port, path, timeout=15):
    """Check that host:port serves the cert at path, trusted via our Root CA (waits for restarts)."""
    leaf_der = ssl.PEM_cert_to_DER_cert(openssl.leaf_pem(path))
    context = ssl.create_default_context(cafile=ROOT_CERT)
    deadline = time.monotonic() + timeout
    while True:
        try:
            with socket.create_connection((host, port), timeout=5) as sock:
                with context.wrap_socket(sock, server_hostname=host) as tls:
                    served = tls.getpeercert(binary_form=True)
            break
        except (OSError, ssl.SSLError) as e:
            if time.monotonic() > deadline:
                raise HomeCAError(f'{host}:{port} not reachable with a trusted certificate: {e}')
            time.sleep(1)
    if served != leaf_der:
        raise HomeCAError(f'{host}:{port} serves a different certificate than {path}.')
    print(f'  {host}:{port} serves it, valid until {openssl.enddate(path)}')


def _hex(fingerprint):
    """A fingerprint as plain lowercase hex, without separators."""
    return ''.join(ch for ch in (fingerprint or '').lower() if ch in '0123456789abcdef')


def install_unifi_cert():
    """Upload the configured certificate to the UniFi OS console, activate it, drop the old one."""
    section = _section('unifi')
    host, cert_name, port = section['host'], section['certificate'], section.get('port', 443)
    path = cert_path(cert_name)
    with open(path) as f:
        chain_pem = f.read()   # leaf + issuing CA, as the console expects
    leaf_der = ssl.PEM_cert_to_DER_cert(openssl.leaf_pem(path))
    fingerprints = {hashlib.sha256(leaf_der).hexdigest(), hashlib.sha1(leaf_der).hexdigest()}
    cn = openssl.subject_cn(path)

    print(f'Installing {cert_name} to UniFi OS on {host} ...')
    console = unifi.UniFiOS(host, port)
    console.login(*onepassword.read_login(section['login']))
    try:
        installed = console.certificates()
        previous = [c for c in installed if c.get('active')]
        same = [c for c in installed if _hex(c.get('fingerprint')) in fingerprints]
        if same:
            new = same[0]
            print(f'  already uploaded as "{new["name"]}"')
        else:
            name = f'{cn} until {expiry.enddate(path):%Y-%m-%d}'
            new = console.upload_certificate(name, chain_pem, _key_pem(cert_name))
            print(f'  uploaded as "{name}"')
        if not new.get('active'):
            console.activate_certificate(new['id'])
            print('  activated')
        # Remove the certificate it replaces, if it was one of ours for the same name
        for old in previous:
            if old['id'] != new['id'] and old.get('source', 'uploaded') == 'uploaded' \
                    and cn in str(old.get('subject', '')):
                console.delete_certificate(old['id'])
                print(f'  deleted the previous certificate "{old["name"]}"')
    finally:
        console.logout()
    _verify_served(host, port, path)


TARGETS = {
    'docker': install_docker_certs,
    'java': install_java_ca,
    'synology': install_synology_certs,
    'proxmox': install_proxmox_certs,
    'unifi': install_unifi_cert,
}


def _run_target(target):
    """Run one target; return None on success, or the error message."""
    try:
        TARGETS[target]()
    except subprocess.CalledProcessError as e:
        return f'command failed with exit code {e.returncode}: {" ".join(str(a) for a in e.cmd)}'
    except HomeCAError as e:
        return str(e)
    except Exception as e:      # anything unexpected, e.g. a missing config key or network error
        return f'{type(e).__name__}: {e}'
    return None


def main():
    sys.stdout.reconfigure(line_buffering=True)   # keep our output in order with the commands'
    parser = argparse.ArgumentParser(
        description='Install certificates to their target systems.',
        epilog='With several targets (or all), an error in one target is reported '
               'and the remaining targets still run.')
    parser.add_argument('targets', nargs='*', metavar='TARGET',
                        help=f'what to install: {", ".join(TARGETS)}, or all')
    parser.add_argument('--list-synology', action='store_true',
                        help='only list the certificates installed in DSM')
    args = parser.parse_args()

    if args.list_synology:
        list_synology_certs()
        return

    if not args.targets:
        parser.error(f'name the targets to install: {", ".join(TARGETS)}, or all')
    targets = list(TARGETS) if 'all' in args.targets else list(dict.fromkeys(args.targets))
    unknown = set(targets) - set(TARGETS)
    if unknown:
        parser.error(f'unknown target(s): {", ".join(sorted(unknown))}')

    failed = {}
    for i, target in enumerate(targets):
        if i:
            print()
        error = _run_target(target)
        if error:
            failed[target] = error
            print(f'Error in {target}: {error}', file=sys.stderr)

    if len(targets) > 1:
        print()
        for target in targets:
            print(f'  {target:10} {"FAILED" if target in failed else "ok"}')
    if failed:
        sys.exit(1)


if __name__ == '__main__':
    common.run(main)
