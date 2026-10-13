#!/usr/bin/env -S uv run
# (c) Martin Erzberger 2025-2026
# Backup and restore all certificates

import argparse
import os
import sys
import tempfile
import zipfile

from lib import common, onepassword

# The latest backup is also attached to this 1Password item
BACKUP_ITEM = 'issuing-ca'


def setup():
    global variables
    from lib.common import setup as common_setup
    variables = common_setup()
    os.chdir(variables.projectroot)


# CA database files: serial numbers and issued-certificate index (needed to keep signing)
DATABASE_FILES = [
    'rootca/serial', 'rootca/index.txt', 'rootca/index.txt.attr',
    'issuingca/serial', 'issuingca/index.txt', 'issuingca/index.txt.attr',
    'issuingca/crlnumber',
]


def backup(zip_path, confirm=True):
    if confirm and input(f"This will backup all certificates to {zip_path}. Are you sure (y/n)? ") != "y":
        print("Aborting")
        sys.exit(0)

    # Make the list of files to be archived
    files_to_backup = set()
    # Add Root CA
    files_to_backup.update(walk_directory("rootca/certs/", variables.projectroot))
    files_to_backup.update(walk_directory("rootca/private/", variables.projectroot))
    # Add Issuing CA and certificates
    files_to_backup.update(walk_directory("issuingca/certs/", variables.projectroot))
    files_to_backup.update(walk_directory("issuingca/private/", variables.projectroot))
    # Add CA database files that exist (rootca has no index.txt.attr until it signs again)
    files_to_backup.update(f for f in DATABASE_FILES if os.path.exists(f))
    # Add personal config file (gitignored, not recoverable from source control)
    files_to_backup.add("lib/defaults.yaml")

    # Keep the previous backup, in case this one turns out to be bad
    if os.path.exists(zip_path):
        previous = f'{zip_path}.previous'
        if os.path.exists(previous):
            os.remove(previous)
        os.rename(zip_path, previous)
    with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_BZIP2) as myzip:
        for entry in sorted(files_to_backup):
            if os.path.exists(entry):
                myzip.write(entry)
            else:
                print(f'Warning: {entry} not found — skipping.')
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
        print(f"Error: {zip_path} not found.")
        sys.exit(1)

    with zipfile.ZipFile(zip_path, 'r') as myzip:
        contents = myzip.namelist()

    print(f"Restoring from: {zip_path}")
    print("Contents:")
    common.print_list(contents)
    print()
    print("WARNING: Existing files will be overwritten.")
    if input("Are you sure (y/n)? ") != "y":
        print("Aborting")
        sys.exit(0)

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


def walk_directory(enum_dir, project_root):
    file_set = set()
    for dir_, _, files in os.walk(enum_dir):
        for file_name in files:
            # Skip unencrypted deployment keys, unfinished certificates and dotfiles
            if not (file_name.startswith('.') or 'key.open.pem' in file_name
                    or file_name.endswith('.new')):
                rel_dir = os.path.relpath(dir_, project_root)
                rel_file = os.path.join(rel_dir, file_name)
                file_set.add(rel_file)
    return file_set


def main():
    parser = argparse.ArgumentParser(
        description='Backup and restore CA certificates.',
        epilog=(
            'Without --restore (default): creates a compressed ZIP of all keys\n'
            '  and certificates, excluding unencrypted deployment keys.\n\n'
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

    if args.restore:
        # Restore must work even when defaults.yaml is absent (it may be what
        # we are restoring). Only _PROJECT_ROOT is needed; it is computed from
        # __file__ and requires no config file.
        from lib.variables import _PROJECT_ROOT, _LIB_DIR
        os.chdir(_PROJECT_ROOT)
        if args.file:
            zip_path = args.file
        elif os.path.exists(os.path.join(_LIB_DIR, 'defaults.yaml')):
            # defaults.yaml is present — read the configured backup filename.
            setup()
            zip_path = variables.zipfilename
        else:
            print('Error: no ZIP filename given and lib/defaults.yaml is missing.')
            print('Specify the ZIP file explicitly: uv run backup.py --restore FILE')
            sys.exit(1)
        if args.from_1password:
            restore_from_1password(os.path.basename(zip_path), args.vault)
        else:
            restore(zip_path)
    else:
        setup()
        zip_path = args.file or variables.zipfilename
        backup(zip_path)


if __name__ == '__main__':
    main()
