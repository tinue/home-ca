#!/usr/bin/env -S uv run
# (c) Martin Erzberger 2025-2026
# Dump expiry dates of issued certificates

import locale
import os
import sys
from datetime import datetime, timezone

from lib import common, expiry

try:
    locale.setlocale(locale.LC_TIME, '')
except locale.Error:
    pass  # unsupported locale; strftime will use the C default


_RED = '\033[31m'
_YELLOW = '\033[33m'
_RESET = '\033[0m'

_COLORS = {expiry.EXPIRED: _RED, expiry.EXPIRING: _YELLOW, expiry.VALID: ''}


def dump_expiries():
    expiries = {}
    for dirpath, _, filenames in os.walk('issuingca/certs/'):
        for filename in filenames:
            if filename.endswith('.pem'):
                cert_path = os.path.join(dirpath, filename)
                expiries[filename] = expiry.enddate(cert_path)

    use_color = sys.stdout.isatty() and 'NO_COLOR' not in os.environ
    now = datetime.now(timezone.utc)
    for filename in sorted(expiries):
        enddate = expiries[filename]
        line = f'{filename}: {enddate.strftime("%c %Z")}'
        color = _COLORS[expiry.status_of(enddate, now)] if use_color else ''
        print(f'{color}{line}{_RESET}' if color else line)


# Program starts here
if __name__ == "__main__":
    common.run(dump_expiries)
