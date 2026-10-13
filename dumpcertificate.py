#!/usr/bin/env -S uv run
# (c) Martin Erzberger 2026
# Dump key fields of an issued certificate: CN, SANs, expiry, key usage, EKU.

import argparse
import os

from lib import common, openssl


def dump_certificate(cert_path):
    label_w = 22
    def row(label, value):
        print(f'  {label + ":":<{label_w}} {value}')

    print(f'Certificate: {cert_path}')

    row('CN', openssl.subject_cn(cert_path))

    sans = openssl.san_list(cert_path)
    if sans:
        row('SANs', sans[0])
        for entry in sans[1:]:
            row('', entry)
    else:
        row('SANs', '(none)')

    row('Expiry', openssl.enddate(cert_path))

    ku = openssl.key_usage(cert_path)
    row('Key Usage', ku if ku is not None else '(not set)')

    eku = openssl.extended_key_usage(cert_path)
    row('Ext. Key Usage', eku if eku is not None else '(not set)')


def main():
    parser = argparse.ArgumentParser(description='Dump key fields of an issued certificate.')
    common.add_cert_name_args(parser)
    cert_path = common.cert_path(common.cert_name_from_args(parser.parse_args()))

    if not os.path.exists(cert_path):
        raise common.HomeCAError(f'{cert_path} not found.')
    dump_certificate(cert_path)


if __name__ == '__main__':
    common.run(main)
