#!/usr/bin/env -S uv run
# (c) Martin Erzberger 2026
# Create or renew a TLS certificate: uv run gencert.py NAME
#
# NAME is a configured domain (or *.domain) for a wildcard cert, or host.domain.
# - Certificate exists and expires within the warning period (or has expired):
#   renewed with the same key, CN and SANs.
# - Certificate exists and is still valid: nothing is done (unless --force).
# - No certificate: a password is generated in 1Password, then key and cert are created.
# Passwords come from 1Password (one Password item per key, see lib/onepassword.py).
# Afterwards the unencrypted key is left for installation and a backup is made.

import argparse
import os
import sys

from lib import expiry, onepassword, openssl


def setup():
    global variables
    from lib.common import setup as common_setup
    variables = common_setup()
    os.chdir(variables.projectroot)
    os.environ["PROJECTROOT"] = variables.projectroot


def parse_name(name):
    """Return (cert_name, domain, host); host is None for a wildcard cert."""
    name = name.lower().rstrip('.')
    wildcard = name.startswith('*.')
    name = name.removeprefix('*.')
    if name in variables.domains:
        return name, name, None
    if not wildcard:
        for domain in sorted(variables.domains, key=len, reverse=True):
            if name.endswith(f'.{domain}'):
                host = name.removesuffix(f'.{domain}')
                return name, domain, host
    sys.exit(
        f'{name} is not a configured domain or a host in one.\n'
        f'Configured domains: {", ".join(variables.domains)}'
    )


def sans_from_args(cert_name, domain, host, args):
    """SAN list for a new certificate, built from the command line."""
    if host is None:
        if args.multi_domain:
            sys.exit('--multi-domain cannot be combined with a wildcard certificate.')
        sans = [f'DNS:*.{domain}', f'DNS:{domain}']
    else:
        sans = [f'DNS:{cert_name}']
        if args.multi_domain:
            sans += [f'DNS:{d}' for d in variables.domains if d != domain]
    return sans + [f'DNS:{san}' for san in args.extra_sans]


def sans_from_cert(cert_path):
    """SAN list of an existing certificate, in the form -addext accepts."""
    sans = []
    for entry in openssl.san_list(cert_path):
        kind, value = entry.split(':', 1)
        if kind == 'DNS':
            sans.append(f'DNS:{value}')
        elif kind == 'IP Address':
            sans.append(f'IP:{value}')
        else:
            sys.exit(f'Unsupported SAN in {cert_path}: {entry}')
    return sans


def key_password_for_new_cert(cert_name, key_path):
    """Password for a new certificate's key; creates the 1Password item if needed.

    Also resumes an earlier run that failed after the item or the key was created.
    """
    if onepassword.item_exists(cert_name):
        password = onepassword.read_password(cert_name)
        if os.path.exists(key_path) and not openssl.key_password_ok(key_path, password):
            sys.exit(f'{key_path} exists, but the 1Password item "{cert_name}" does not open it.')
        print(f'Using existing 1Password item "{cert_name}".')
        return password
    if os.path.exists(key_path):
        sys.exit(f'{key_path} exists without a certificate and without a 1Password item.\n'
                 'Its password is unknown; remove the key file to start over.')
    print(f'Creating 1Password item "{cert_name}" with a generated password ...')
    return onepassword.create_password_item(cert_name, f'Password for {key_path} (home-ca)')


def write_open_key(cert_name, key_password):
    """Write the unencrypted key for deployment, readable only by the owner."""
    path = f'issuingca/private/{cert_name}.key.open.pem'
    if os.path.exists(path):
        os.remove(path)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as f:
        f.write(openssl.decrypted_key(cert_name, key_password))
    return path


def main():
    setup()

    parser = argparse.ArgumentParser(
        description='Create or renew a TLS certificate.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            'Examples:\n'
            '  gencert.py home.example.com             wildcard *.home.example.com\n'
            '  gencert.py myserver.home.example.com    single host\n'
            '  gencert.py nas.home.example.com -s nas.local\n'
            '\n'
            'An existing certificate is renewed (same key, CN and SANs) when it has\n'
            f'expired or expires within {expiry.WARN_PERIOD.days} days.\n'
        ),
    )
    parser.add_argument('name', metavar='NAME',
                        help='domain or *.domain (wildcard), or host.domain')
    parser.add_argument('-s', '--extra-san', action='append', default=[], metavar='SAN',
                        dest='extra_sans', help='additional DNS SAN (repeatable); new certs or --force')
    parser.add_argument('-m', '--multi-domain', action='store_true',
                        help='add all other configured domains as SANs; new certs or --force')
    parser.add_argument('--force', action='store_true',
                        help='renew even if still valid; with -s/-m the SANs are replaced')
    args = parser.parse_args()

    cert_name, domain, host = parse_name(args.name)
    cert_path = f'issuingca/certs/{cert_name}.cert.pem'
    key_path = f'issuingca/private/{cert_name}.key.pem'
    new_path = f'{cert_path}.new'
    is_renewal = os.path.exists(cert_path)
    san_args_given = bool(args.extra_sans or args.multi_domain)

    # 1. What to issue
    if is_renewal:
        status, end = expiry.status(cert_path)
        print(f'Existing certificate {cert_path}: {status}, end date {end:%Y-%m-%d %H:%M} UTC')
        if status == expiry.VALID and not args.force:
            print('Still valid, nothing to do. Use --force to renew anyway.')
            return
        if san_args_given and not args.force:
            sys.exit('-s/-m change the SANs of an existing certificate; add --force to confirm.')
        if not os.path.exists(key_path):
            sys.exit(f'{key_path} not found; cannot renew with the existing key.')
        cn = openssl.subject_cn(cert_path)
        sans = sans_from_args(cert_name, domain, host, args) if san_args_given else sans_from_cert(cert_path)
    else:
        print(f'No certificate for {cert_name} yet, creating one.')
        cn = f'*.{domain}' if host is None else cert_name
        sans = sans_from_args(cert_name, domain, host, args)
    print(f'CN:   {cn}')
    print(f'SANs: {", ".join(sans)}')
    print()

    # 2. Passwords from 1Password, checked before anything is changed
    issuing_password = onepassword.read_password('issuing-ca')
    if not openssl.key_password_ok('issuingca/private/issuing.key.pem', issuing_password):
        sys.exit('The 1Password item "issuing-ca" does not open issuingca/private/issuing.key.pem.')
    if is_renewal:
        key_password = onepassword.read_password(cert_name)
        if not openssl.key_password_ok(key_path, key_password):
            sys.exit(f'The 1Password item "{cert_name}" does not open {key_path}.')
    else:
        key_password = key_password_for_new_cert(cert_name, key_path)

    # 3. CSR (new key only if none exists yet) and signature into a temporary file
    san_string = ','.join(sans)
    try:
        if os.path.exists(key_path):
            openssl.signing_request_renew(cert_name, cn, san_string, key_password)
        else:
            print('Generating private key (RSA 4096) ...')
            openssl.signing_request(cert_name, cn, san_string, key_password)
            os.chmod(key_path, 0o400)
        openssl.sign_certificate(cert_name, issuing_password, out_path=new_path)
        # Append issuing CA chain so clients only need to import the Root CA
        with open(new_path, 'a') as cert_file, open('issuingca/certs/issuing.cert.pem') as issuing_file:
            cert_file.write(issuing_file.read())
        print(openssl.verify_certificate(cert_name, new_path).strip())
    except RuntimeError as e:
        if os.path.exists(new_path):
            os.remove(new_path)
        sys.exit(f'Error: {e}\nNothing was replaced.')

    # 4. Swap in the new certificate; the previous one is kept as .backup
    if is_renewal:
        backup_path = f'{cert_path}.backup'
        if os.path.exists(backup_path):
            os.remove(backup_path)
        os.rename(cert_path, backup_path)
    os.rename(new_path, cert_path)
    os.chmod(cert_path, 0o444)

    # 5. Unencrypted key for installation
    open_key = write_open_key(cert_name, key_password)

    _, end = expiry.status(cert_path)
    print()
    print(f'{"Renewed" if is_renewal else "Created"} {cert_path}, valid until {end:%Y-%m-%d %H:%M} UTC')
    print(f'Unencrypted private key for installation: {open_key}')
    print('Delete it after installing the certificate.')

    # 6. Backup
    print()
    import backup
    backup.setup()
    backup.backup(variables.zipfilename, confirm=False)


if __name__ == '__main__':
    main()
