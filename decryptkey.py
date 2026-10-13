#!/usr/bin/env -S uv run
# (c) Martin Erzberger 2019-2026
# Print a certificate's decrypted private key to stdout, for manual imports
# into systems that installcerts.py does not cover. No file is written; pipe it
# where it is needed, e.g. uv run decryptkey.py -H nas | pbcopy

import argparse
import os
import sys

from lib import common, onepassword, openssl


def main():
    parser = argparse.ArgumentParser(
        description='Print a certificate private key, decrypted, to stdout.',
        epilog='No file is written; pipe the output, e.g. uv run decryptkey.py -H nas | pbcopy',
    )
    common.add_cert_name_args(parser)
    cert_name = common.cert_name_from_args(parser.parse_args())

    if not os.path.exists(common.key_path(cert_name)):
        raise common.HomeCAError(f'{common.key_path(cert_name)} not found.')
    sys.stdout.write(openssl.decrypted_key(cert_name, onepassword.read_password(cert_name)))


if __name__ == '__main__':
    common.run(main)
