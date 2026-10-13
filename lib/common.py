#!/usr/bin/env python3
# (c) Martin Erzberger 2025-2026
# Shared by all scripts: project root, configuration, error type and the CA layout on disk.
#
# Importing lib changes to the project root, so all paths below are relative to it.

import functools
import os
import sys

LIB_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(LIB_DIR)
DEFAULTS_PATH = os.path.join(LIB_DIR, 'defaults.yaml')

os.chdir(PROJECT_ROOT)


class HomeCAError(Exception):
    """An expected failure, reported to the user as 'Error: <message>'."""

    def __init__(self, message, code=None):
        super().__init__(message)
        self.code = code


@functools.cache
def config():
    """The settings from lib/defaults.yaml, read once."""
    from .variables import Variables
    return Variables()


def run(main):
    """Run a script's main(), reporting a HomeCAError without a traceback."""
    try:
        main()
    except HomeCAError as e:
        sys.exit(f'Error: {e}')


def confirm(question):
    """Ask a yes/no question; anything but y aborts the script."""
    if input(f'{question} (y/N) ').strip().lower() != 'y':
        print('Aborted.')
        sys.exit(0)


def print_list(entries):
    print(*sorted(entries), sep='\n')


# CA layout
CA_DIRS = {
    'rootca': ['certs', 'crl', 'newcerts', 'private'],
    'issuingca': ['certs', 'crl', 'csr', 'newcerts', 'private'],
}
ROOT_CERT = 'rootca/certs/ca.cert.pem'
ROOT_KEY = 'rootca/private/ca.key.pem'
ISSUING_CERT = 'issuingca/certs/issuing.cert.pem'
ISSUING_KEY = 'issuingca/private/issuing.key.pem'
ISSUING_CSR = 'issuingca/csr/issuing.csr.pem'


def cert_path(name):
    return f'issuingca/certs/{name}.cert.pem'


def key_path(name):
    return f'issuingca/private/{name}.key.pem'


def csr_path(name):
    return f'issuingca/csr/{name}.csr.pem'


def init_database(ca, overwrite=False):
    """Create the OpenSSL database files of a CA directory; returns their names.
    Existing files are kept unless overwrite is set."""
    files = {'index.txt': '', 'serial': '1000\n'}
    if ca == 'issuingca':
        files['crlnumber'] = '1000\n'
    for name, content in files.items():
        path = os.path.join(ca, name)
        if overwrite or not os.path.exists(path):
            with open(path, 'w') as f:
                f.write(content)
    return list(files)


def add_cert_name_args(parser):
    """The -d/--domain and -H/--host options naming an issued certificate."""
    c = config()
    parser.add_argument('-d', '--domain', default=c.domain, choices=c.domains, metavar='DOMAIN',
                        help=f'Domain the cert was issued for (default: {c.domain}). '
                             f'Choices: {" | ".join(c.domains)}')
    parser.add_argument('-H', '--host', default='*', metavar='HOST',
                        help='Hostname or * for wildcard (default: *)')


def cert_name_from_args(args):
    return args.domain if args.host == '*' else f'{args.host}.{args.domain}'
