#!/usr/bin/env python3
# (c) Martin Erzberger 2025
# Dump expiry dates of issues certificates

# This part needs to be duplicated in each script
def setup():
  global variables
  from common import setup
  variables = setup()

def dump_expiries():
  import os
  import openssl

  for dirpath,_,filenames in os.walk('issuingca/certs/'):
    for f in filenames:
      abs_file = os.path.abspath(os.path.join(dirpath, f))
      if abs_file.endswith('.pem'):
        dump = openssl.validity(abs_file)
        clean_start = dump[dump.find('Not After :') + 12:]
        clean_end = clean_start[0:clean_start.find('\n')]
        print(f + ": " + clean_end)

# Program starts here
if __name__ == "__main__":
  setup()
  dump_expiries()

