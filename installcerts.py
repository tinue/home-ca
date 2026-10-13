#!/usr/bin/env -S uv run
# (c) Martin Erzberger 2024-2026
# Install the various certificates to their target servers / locations
#
# This file is highly specific to a specific home lab setup.
# Use it as an example for your own servers and services.

import argparse
import getpass
import hashlib
import os
import socket
import ssl
import subprocess
import sys
import time

from lib import expiry, onepassword, openssl, synology, unifi


def setup():
    global variables
    from lib.common import setup as common_setup
    variables = common_setup()
    os.chdir(variables.projectroot)


def _run(*args):
    """Print and execute a command, raising CalledProcessError on failure."""
    print(' '.join(str(a) for a in args))
    subprocess.run(args, check=True)


def _key_pem(cert_name):
    """Decrypt the certificate's private key in memory, with the password from 1Password."""
    return openssl.decrypted_key(cert_name, onepassword.read_password(cert_name))


def _leaf_pem(cert_path):
    """Return the first certificate of a cert file (leaf + issuing CA)."""
    with open(cert_path) as f:
        return f.read().split('-----END CERTIFICATE-----')[0] + '-----END CERTIFICATE-----\n'


def _ssh_write(host, path, content):
    """Write content to a file on host via ssh stdin, readable only by the owner."""
    print(f'ssh {host} cat > {path}')
    subprocess.run(['ssh', host, f'umask 077 && cat > {path}'], input=content, text=True, check=True)


def install_docker_certs():
    """Copy wildcard certificate and key to the Docker host."""
    fqdn = f'{variables.dockerhost}.{variables.domain}'
    remote_dir = variables.dockerdir
    cert_src = f'issuingca/certs/{variables.domain}.cert.pem'
    key_pem  = _key_pem(variables.domain)

    print(f'Installing wildcard certificate to {fqdn}:{remote_dir}/certs ...')
    _run('ssh', fqdn, f'rm -rf {remote_dir}/certs')
    _run('ssh', fqdn, f'mkdir -p {remote_dir}/certs')
    _run('scp', cert_src, f'{fqdn}:{remote_dir}/certs/{variables.domain}.cert')
    _ssh_write(fqdn, f'{remote_dir}/certs/{variables.domain}.key', key_pem)
    _run('ssh', fqdn, f'chmod 444 {remote_dir}/certs/{variables.domain}.cert')
    _run('ssh', fqdn, f'chmod 400 {remote_dir}/certs/{variables.domain}.key')
    print('Done.')


def install_java_ca():
    """Add the root CA certificate to the Java truststore."""
    java_home = os.environ.get('JAVA_HOME')
    if not java_home:
        print('JAVA_HOME is not set — skipping Java keystore update.')
        return

    keytool = os.path.join(java_home, 'bin', 'keytool')
    alias   = variables.domainalias
    ca_cert = 'rootca/certs/ca.cert.pem'

    print(f'Updating Java keystore (alias: {alias}) ...')
    # Replace an existing entry; a fresh truststore (e.g. after a JDK upgrade) has none
    listed = subprocess.run([keytool, '-list', '-alias', alias, '-cacerts', '-storepass', 'changeit'],
                            capture_output=True)
    if listed.returncode == 0:
        _run(keytool, '-delete', '-alias', alias, '-cacerts', '-storepass', 'changeit')
    _run(keytool, '-importcert', '-alias', alias,
         '-trustcacerts', '-noprompt',
         '-cacerts', '-storepass', 'changeit',
         '-file', ca_cert)
    print('Done.')


def _synology_login():
    """Log in to DSM with the account from 1Password; the OTP comes from the same item."""
    config = variables.synology
    if not config:
        sys.exit('No synology section in lib/defaults.yaml.')
    login = config['login']

    def otp():
        code = onepassword.read_otp(login)
        return code or input('DSM one-time password: ').strip()

    dsm = synology.DSM(config['host'], config.get('port', 5001))
    dsm.login(onepassword.read_field(f'{login}/username'),
              onepassword.read_field(f'{login}/password'), otp)
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
    config = variables.synology
    print(f'Installing certificates to DSM on {config["host"]} ...')
    dsm = _synology_login()
    try:
        installed = dsm.certificates()
        for cert_name in config['certificates']:
            _install_synology_cert(dsm, installed, cert_name)
    finally:
        dsm.logout()


def _install_synology_cert(dsm, installed, cert_name):
    cert_path = f'issuingca/certs/{cert_name}.cert.pem'
    cn = openssl.subject_cn(cert_path)

    matches = [c for c in installed if c['subject'].get('common_name') == cn]
    if len(matches) != 1:
        sys.exit(f'Expected one DSM certificate with CN {cn}, found {len(matches)}.\n'
                 'Import it once in the DSM GUI, then re-run. List: uv run installcerts.py --list-synology')
    existing = matches[0]

    key_pem = _key_pem(cert_name)
    cert_pem = _leaf_pem(cert_path)   # DSM wants leaf and issuing CA separately
    with open('issuingca/certs/issuing.cert.pem') as f:
        chain_pem = f.read()

    result = dsm.import_certificate(existing['id'], existing.get('desc', ''), key_pem, cert_pem,
                                    chain_pem, existing.get('is_default', False))
    print(f'  {cn}: replaced (was valid until {existing.get("valid_till")})'
          + (', DSM restarts its web server' if result.get('restart_httpd') else ''))


def install_proxmox_certs():
    """Install the configured certificate as pveproxy certificate on each Proxmox VE node."""
    config = variables.proxmox
    if not config:
        sys.exit('No proxmox section in lib/defaults.yaml.')
    cert_name = config['certificate']
    cert_path = f'issuingca/certs/{cert_name}.cert.pem'
    key_pem = _key_pem(cert_name)

    for node in config['nodes']:
        print(f'Installing {cert_name} to Proxmox VE node {node} ...')
        fqdn, tmp = subprocess.run(['ssh', node, 'hostname -f && mktemp -d'], capture_output=True,
                                   text=True, check=True).stdout.split()
        try:
            _ssh_write(node, f'{tmp}/key.pem', key_pem)
            _run('scp', '-q', cert_path, f'{node}:{tmp}/cert.pem')
            # The supported way; it writes /etc/pve/nodes/<node>/pveproxy-ssl.{pem,key}
            _run('ssh', node, f'pvenode cert set {tmp}/cert.pem {tmp}/key.pem --force 1 --restart 1')
        finally:
            subprocess.run(['ssh', node, f'rm -rf {tmp}'], check=True)
        _verify_served(fqdn, 8006, cert_path)


def _verify_served(host, port, cert_path, timeout=15):
    """Check that host:port serves cert_path, trusted via our Root CA (waits for restarts)."""
    leaf_der = ssl.PEM_cert_to_DER_cert(_leaf_pem(cert_path))
    context = ssl.create_default_context(cafile='rootca/certs/ca.cert.pem')
    deadline = time.monotonic() + timeout
    while True:
        try:
            with socket.create_connection((host, port), timeout=5) as sock:
                with context.wrap_socket(sock, server_hostname=host) as tls:
                    served = tls.getpeercert(binary_form=True)
            break
        except (OSError, ssl.SSLError) as e:
            if time.monotonic() > deadline:
                sys.exit(f'  {host}:{port} not reachable with a trusted certificate: {e}')
            time.sleep(1)
    if served != leaf_der:
        sys.exit(f'  {host}:{port} serves a different certificate than {cert_path}.')
    print(f'  {host}:{port} serves it, valid until {openssl.enddate(cert_path)}')


def install_unifi_cert():
    """Upload the configured certificate to the UniFi OS console, activate it, drop the old one."""
    config = variables.unifi
    if not config:
        sys.exit('No unifi section in lib/defaults.yaml.')
    host, cert_name, login = config['host'], config['certificate'], config['login']
    cert_path = f'issuingca/certs/{cert_name}.cert.pem'
    with open(cert_path) as f:
        chain_pem = f.read()   # leaf + issuing CA, as the console expects
    leaf_der = ssl.PEM_cert_to_DER_cert(_leaf_pem(cert_path))
    fingerprints = {hashlib.sha256(leaf_der).hexdigest(), hashlib.sha1(leaf_der).hexdigest()}
    cn = openssl.subject_cn(cert_path)

    print(f'Installing {cert_name} to UniFi OS on {host} ...')
    console = unifi.UniFiOS(host, config.get('port', 443))
    console.login(onepassword.read_field(f'{login}/username'),
                  onepassword.read_field(f'{login}/password'), onepassword.read_otp(login))
    try:
        installed = console.certificates()
        previous = [c for c in installed if c.get('active')]
        same = [c for c in installed
                if ''.join(ch for ch in (c.get('fingerprint') or '').lower() if ch in '0123456789abcdef')
                in fingerprints]
        if same:
            new = same[0]
            print(f'  already uploaded as "{new["name"]}"')
        else:
            name = f'{cn} until {expiry.status(cert_path)[1]:%Y-%m-%d}'
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
    _verify_served(host, config.get('port', 443), cert_path)


TARGETS = {
    'docker': install_docker_certs,
    'java': install_java_ca,
    'synology': install_synology_certs,
    'proxmox': install_proxmox_certs,
    'unifi': install_unifi_cert,
}


def main():
    setup()
    sys.stdout.reconfigure(line_buffering=True)   # keep our output in order with the commands'
    parser = argparse.ArgumentParser(description='Install certificates to their target systems.')
    parser.add_argument('targets', nargs='*', metavar='TARGET',
                        help=f'what to install: {", ".join(TARGETS)} (default: all)')
    parser.add_argument('--list-synology', action='store_true',
                        help='only list the certificates installed in DSM')
    args = parser.parse_args()
    unknown = set(args.targets) - set(TARGETS)
    if unknown:
        parser.error(f'unknown target(s): {", ".join(sorted(unknown))}')

    try:
        if args.list_synology:
            list_synology_certs()
            return
        for i, target in enumerate(args.targets or TARGETS):
            if i:
                print()
            TARGETS[target]()
    except subprocess.CalledProcessError as e:
        print(f'Error: command failed with exit code {e.returncode}')
        sys.exit(1)
    except (synology.DSMError, unifi.UniFiError) as e:
        print(f'Error: {e.args[0]}')
        sys.exit(1)


if __name__ == '__main__':
    main()
