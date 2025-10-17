#!/usr/bin/env python3
# (c) Martin Erzberger 2025
# Backup all certificates

# This part needs to be duplicated in each script
def setup():
  global variables
  from common import setup
  variables = setup()

def backup():
  import os
  import zipfile
  import common

  # Ask for confirmation
  if input("This will backup all certificates into a ZIP file. Are you sure (y/n)? ") != "y":
    print("Aborting")
    exit()

  # Make the list of files to be archived
  files_to_backup = set()
  # Add Root CA
  files_to_backup.update(walk_directory("rootca/certs/"))
  files_to_backup.update(walk_directory("rootca/private/"))
  # Add Issuing CA and certificates
  files_to_backup.update(walk_directory("issuingca/certs/"))
  files_to_backup.update(walk_directory("issuingca/private/"))
  files_to_backup.add("variables.py")

  # Make the zip file
  if os.path.exists(variables.zipfilename):
    os.remove(variables.zipfilename)
  with zipfile.ZipFile(variables.zipfilename, 'w', compression=zipfile.ZIP_BZIP2) as myzip:
    sorted_list = sorted(files_to_backup)
    for entry in sorted_list:
      myzip.write(entry)

  # Protect the zip file
  os.chmod(variables.zipfilename, 0o400)

  # Print zipfile content
  common.print_list(zipfile.ZipFile(variables.zipfilename).namelist())

# Helper to enumerate a directory
def walk_directory(enum_dir):
  import os
  file_set = set()
  for dir_, _, files in os.walk(enum_dir):
    for file_name in files:
        if not (file_name.startswith('.') or 'key.open.pem' in file_name): # Do not add unencrypted keys or dotfiles
          rel_dir = os.path.relpath(dir_, variables.projectroot)
          rel_file = os.path.join(rel_dir, file_name)
          file_set.add(rel_file)
  return file_set

# Program starts here
if __name__ == "__main__":
  setup()
  backup()