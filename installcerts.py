#!/usr/bin/env -S uv run
# (c) Martin Erzberger 2024-2026
# Install the various certificates to their target servers / locations
#
# This file is highly specific to a specific home lab setup.
# Use it as an example for your own servers and services.

import argparse
import getpass
import os
import subprocess
import sys

from lib import onepassword, openssl, synology


def setup():
    global variables
    from lib.common import setup as common_setup
    variables = common_setup()
    os.chdir(variables.projectroot)


def _run(*args):
    """Print and execute a command, raising CalledProcessError on failure."""
    print(' '.join(str(a) for a in args))
    subprocess.run(args, check=True)


def install_docker_certs():
    """Copy wildcard certificate and key to the Docker host."""
    fqdn = f'{variables.dockerhost}.{variables.domain}'
    remote_dir = variables.dockerdir
    cert_src = f'issuingca/certs/{variables.domain}.cert.pem'
    key_src  = f'issuingca/private/{variables.domain}.key.open.pem'

    if not os.path.exists(key_src):
        print(f'Error: {key_src} not found.')
        print('Run uv run gencert.py (or uv run decryptkey.py) first to produce the unencrypted key.')
        sys.exit(1)

    print(f'Installing wildcard certificate to {fqdn}:{remote_dir}/certs ...')
    _run('ssh', fqdn, f'rm -rf {remote_dir}/certs')
    _run('ssh', fqdn, f'mkdir -p {remote_dir}/certs')
    _run('scp', cert_src, f'{fqdn}:{remote_dir}/certs/{variables.domain}.cert')
    _run('scp', key_src,  f'{fqdn}:{remote_dir}/certs/{variables.domain}.key')
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
    # Remove existing entry first; ignore failure if alias is not present
    subprocess.run(
        [keytool, '-delete', '-alias', alias, '-cacerts', '-storepass', 'changeit', '-v'],
    )
    _run(keytool, '-importcert', '-alias', alias,
         '-trustcacerts', '-noprompt',
         '-cacerts', '-storepass', 'changeit',
         '-file', ca_cert, '-v')
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
    key_path = f'issuingca/private/{cert_name}.key.open.pem'
    cn = openssl.subject_cn(cert_path)

    matches = [c for c in installed if c['subject'].get('common_name') == cn]
    if len(matches) != 1:
        sys.exit(f'Expected one DSM certificate with CN {cn}, found {len(matches)}.\n'
                 'Import it once in the DSM GUI, then re-run. List: uv run installcerts.py --list-synology')
    existing = matches[0]

    if os.path.exists(key_path):
        with open(key_path) as f:
            key_pem = f.read()
    else:
        key_pem = openssl.decrypted_key(cert_name, onepassword.read_password(cert_name))
    with open(cert_path) as f:
        # The cert file holds leaf + issuing CA; DSM wants them separately
        cert_pem = f.read().split('-----END CERTIFICATE-----')[0] + '-----END CERTIFICATE-----\n'
    with open('issuingca/certs/issuing.cert.pem') as f:
        chain_pem = f.read()

    result = dsm.import_certificate(existing['id'], existing.get('desc', ''), key_pem, cert_pem,
                                    chain_pem, existing.get('is_default', False))
    print(f'  {cn}: replaced (was valid until {existing.get("valid_till")})'
          + (', DSM restarts its web server' if result.get('restart_httpd') else ''))


TARGETS = {
    'docker': install_docker_certs,
    'java': install_java_ca,
    'synology': install_synology_certs,
}


def main():
    setup()
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
    except synology.DSMError as e:
        print(f'Error: {e.args[0]}')
        sys.exit(1)


if __name__ == '__main__':
    main()
