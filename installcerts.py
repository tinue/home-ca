#!/usr/bin/env python3
# (c) Martin Erzberger 2024-2026
# Install the various certificates to their target servers / locations
#
# This file is highly specific to a specific home lab setup.
# Use it as an example for your own servers and services.

import os
import subprocess
import sys


def setup():
    global variables
    from common import setup as common_setup
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
        print('Run python gencert.py (or python decryptkey.py) first to produce the unencrypted key.')
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


def main():
    setup()
    try:
        install_docker_certs()
        print()
        install_java_ca()
    except subprocess.CalledProcessError as e:
        print(f'Error: command failed with exit code {e.returncode}')
        sys.exit(1)


if __name__ == '__main__':
    main()
