#!/usr/bin/env python3
# (c) Martin Erzberger 2025-2026
# Dump expiry dates of issued certificates

import locale
import os
from datetime import datetime, timezone

from lib import openssl

try:
    locale.setlocale(locale.LC_TIME, '')
except locale.Error:
    pass  # unsupported locale; strftime will use the C default


def setup():
    global variables
    from lib.common import setup as common_setup
    variables = common_setup()
    os.chdir(variables.projectroot)


_MONTHS = {
    'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5,  'Jun': 6,
    'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12,
}


def _format_enddate(raw):
    """Parse OpenSSL enddate string and return a locale-formatted date/time.

    OpenSSL always emits English month abbreviations regardless of locale,
    so we parse manually rather than using strptime's locale-dependent %b.
    """
    # OpenSSL format: "Feb 26 10:00:00 2027 GMT"
    mon, day, time_, year, _ = raw.split()
    h, m, s = time_.split(':')
    dt = datetime(int(year), _MONTHS[mon], int(day), int(h), int(m), int(s),
                  tzinfo=timezone.utc)
    return dt.strftime('%c %Z')


def dump_expiries():
    expiries = {}
    for dirpath, _, filenames in os.walk('issuingca/certs/'):
        for filename in filenames:
            if filename.endswith('.pem'):
                cert_path = os.path.join(dirpath, filename)
                expiries[filename] = _format_enddate(openssl.enddate(cert_path))

    for filename in sorted(expiries):
        print(f'{filename}: {expiries[filename]}')


# Program starts here
if __name__ == "__main__":
    setup()
    dump_expiries()
