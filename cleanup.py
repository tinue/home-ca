#!/usr/bin/env python3
# (c) Martin Erzberger 2026
# Clean up CA directories.
# Default: remove issued certificates only, keeping the CA intact.
# --full: complete reset including CA keys and certificates.

import argparse
import glob
import os
import shutil
import sys


def setup():
    global variables
    from common import setup as common_setup
    variables = common_setup()
    os.chdir(variables.projectroot)


def _clean_dir(dirpath, keep=None):
    """Remove all files and subdirs in dirpath, optionally keeping named entries."""
    keep = set(keep or [])
    for path in sorted(glob.glob(os.path.join(dirpath, '*'))):
        if os.path.basename(path) not in keep:
            if os.path.isfile(path):
                os.remove(path)
                print(f'  removed {path}')
            elif os.path.isdir(path):
                shutil.rmtree(path)
                print(f'  removed {path}/')


def _reset_dir(dirpath):
    """Delete and recreate a directory."""
    shutil.rmtree(dirpath, ignore_errors=True)
    os.makedirs(dirpath)
    print(f'  reset   {dirpath}/')


def _init_database(ca_dir, has_crlnumber=False):
    """Remove existing database files and reinitialise them."""
    for f in glob.glob(os.path.join(ca_dir, 'index.txt*')):
        os.remove(f)
    for name in (['serial', 'crlnumber'] if has_crlnumber else ['serial']):
        path = os.path.join(ca_dir, name)
        if os.path.exists(path):
            os.remove(path)

    with open(os.path.join(ca_dir, 'index.txt'), 'w'):
        pass
    with open(os.path.join(ca_dir, 'serial'), 'w') as f:
        f.write('1000\n')
    if has_crlnumber:
        with open(os.path.join(ca_dir, 'crlnumber'), 'w') as f:
            f.write('1000\n')
    print(f'  reset   {ca_dir}/index.txt, serial' +
          (', crlnumber' if has_crlnumber else ''))


def cleanup_certs():
    """Remove issued certificates and keys, keeping the CA intact."""
    _clean_dir('issuingca/certs',    keep=['issuing.cert.pem'])
    _clean_dir('issuingca/csr',      keep=['issuing.csr.pem'])
    _clean_dir('issuingca/newcerts')
    _clean_dir('issuingca/private',  keep=['issuing.key.pem'])
    _init_database('issuingca', has_crlnumber=True)
    print()
    print('Issued certificates removed. Run python gencert.py to issue new ones.')


def cleanup_full():
    """Full reset: wipe everything and rebuild an empty CA structure."""
    for d in ['certs', 'crl', 'newcerts', 'private']:
        _reset_dir(f'rootca/{d}')
    os.chmod('rootca/private', 0o700)
    _init_database('rootca')

    for d in ['certs', 'crl', 'csr', 'newcerts', 'private']:
        _reset_dir(f'issuingca/{d}')
    os.chmod('issuingca/private', 0o700)
    _init_database('issuingca', has_crlnumber=True)

    print()
    print('Full reset complete. Run python initca.py to regenerate the CA.')


def main():
    parser = argparse.ArgumentParser(
        description='Clean up CA directories.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            'Without --full (default): removes all issued certificates and keys\n'
            '  while keeping the CA keys and certificates intact.\n\n'
            'With --full: complete reset — deletes everything including CA keys\n'
            '  and certificates. Run python initca.py afterwards to regenerate.'
        ),
    )
    parser.add_argument(
        '--full',
        action='store_true',
        help='Full reset: delete everything including CA keys and certificates',
    )
    args = parser.parse_args()

    setup()

    if args.full:
        print('WARNING: This will delete ALL certificates and keys, including the CA!')
        answer = input('Are you sure? (y/N) ')
        if answer.strip().lower() != 'y':
            print('Aborted.')
            sys.exit(0)
        print()
        cleanup_full()
    else:
        print('This will delete all issued certificates. CA keys and certificates are kept.')
        answer = input('Are you sure? (y/N) ')
        if answer.strip().lower() != 'y':
            print('Aborted.')
            sys.exit(0)
        print()
        cleanup_certs()


if __name__ == '__main__':
    main()
