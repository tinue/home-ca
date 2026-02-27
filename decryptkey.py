#!/usr/bin/env python3
# (c) Martin Erzberger 2019-2026
# Re-decrypt a certificate's private key for deployment.
# Use this if the unencrypted key was already deleted after a previous import.
# Delete the output file immediately after importing it to the target system.

import getpass
import os
import sys

from lib import openssl


def setup():
    global variables
    from lib.common import setup as common_setup
    variables = common_setup()
    os.chdir(variables.projectroot)
    os.environ["PROJECTROOT"] = variables.projectroot


def main():
    setup()

    import argparse

    parser = argparse.ArgumentParser(
        description='Re-decrypt a certificate private key for deployment.',
        epilog=(
            'Use the same -d/-H arguments as when the certificate was issued.\n'
            'Delete the output file immediately after importing it to the target system.'
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        '-d', '--domain',
        default=variables.domain,
        choices=variables.domains,
        metavar='DOMAIN',
        help=(
            f'Domain the cert was issued for (default: {variables.domain}). '
            f'Choices: {" | ".join(variables.domains)}'
        ),
    )
    parser.add_argument(
        '-H', '--host',
        default='*',
        metavar='HOST',
        help='Hostname or * for wildcard (default: *)',
    )

    args = parser.parse_args()

    domain = args.domain
    cert_name = domain if args.host == '*' else f'{args.host}.{domain}'
    key_path = f'issuingca/private/{cert_name}.key.pem'

    if not os.path.exists(key_path):
        print(f'Error: {key_path} not found.')
        sys.exit(1)

    key_password = getpass.getpass(f'Private key password for {cert_name}: ')

    try:
        openssl.decrypt_key(cert_name, key_password)
    except RuntimeError as e:
        print(f'Error: {e}')
        sys.exit(1)

    out_path = f'issuingca/private/{cert_name}.key.open.pem'
    print(f'Decrypted key written to:')
    print(f'  {out_path}')
    print()
    print('WARNING: Delete this file immediately after importing it to the target system.')


if __name__ == '__main__':
    main()
