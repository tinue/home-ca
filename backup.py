#!/usr/bin/env python3
# (c) Martin Erzberger 2025-2026
# Backup and restore all certificates

import argparse
import os
import sys
import zipfile

from lib import common


def setup():
    global variables
    from lib.common import setup as common_setup
    variables = common_setup()
    os.chdir(variables.projectroot)


def backup(zip_path):
    if input(f"This will backup all certificates to {zip_path}. Are you sure (y/n)? ") != "y":
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
    # Add personal config file (gitignored, not recoverable from source control)
    files_to_backup.add("defaults.yaml")

    # Make the zip file
    if os.path.exists(zip_path):
        os.remove(zip_path)
    with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_BZIP2) as myzip:
        for entry in sorted(files_to_backup):
            myzip.write(entry)
        archived = myzip.namelist()

    # Protect the zip file
    os.chmod(zip_path, 0o400)

    # Print zipfile content
    common.print_list(archived)


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


def walk_directory(enum_dir, project_root):
    file_set = set()
    for dir_, _, files in os.walk(enum_dir):
        for file_name in files:
            # Skip unencrypted deployment keys and dotfiles
            if not (file_name.startswith('.') or 'key.open.pem' in file_name):
                rel_dir = os.path.relpath(dir_, project_root)
                rel_file = os.path.join(rel_dir, file_name)
                file_set.add(rel_file)
    return file_set


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Backup and restore CA certificates.',
        epilog=(
            'Without --restore (default): creates a compressed ZIP of all keys\n'
            '  and certificates, excluding unencrypted deployment keys.\n\n'
            'With --restore: extracts a ZIP backup and restores file permissions.'
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
    args = parser.parse_args()

    setup()

    zip_path = args.file or variables.zipfilename
    if args.restore:
        restore(zip_path)
    else:
        backup(zip_path)
