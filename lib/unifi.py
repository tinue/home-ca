#!/usr/bin/env python3
# (c) Martin Erzberger 2026
# Minimal client for the UniFi OS console API: login, list, upload, activate and delete
# the custom certificates of Settings > Control Plane > Console (UniFi OS 4.1 and newer).
# These are the calls the web UI makes; Ubiquiti does not document them.
#
# TLS: see lib/https.py.

import json
from http.cookies import SimpleCookie

from .common import HomeCAError
from .https import PinnedHTTPS


class UniFiError(HomeCAError):
    pass


class UniFiOS:
    def __init__(self, host, port=443):
        self._https = PinnedHTTPS(host, port)
        self._cookie = None
        self._csrf = None

    def _request(self, method, path, body=None):
        """Send a JSON request to /api/<path>; returns the decoded response body (or None)."""
        headers = {'Accept': 'application/json'}
        if body is not None:
            headers['Content-Type'] = 'application/json'
        if self._cookie:
            headers['Cookie'] = f'TOKEN={self._cookie}'
        if self._csrf:
            headers['X-CSRF-Token'] = self._csrf

        response, text = self._https.request(method, f'/api/{path}',
                                             None if body is None else json.dumps(body), headers)

        for header in response.headers.get_all('Set-Cookie') or []:
            token = SimpleCookie(header).get('TOKEN')
            if token is not None:
                self._cookie = token.value
        self._csrf = (response.getheader('X-Updated-CSRF-Token')
                      or response.getheader('X-CSRF-Token') or self._csrf)

        if response.status >= 300:
            raise UniFiError(f'{method} /api/{path} failed (HTTP {response.status}): {text[:300]}',
                             code=response.status)
        if not text:
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            raise UniFiError(f'Unexpected response from /api/{path} (HTTP {response.status}): {text[:200]}')

    def login(self, username, password, otp=None):
        """Log in with a local console account; otp is the current one-time password, if the
        account has 2FA (the console rejects a missing one with HTTP 499)."""
        body = {'username': username, 'password': password, 'rememberMe': False}
        if otp:
            body['token'] = otp
        try:
            self._request('POST', 'auth/login', body)
        except UniFiError as e:
            if e.code == 499:
                raise UniFiError('Login failed: the account requires a one-time password')
            raise UniFiError(f'Login failed: {e}')
        if not self._cookie:
            raise UniFiError('Login failed: no session cookie in the response')

    def logout(self):
        if self._cookie:
            try:
                self._request('POST', 'auth/logout')
            except UniFiError:
                pass
            self._cookie = self._csrf = None

    def certificates(self):
        """All custom certificates: id, name, fingerprint, subject, valid_to, source, active, ..."""
        return self._request('GET', 'userCertificates')

    def upload_certificate(self, name, cert_pem, key_pem):
        """Add a certificate (not yet active); name and fingerprint must be new."""
        return self._request('POST', 'userCertificates', {'name': name, 'cert': cert_pem, 'key': key_pem})

    def activate_certificate(self, cert_id):
        """Serve cert_id on the console; UniFi OS reloads its web server."""
        return self._request('PUT', f'userCertificates/{cert_id}/status', {'active': True})

    def delete_certificate(self, cert_id):
        self._request('DELETE', f'userCertificates/{cert_id}')
