#!/usr/bin/env python3
# (c) Martin Erzberger 2026
# One-time project setup: configure defaults.yaml, initialise the CA
# directory structure, and generate the Root and Issuing CA certificates.

import getpass
import os
import shutil
import subprocess
import sys

from lib import openssl
from lib.variables import _PROJECT_ROOT, _LIB_DIR


def setup():
    global variables
    from lib.common import setup as common_setup
    variables = common_setup()
    os.chdir(variables.projectroot)
    os.environ["PROJECTROOT"] = variables.projectroot


def _configure():
    """Phase 1: ensure defaults.yaml exists and is configured."""
    os.chdir(_PROJECT_ROOT)

    defaults_path = os.path.join(_LIB_DIR, 'defaults.yaml')
    example_path  = os.path.join(_LIB_DIR, 'defaults_example.yaml')

    if os.path.exists(defaults_path):
        print('defaults.yaml already exists — skipping configuration step.')
        return

    print('defaults.yaml not found. Copying from defaults_example.yaml...')
    shutil.copy(example_path, defaults_path)

    editor = os.environ.get('VISUAL', os.environ.get('EDITOR', 'vi'))
    print(f'Opening defaults.yaml in {editor}...')
    subprocess.call([editor, defaults_path])

    print()
    print('Edit defaults.yaml to match your environment, then re-run:')
    print('  python initca.py')
    sys.exit(0)


def _create_directory_structure():
    """Phase 2: create CA directories and initialise database files if absent."""
    dirs = {
        'rootca':   ['certs', 'crl', 'newcerts', 'private'],
        'issuingca': ['certs', 'crl', 'csr', 'newcerts', 'private'],
    }
    for ca, subdirs in dirs.items():
        for d in subdirs:
            os.makedirs(os.path.join(ca, d), exist_ok=True)
        os.chmod(os.path.join(ca, 'private'), 0o700)

        # Initialise database files only if not already present
        index  = os.path.join(ca, 'index.txt')
        serial = os.path.join(ca, 'serial')
        if not os.path.exists(index):
            with open(index, 'w'):
                pass
        if not os.path.exists(serial):
            with open(serial, 'w') as f:
                f.write('1000\n')

    crlnumber = 'issuingca/crlnumber'
    if not os.path.exists(crlnumber):
        with open(crlnumber, 'w') as f:
            f.write('1000\n')


def _generate_ca():
    """Phase 3: generate Root CA and Issuing CA keys and certificates."""
    if os.path.exists('rootca/private/ca.key.pem'):
        print('rootca/private/ca.key.pem already exists.')
        print('CA already initialised — skipping certificate generation.')
        return

    print()
    print('Both passwords are asked twice for confirmation.')
    print()
    root_password    = _prompt_password('Root CA private key')
    issuing_password = _prompt_password('Issuing CA private key')

    # Root CA
    print()
    print('Generating Root CA private key (RSA 4096)...')
    openssl.generate_key('rootca/private/ca.key.pem', root_password, bits=4096)
    os.chmod('rootca/private/ca.key.pem', 0o400)

    print('Generating Root CA self-signed certificate (valid 20 years)...')
    openssl.self_sign(
        'rootca/private/ca.key.pem',
        'rootca/openssl.cnf',
        root_password,
        'rootca/certs/ca.cert.pem',
        days=7300,
    )
    os.chmod('rootca/certs/ca.cert.pem', 0o444)

    # Issuing CA
    print('Generating Issuing CA private key (RSA 4096)...')
    openssl.generate_key('issuingca/private/issuing.key.pem', issuing_password, bits=4096)
    os.chmod('issuingca/private/issuing.key.pem', 0o400)

    print('Generating Issuing CA certificate signing request...')
    openssl.ca_csr(
        'issuingca/private/issuing.key.pem',
        'issuingca/openssl.cnf',
        issuing_password,
        'issuingca/csr/issuing.csr.pem',
    )

    print('Signing Issuing CA certificate with Root CA (valid 10 years)...')
    openssl.sign_intermediate_ca(
        'issuingca/csr/issuing.csr.pem',
        'rootca/openssl.cnf',
        root_password,
        'issuingca/certs/issuing.cert.pem',
        days=3650,
    )

    # Inspect
    print()
    print('------------------------------------------------------')
    print('Root CA:')
    print(openssl.validity('rootca/certs/ca.cert.pem'))
    print()
    print('------------------------------------------------------')
    print('Issuing CA:')
    print(openssl.validity('issuingca/certs/issuing.cert.pem'))

    # Verify chain
    print()
    print('------------------------------------------------------')
    print('Chain verification:')
    print(openssl.verify_chain('rootca/certs/ca.cert.pem', 'issuingca/certs/issuing.cert.pem'))

    print()
    print('CA certificates created successfully.')
    print('Recommended next step: python backup.py')


def _prompt_password(label):
    while True:
        pwd     = getpass.getpass(f'{label} password: ')
        confirm = getpass.getpass(f'{label} password (confirm): ')
        if pwd == confirm:
            return pwd
        print('Passwords do not match, try again.')


def main():
    _configure()   # must come before setup() so defaults.yaml is in place
    setup()
    _create_directory_structure()
    _generate_ca()


if __name__ == '__main__':
    main()
