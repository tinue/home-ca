#!/usr/bin/env -S uv run
# (c) Martin Erzberger 2026
# One-time project setup: configure defaults.yaml, initialise the CA
# directory structure, and generate the Root and Issuing CA certificates.

import getpass
import os
import shutil
import subprocess
import sys

from lib import common, openssl
from lib.common import DEFAULTS_PATH, ISSUING_CERT, ISSUING_CSR, ISSUING_KEY, LIB_DIR, ROOT_CERT, ROOT_KEY


def _configure():
    """Phase 1: ensure defaults.yaml exists and is configured."""
    if os.path.exists(DEFAULTS_PATH):
        print('defaults.yaml already exists — skipping configuration step.')
        return

    print('defaults.yaml not found. Copying from defaults_example.yaml...')
    shutil.copy(os.path.join(LIB_DIR, 'defaults_example.yaml'), DEFAULTS_PATH)

    editor = os.environ.get('VISUAL', os.environ.get('EDITOR', 'vi'))
    print(f'Opening defaults.yaml in {editor}...')
    subprocess.call([editor, DEFAULTS_PATH])

    print()
    print('Edit defaults.yaml to match your environment, then re-run:')
    print('  uv run initca.py')
    sys.exit(0)


def _create_directory_structure():
    """Phase 2: create CA directories and initialise database files if absent."""
    for ca, subdirs in common.CA_DIRS.items():
        for d in subdirs:
            os.makedirs(os.path.join(ca, d), exist_ok=True)
        os.chmod(os.path.join(ca, 'private'), 0o700)
        common.init_database(ca)   # only files not already present


def _generate_ca():
    """Phase 3: generate Root CA and Issuing CA keys and certificates."""
    if os.path.exists(ROOT_KEY):
        print(f'{ROOT_KEY} already exists.')
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
    openssl.generate_key(ROOT_KEY, root_password, bits=4096)
    os.chmod(ROOT_KEY, 0o400)

    print('Generating Root CA self-signed certificate (valid 20 years)...')
    openssl.self_sign(ROOT_KEY, 'rootca/openssl.cnf', root_password, ROOT_CERT, days=7300)
    os.chmod(ROOT_CERT, 0o444)

    # Issuing CA
    print('Generating Issuing CA private key (RSA 4096)...')
    openssl.generate_key(ISSUING_KEY, issuing_password, bits=4096)
    os.chmod(ISSUING_KEY, 0o400)

    print('Generating Issuing CA certificate signing request...')
    openssl.ca_csr(ISSUING_KEY, 'issuingca/openssl.cnf', issuing_password, ISSUING_CSR)

    print('Signing Issuing CA certificate with Root CA (valid 10 years)...')
    openssl.sign_intermediate_ca(ISSUING_CSR, 'rootca/openssl.cnf', root_password, ISSUING_CERT, days=3650)

    # Inspect
    print()
    print('------------------------------------------------------')
    print('Root CA:')
    print(openssl.text(ROOT_CERT))
    print()
    print('------------------------------------------------------')
    print('Issuing CA:')
    print(openssl.text(ISSUING_CERT))

    # Verify chain
    print()
    print('------------------------------------------------------')
    print('Chain verification:')
    print(openssl.verify_chain(ROOT_CERT, ISSUING_CERT))

    print()
    print('CA certificates created successfully.')
    print('Recommended next step: uv run backup.py')


def _prompt_password(label):
    while True:
        pwd     = getpass.getpass(f'{label} password: ')
        confirm = getpass.getpass(f'{label} password (confirm): ')
        if pwd == confirm:
            return pwd
        print('Passwords do not match, try again.')


def main():
    _configure()   # must come first so defaults.yaml is in place
    _create_directory_structure()
    _generate_ca()


if __name__ == '__main__':
    common.run(main)
