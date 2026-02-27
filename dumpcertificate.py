#!/usr/bin/env python3
# (c) Martin Erzberger 2026
# Dump key fields of an issued certificate: CN, SANs, expiry, key usage, EKU.

import os
import sys

from lib import openssl


def setup():
    global variables
    from lib.common import setup as common_setup
    variables = common_setup()
    os.chdir(variables.projectroot)
    os.environ["PROJECTROOT"] = variables.projectroot


def dump_certificate(cert_path):
    label_w = 22
    def row(label, value):
        print(f'  {label + ":":<{label_w}} {value}')

    print(f'Certificate: {cert_path}')

    row('CN', openssl.subject_cn(cert_path))

    sans = openssl.san_list(cert_path)
    if sans:
        row('SANs', sans[0])
        for entry in sans[1:]:
            row('', entry)
    else:
        row('SANs', '(none)')

    row('Expiry', openssl.enddate(cert_path))

    ku = openssl.key_usage(cert_path)
    row('Key Usage', ku if ku is not None else '(not set)')

    eku = openssl.extended_key_usage(cert_path)
    row('Ext. Key Usage', eku if eku is not None else '(not set)')


def main():
    setup()

    import argparse

    parser = argparse.ArgumentParser(
        description='Dump key fields of an issued certificate.',
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
    cert_path = f'issuingca/certs/{cert_name}.cert.pem'

    if not os.path.exists(cert_path):
        print(f'Error: {cert_path} not found.')
        sys.exit(1)

    try:
        dump_certificate(cert_path)
    except RuntimeError as e:
        print(f'Error: {e}')
        sys.exit(1)


if __name__ == '__main__':
    main()
