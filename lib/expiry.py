#!/usr/bin/env python3
# (c) Martin Erzberger 2025-2026
# Certificate expiry dates and their status (expired / expiring / valid)

from datetime import datetime, timedelta, timezone

from . import openssl

WARN_PERIOD = timedelta(days=60)

EXPIRED = 'expired'
EXPIRING = 'expiring'
VALID = 'valid'

_MONTHS = {
    'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5,  'Jun': 6,
    'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12,
}


def parse_enddate(raw):
    """Parse OpenSSL enddate string into an aware UTC datetime.

    OpenSSL always emits English month abbreviations regardless of locale,
    so we parse manually rather than using strptime's locale-dependent %b.
    """
    # OpenSSL format: "Feb 26 10:00:00 2027 GMT"
    mon, day, time_, year, _ = raw.split()
    h, m, s = time_.split(':')
    return datetime(int(year), _MONTHS[mon], int(day), int(h), int(m), int(s),
                    tzinfo=timezone.utc)


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
