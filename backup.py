#!/usr/bin/env -S uv run
# (c) Martin Erzberger 2025-2026
# Backup and restore all certificates

import argparse
import os
import tempfile
import zipfile

from lib import common, onepassword

# The latest backup is also attached to this 1Password item
BACKUP_ITEM = 'issuing-ca'

# Directories with keys and certificates
BACKUP_DIRS = ['rootca/certs', 'rootca/private', 'issuingca/certs', 'issuingca/private']

# CA database files: serial numbers and issued-certificate index (needed to keep signing)
DATABASE_FILES = [
    'rootca/serial', 'rootca/index.txt', 'rootca/index.txt.attr',
    'issuingca/serial', 'issuingca/index.txt', 'issuingca/index.txt.attr',
    'issuingca/crlnumber',
]


def backup(zip_path, confirm=True):
    if confirm:
        common.confirm(f'This will backup all certificates to {zip_path}. Are you sure?')

    files_to_backup = {path for d in BACKUP_DIRS for path in walk_directory(d)}
    # CA database files that exist (rootca has no index.txt.attr until it signs again)
    files_to_backup.update(f for f in DATABASE_FILES if os.path.exists(f))
    # Personal config file (gitignored, not recoverable from source control)
    if os.path.exists('lib/defaults.yaml'):
        files_to_backup.add('lib/defaults.yaml')
    else:
        print('Warning: lib/defaults.yaml not found — skipping.')

    # Keep the previous backup, in case this one turns out to be bad
    if os.path.exists(zip_path):
        os.replace(zip_path, f'{zip_path}.previous')
    with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_BZIP2) as myzip:
        for entry in sorted(files_to_backup):
            myzip.write(entry)
        archived = myzip.namelist()

    # Protect the zip file
    os.chmod(zip_path, 0o400)

    # Print zipfile content
    print(f'Backup written to {zip_path}:')
    common.print_list(archived)

    # Off-site copy: replaces the previous attachment of the same name
    onepassword.attach_file(BACKUP_ITEM, zip_path)
    print(f'Attached to 1Password item "{BACKUP_ITEM}" as {os.path.basename(zip_path)}.')


def restore(zip_path):
    if not os.path.exists(zip_path):
        raise common.HomeCAError(f'{zip_path} not found.')

    with zipfile.ZipFile(zip_path, 'r') as myzip:
        contents = myzip.namelist()

    print(f"Restoring from: {zip_path}")
    print("Contents:")
    common.print_list(contents)
    print()
    print("WARNING: Existing files will be overwritten.")
    common.confirm('Are you sure?')

    with zipfile.ZipFile(zip_path, 'r') as myzip:
        myzip.extractall('.')

    # Restore directory and file permissions
    for private_dir in ['rootca/private', 'issuingca/private']:
        if os.path.isdir(private_dir):
            os.chmod(private_dir, 0o700)
    for path in contents:
        if os.path.exists(path):
            if path.endswith('.key.pem'):
                os.chmod(path, 0o400)
            elif path.endswith('.cert.pem'):
                os.chmod(path, 0o444)

    print()
    print(f"Restored {len(contents)} file(s).")


def restore_from_1password(zip_name, vault=None):
    """Download the backup attached to the 1Password item and restore from it."""
    with tempfile.TemporaryDirectory() as tmp:
        zip_path = os.path.join(tmp, zip_name)
        onepassword.read_file(BACKUP_ITEM, zip_name, zip_path, vault)
        restore(zip_path)


def walk_directory(enum_dir):
    """Files below enum_dir, without unencrypted keys, unfinished certificates and dotfiles."""
    return {os.path.join(dir_, name)
            for dir_, _, files in os.walk(enum_dir) for name in files
            if not (name.startswith('.') or 'key.open.pem' in name or name.endswith('.new'))}


def main():
    parser = argparse.ArgumentParser(
        description='Backup and restore CA certificates.',
        epilog=(
            'Without --restore (default): creates a compressed ZIP of all keys,\n'
            '  certificates, CA database files and lib/defaults.yaml.\n\n'
            'With --restore: extracts a ZIP backup and restores file permissions.\n'
            'With --restore --from-1password: restores the backup attached to the\n'
            f'  1Password item "{BACKUP_ITEM}" (FILE names the attachment). Without\n'
            '  lib/defaults.yaml (e.g. on a new machine), also give FILE and --vault:\n'
            '  uv run backup.py --restore --from-1password --vault "Home CA" certbackup.zip'
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        'file',
        metavar='FILE',
        nargs='?',
        default=None,
        help='ZIP file to create or restore (default: configured backup filename)',
    )
    parser.add_argument(
        '--restore',
        action='store_true',
        help='Restore from a ZIP backup instead of creating one',
    )
    parser.add_argument(
        '--from-1password',
        action='store_true',
        help=f'With --restore: use the backup attached to the 1Password item "{BACKUP_ITEM}"',
    )
    parser.add_argument(
        '--vault',
        help='With --from-1password: vault of the item (default: onepassword.vault from lib/defaults.yaml)',
    )
    args = parser.parse_args()
    if args.from_1password and not args.restore:
        parser.error('--from-1password only works with --restore')
    if args.vault and not args.from_1password:
        parser.error('--vault only works with --from-1password')

    # Restore must work without lib/defaults.yaml (it may be what is restored), so the
    # configured filename is only used when no FILE is given.
    if args.file:
        zip_path = args.file
    elif os.path.exists(common.DEFAULTS_PATH):
        zip_path = common.config().zipfilename
    else:
        raise common.HomeCAError('no ZIP filename given and lib/defaults.yaml is missing.\n'
                                 'Specify the ZIP file explicitly: uv run backup.py --restore FILE')

    if not args.restore:
        backup(zip_path)
    elif args.from_1password:
        restore_from_1password(os.path.basename(zip_path), args.vault)
    else:
        restore(zip_path)


if __name__ == '__main__':
    common.run(main)
