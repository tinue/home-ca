#!/usr/bin/env python3
# (c) Martin Erzberger 2026
# Unified certificate generation script
# Supports wildcard, single-host, and multi-domain (everest) modes.
# Automatically detects existing certs and performs renewal (reusing the existing key).

import getpass
import os
import shutil
import sys

import openssl


def setup():
    global variables
    from common import setup as common_setup
    variables = common_setup()
    os.chdir(variables.projectroot)
    os.environ["PROJECTROOT"] = variables.projectroot


def main():
    setup()

    import argparse

    parser = argparse.ArgumentParser(
        description='Generate or renew TLS certificates',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            'Cert modes:\n'
            '  Wildcard    --host * (default)  CN=*.domain, SAN=*.domain + domain\n'
            '  Single host --host NAME          CN=NAME.domain, SAN=NAME.domain\n'
            '  Multi-domain --host NAME -m      adds other configured domains as SANs\n'
        ),
    )
    parser.add_argument(
        '-d', '--domain',
        default=variables.domain,
        choices=variables.domains,
        metavar='DOMAIN',
        help=(
            f'Domain to issue cert for (default: {variables.domain}). '
            f'Choices: {" | ".join(variables.domains)}'
        ),
    )
    parser.add_argument(
        '-H', '--host',
        default='*',
        metavar='HOST',
        help='Hostname or * for wildcard (default: *)',
    )
    parser.add_argument(
        '-s', '--extra-san',
        action='append',
        default=[],
        metavar='SAN',
        dest='extra_sans',
        help='Additional SAN entry (repeatable)',
    )
    parser.add_argument(
        '-m', '--multi-domain',
        action='store_true',
        help='Add other configured domains as SANs (everest pattern)',
    )

    args = parser.parse_args()

    # Validate conflicting options — no prompts, fail fast
    if args.host == '*' and args.multi_domain:
        parser.error('--multi-domain cannot be combined with wildcard (--host *)')

    domain = args.domain

    # Determine cert_name, CN, and SAN list
    if args.host == '*':
        cert_name = domain
        cn = f'*.{domain}'
        sans = [f'DNS.1:*.{domain}', f'DNS.2:{domain}']
    else:
        cert_name = f'{args.host}.{domain}'
        cn = cert_name
        sans = [f'DNS.1:{cert_name}']
        if args.multi_domain:
            idx = 2
            for other_domain in variables.domains:
                if other_domain != domain:
                    sans.append(f'DNS.{idx}:{other_domain}')
                    idx += 1

    # Append any extra SANs
    next_idx = len(sans) + 1
    for extra in args.extra_sans:
        sans.append(f'DNS.{next_idx}:{extra}')
        next_idx += 1

    san_string = ','.join(sans)

    # Detect create vs. renew
    cert_path = f'issuingca/certs/{cert_name}.cert.pem'
    is_renewal = os.path.exists(cert_path)

    if is_renewal:
        print(f'Existing certificate found: {cert_path}')
        print('Current validity:')
        print(openssl.cert_validity_text(cert_path))
        print()
        backup_path = f'{cert_path}.backup'
        shutil.move(cert_path, backup_path)
        print(f'Backed up to: {backup_path}')
        print()

    # Prompt for passwords
    issuing_password = getpass.getpass('Issuing CA private key password: ')
    key_label = 'Existing' if is_renewal else 'New'
    key_password = getpass.getpass(f'{key_label} certificate private key password: ')

    # Generate CSR
    if is_renewal:
        openssl.signing_request_renew(cert_name, cn, san_string, key_password)
    else:
        openssl.signing_request_new(cert_name, cn, san_string, key_password)

    # Sign the certificate
    openssl.sign_certificate(cert_name, issuing_password)

    # Append issuing CA chain so clients only need to import the Root CA
    with open(cert_path, 'a') as cert_file:
        with open('issuingca/certs/issuing.cert.pem', 'r') as issuing_file:
            cert_file.write(issuing_file.read())

    # Certificates are public — readable by all
    os.chmod(cert_path, 0o444)

    # Verify chain
    print(openssl.verify_certificate(cert_name))

    # Produce unencrypted deployment key
    openssl.decrypt_key(cert_name, key_password)
    print()
    print('WARNING: Unencrypted private key written to:')
    print(f'  issuingca/private/{cert_name}.key.open.pem')
    print('Delete this file immediately after deploying it to the target system!')

    if is_renewal:
        print()
        print('Renewal complete. Delete the backup when no longer needed:')
        print(f'  rm -f {cert_path}.backup')


if __name__ == '__main__':
    main()
