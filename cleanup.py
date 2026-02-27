#!/usr/bin/env python3
# (c) Martin Erzberger 2026
# Clean up CA directories.
# Default: remove issued certificates only, keeping the CA intact.
# --full: complete reset including CA keys, certificates, and database files.
# --clobber: like --full, but also removes defaults.yaml.

import argparse
import glob
import os
import shutil
import sys


def setup():
    from lib.variables import _PROJECT_ROOT
    os.chdir(_PROJECT_ROOT)


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
    _remove_database(ca_dir, has_crlnumber)
    with open(os.path.join(ca_dir, 'index.txt'), 'w'):
        pass
    with open(os.path.join(ca_dir, 'serial'), 'w') as f:
        f.write('1000\n')
    if has_crlnumber:
        with open(os.path.join(ca_dir, 'crlnumber'), 'w') as f:
            f.write('1000\n')
    print(f'  reset   {ca_dir}/index.txt, serial' +
          (', crlnumber' if has_crlnumber else ''))


def _remove_database(ca_dir, has_crlnumber=False):
    """Remove database files without recreating them."""
    removed = []
    for f in glob.glob(os.path.join(ca_dir, 'index.txt*')):
        os.remove(f)
        removed.append(os.path.basename(f))
    for name in (['serial', 'crlnumber'] if has_crlnumber else ['serial']):
        path = os.path.join(ca_dir, name)
        if os.path.exists(path):
            os.remove(path)
            removed.append(name)
    if removed:
        print(f'  removed {ca_dir}/{{{", ".join(removed)}}}')


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
    """Full reset: wipe everything including CA keys, certificates, and database files."""
    for d in ['certs', 'crl', 'newcerts', 'private']:
        _reset_dir(f'rootca/{d}')
    os.chmod('rootca/private', 0o700)
    _remove_database('rootca')

    for d in ['certs', 'crl', 'csr', 'newcerts', 'private']:
        _reset_dir(f'issuingca/{d}')
    os.chmod('issuingca/private', 0o700)
    _remove_database('issuingca', has_crlnumber=True)

    print()
    print('Full reset complete. Run python initca.py to regenerate the CA.')


def cleanup_clobber():
    """Clobber: full reset plus delete defaults.yaml."""
    cleanup_full()
    path = 'lib/defaults.yaml'
    if os.path.exists(path):
        os.remove(path)
        print(f'  removed {path}')
    print()
    print('Clobber complete. Restore defaults.yaml before running python initca.py.')


def main():
    parser = argparse.ArgumentParser(
        description='Clean up CA directories.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            'Without --full (default): removes all issued certificates and keys\n'
            '  while keeping the CA keys and certificates intact.\n\n'
            'With --full: complete reset — deletes everything including CA keys,\n'
            '  certificates, and database files (serial, crlnumber, index.txt).\n'
            '  Run python initca.py afterwards to regenerate.\n\n'
            'With --clobber: everything --full does, plus deletes defaults.yaml.\n'
            '  Restore defaults.yaml before running python initca.py.'
        ),
    )
    parser.add_argument(
        '--full',
        action='store_true',
        help='Full reset: delete everything including CA keys, certificates, and database files',
    )
    parser.add_argument(
        '--clobber',
        action='store_true',
        help='Like --full, but also deletes defaults.yaml',
    )
    args = parser.parse_args()

    setup()

    if args.clobber:
        print('WARNING: This will delete ALL certificates, keys, database files, AND defaults.yaml!')
        answer = input('Are you sure? (y/N) ')
        if answer.strip().lower() != 'y':
            print('Aborted.')
            sys.exit(0)
        print()
        cleanup_clobber()
    elif args.full:
        print('WARNING: This will delete ALL certificates, keys, and database files, including the CA!')
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
