#!/usr/bin/env python3
# (c) Martin Erzberger 2025-2026
# Dump expiry dates of issued certificates

import os

import openssl


def setup():
    global variables
    from common import setup as common_setup
    variables = common_setup()
    os.chdir(variables.projectroot)


def dump_expiries():
    expiries = {}
    for dirpath, _, filenames in os.walk('issuingca/certs/'):
        for filename in filenames:
            if filename.endswith('.pem'):
                cert_path = os.path.join(dirpath, filename)
                expiries[filename] = openssl.enddate(cert_path)

    for filename in sorted(expiries):
        print(f'{filename}: {expiries[filename]}')


# Program starts here
if __name__ == "__main__":
    setup()
    dump_expiries()
