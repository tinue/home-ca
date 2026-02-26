#!/usr/bin/env python3
# (c) Martin Erzberger 2026
# One-time project setup: configure defaults.yaml, initialise the CA
# directory structure, and generate the Root and Issuing CA certificates.

import getpass
import os
import shutil
import subprocess
import sys

import openssl


def setup():
    global variables
    from common import setup as common_setup
    variables = common_setup()
    os.chdir(variables.projectroot)
    os.environ["PROJECTROOT"] = variables.projectroot


def _configure():
    """Phase 1: ensure defaults.yaml exists and is configured.

    Must run before setup() so that setup() loads the user's values,
    not the example fallback. Computes the project root independently
    from the script location so it works from any working directory.
    """
    project_root = os.path.dirname(os.path.abspath(__file__))
    os.chdir(project_root)

    defaults_path = 'defaults.yaml'
    if os.path.exists(defaults_path):
        print(f'{defaults_path} already exists — skipping configuration step.')
        return

    print(f'{defaults_path} not found. Copying from defaults_example.yaml...')
    shutil.copy('defaults_example.yaml', defaults_path)

    editor = os.environ.get('VISUAL', os.environ.get('EDITOR', 'vi'))
    print(f'Opening {defaults_path} in {editor}...')
    print('Edit the file, save, and close the editor to continue.')
    subprocess.call([editor, defaults_path])


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
