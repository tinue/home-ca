#!/usr/bin/env python3
# (c) Martin Erzberger 2026
# HTTPS requests to our own servers, which are trusted only if their certificate chains
# to our Root CA. The expiry date is not checked: a server usually still serves the
# expired certificate that is about to be replaced.

import http.client
import ssl

from . import openssl
from .common import HomeCAError


class PinnedHTTPS:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self._trusted = set()          # DER bytes of server certs already verified
        self._context = ssl.create_default_context()
        self._context.check_hostname = False
        self._context.verify_mode = ssl.CERT_NONE   # verified by _check_peer instead

    def _check_peer(self, der):
        if der in self._trusted:
            return
        try:
            openssl.verify_server_cert(der, self.host)
        except HomeCAError as e:
            raise HomeCAError(f'{self.host} does not present a certificate from our CA:\n{e}')
        self._trusted.add(der)

    def request(self, method, url, body=None, headers=None):
        """Send one request; returns (response, decoded body text)."""
        conn = http.client.HTTPSConnection(self.host, self.port, context=self._context, timeout=60)
        try:
            conn.connect()
            self._check_peer(conn.sock.getpeercert(binary_form=True))
            conn.request(method, url, body=body, headers=headers or {})
            response = conn.getresponse()
            return response, response.read().decode()
        finally:
            conn.close()
