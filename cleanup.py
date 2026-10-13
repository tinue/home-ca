#!/usr/bin/env -S uv run
# (c) Martin Erzberger 2026
# Clean up CA directories.
# Default: remove issued certificates only, keeping the CA intact.
# --full: complete reset including CA keys, certificates, and database files.
# --clobber: like --full, but also removes defaults.yaml.

import argparse
import glob
import os
import shutil

from lib import common
from lib.common import CA_DIRS, ISSUING_CERT, ISSUING_CSR, ISSUING_KEY


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


def _remove_database(ca_dir):
    """Remove database files without recreating them."""
    removed = []
    for f in glob.glob(os.path.join(ca_dir, 'index.txt*')):
        os.remove(f)
        removed.append(os.path.basename(f))
    for name in ['serial', 'crlnumber']:
        path = os.path.join(ca_dir, name)
        if os.path.exists(path):
            os.remove(path)
            removed.append(name)
    if removed:
        print(f'  removed {ca_dir}/{{{", ".join(removed)}}}')


def cleanup_certs():
    """Remove issued certificates and keys, keeping the CA intact."""
    _clean_dir('issuingca/certs',    keep=[os.path.basename(ISSUING_CERT)])
    _clean_dir('issuingca/csr',      keep=[os.path.basename(ISSUING_CSR)])
    _clean_dir('issuingca/newcerts')
    _clean_dir('issuingca/private',  keep=[os.path.basename(ISSUING_KEY)])
    _remove_database('issuingca')
    print(f'  reset   issuingca/{", ".join(common.init_database("issuingca", overwrite=True))}')
    print()
    print('Issued certificates removed. Run uv run gencert.py to issue new ones.')


def cleanup_full():
    """Full reset: wipe everything including CA keys, certificates, and database files."""
    for ca, subdirs in CA_DIRS.items():
        for d in subdirs:
            _reset_dir(f'{ca}/{d}')
        os.chmod(f'{ca}/private', 0o700)
        _remove_database(ca)

    print()
    print('Full reset complete. Run uv run initca.py to regenerate the CA.')


def cleanup_clobber():
    """Clobber: full reset plus delete defaults.yaml."""
    cleanup_full()
    path = 'lib/defaults.yaml'
    if os.path.exists(path):
        os.remove(path)
        print(f'  removed {path}')
    print()
    print('Clobber complete. Restore defaults.yaml before running uv run initca.py.')


def main():
    parser = argparse.ArgumentParser(
        description='Clean up CA directories.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            'Without --full (default): removes all issued certificates and keys\n'
            '  while keeping the CA keys and certificates intact.\n\n'
            'With --full: complete reset — deletes everything including CA keys,\n'
            '  certificates, and database files (serial, crlnumber, index.txt).\n'
            '  Run uv run initca.py afterwards to regenerate.\n\n'
            'With --clobber: everything --full does, plus deletes defaults.yaml.\n'
            '  Restore defaults.yaml before running uv run initca.py.'
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

    if args.clobber:
        warning, action = ('WARNING: This will delete ALL certificates, keys, database files, '
                           'AND defaults.yaml!', cleanup_clobber)
    elif args.full:
        warning, action = ('WARNING: This will delete ALL certificates, keys, and database files, '
                           'including the CA!', cleanup_full)
    else:
        warning, action = ('This will delete all issued certificates. CA keys and certificates '
                           'are kept.', cleanup_certs)
    print(warning)
    common.confirm('Are you sure?')
    print()
    action()


if __name__ == '__main__':
    main()
