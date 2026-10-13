#!/usr/bin/env -S uv run
# (c) Martin Erzberger 2019-2026
# Print a certificate's decrypted private key to stdout, for manual imports
# into systems that installcerts.py does not cover. No file is written; pipe it
# where it is needed, e.g. uv run decryptkey.py -H nas | pbcopy

import os
import sys

from lib import onepassword, openssl


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
        description='Print a certificate private key, decrypted, to stdout.',
        epilog=(
            'Use the same -d/-H arguments as when the certificate was issued.\n'
            'No file is written; pipe the output, e.g. uv run decryptkey.py -H nas | pbcopy'
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
        sys.exit(f'Error: {key_path} not found.')

    key_password = onepassword.read_password(cert_name)

    try:
        sys.stdout.write(openssl.decrypted_key(cert_name, key_password))
    except RuntimeError as e:
        sys.exit(f'Error: {e}')


if __name__ == '__main__':
    main()
