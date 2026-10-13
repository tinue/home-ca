#!/usr/bin/env python3
# (c) Martin Erzberger 2025-2026
# Certificate expiry dates and their status (expired / expiring / valid)

import ssl
from datetime import datetime, timedelta, timezone

from . import openssl

WARN_PERIOD = timedelta(days=60)

EXPIRED = 'expired'
EXPIRING = 'expiring'
VALID = 'valid'

def parse_enddate(raw):
    """Parse an OpenSSL date ("Feb 26 10:00:00 2027 GMT") into an aware UTC datetime.
    ssl.cert_time_to_seconds is locale-independent, unlike strptime's %b."""
    return datetime.fromtimestamp(ssl.cert_time_to_seconds(raw), timezone.utc)


def enddate(cert_path):
    return parse_enddate(openssl.enddate(cert_path))


def status_of(end, now=None):
    """Expired, expiring within WARN_PERIOD, or valid."""
    now = now or datetime.now(timezone.utc)
    if end <= now:
        return EXPIRED
    if end - now <= WARN_PERIOD:
        return EXPIRING
    return VALID


def status(cert_path):
    """Return (status, enddate) for a certificate file."""
    end = enddate(cert_path)
    return status_of(end), end
