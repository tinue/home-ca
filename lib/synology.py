#!/usr/bin/env python3
# (c) Martin Erzberger 2026
# Minimal client for the Synology DSM 7 Web API: login (with 2FA), list and import certificates.
# Same API calls as the acme.sh synology_dsm deploy hook.
#
# TLS: DSM is trusted only if its certificate chains to our own Root CA. The expiry date
# is not checked, because DSM usually still serves the expired certificate being replaced.

import http.client
import json
import ssl
import urllib.parse
import uuid

from . import openssl

# DSM error codes for SYNO.API.Auth login
_AUTH_ERRORS = {
    400: 'wrong account or password',
    401: 'account disabled',
    402: 'permission denied',
    403: 'one-time password required',
    404: 'wrong one-time password',
    406: '2-factor authentication must be enabled first',
    407: 'blocked IP address (too many failed logins)',
    408: 'password expired',
    410: 'password must be changed',
}


class DSMError(Exception):
    pass


class DSM:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.sid = None
        self.token = None
        self._trusted = set()          # DER bytes of server certs already verified
        self._context = ssl.create_default_context()
        self._context.check_hostname = False
        self._context.verify_mode = ssl.CERT_NONE   # verified by _check_peer instead

    def _check_peer(self, der):
        """Verify the server certificate against our Root CA (hostname yes, expiry no)."""
        if der in self._trusted:
            return
        try:
            openssl.verify_server_cert(der, self.host)
        except RuntimeError as e:
            raise DSMError(f'{self.host} does not present a certificate from our CA:\n{e}')
        self._trusted.add(der)

    def _call(self, cgi, params, body=None, content_type=None):
        """POST to /webapi/<cgi>; returns the 'data' member of a successful response."""
        query = dict(params)
        if self.sid:
            query['_sid'] = self.sid
        if self.token:
            query['SynoToken'] = self.token
        if body is None:
            body = urllib.parse.urlencode(query).encode()
            content_type = 'application/x-www-form-urlencoded'
            url = f'/webapi/{cgi}'
        else:
            url = f'/webapi/{cgi}?{urllib.parse.urlencode(query)}'
        headers = {'Content-Type': content_type}
        if self.token:
            headers['X-SYNO-TOKEN'] = self.token

        conn = http.client.HTTPSConnection(self.host, self.port, context=self._context, timeout=60)
        try:
            conn.connect()
            self._check_peer(conn.sock.getpeercert(binary_form=True))
            conn.request('POST', url, body=body, headers=headers)
            response = conn.getresponse()
            text = response.read().decode()
        finally:
            conn.close()
        try:
            result = json.loads(text)
        except json.JSONDecodeError:
            raise DSMError(f'Unexpected response from {url} (HTTP {response.status}): {text[:200]}')
        if not result.get('success'):
            raise DSMError(f'{params.get("api")}.{params.get("method")} failed: {result.get("error")}',
                           result.get('error', {}).get('code'))
        return result.get('data', {})

    def login(self, account, password, otp=None):
        """Log in; otp is a callable returning a one-time password, used only if DSM asks."""
        info = self._call('query.cgi', {'api': 'SYNO.API.Info', 'version': 1,
                                        'method': 'query', 'query': 'SYNO.API.Auth'})
        auth = info['SYNO.API.Auth']
        self._auth = auth
        params = {'api': 'SYNO.API.Auth', 'version': auth['maxVersion'], 'method': 'login',
                  'account': account, 'passwd': password, 'format': 'sid',
                  'enable_syno_token': 'yes'}
        try:
            data = self._call(auth['path'], params)
        except DSMError as e:
            code = e.args[1] if len(e.args) > 1 else None
            if code != 403 or otp is None:
                raise DSMError(f'Login failed: {_AUTH_ERRORS.get(code, e)}')
            try:
                data = self._call(auth['path'], {**params, 'otp_code': otp()})
            except DSMError as e:
                code = e.args[1] if len(e.args) > 1 else None
                raise DSMError(f'Login failed: {_AUTH_ERRORS.get(code, e)}')
        self.sid = data['sid']
        self.token = data.get('synotoken')

    def logout(self):
        if self.sid:
            try:
                self._call(self._auth['path'], {'api': 'SYNO.API.Auth', 'version': self._auth['maxVersion'],
                                                'method': 'logout'})
            except DSMError:
                pass   # DSM may be restarting its web server after an import
            self.sid = self.token = None

    def certificates(self):
        data = self._call('entry.cgi', {'api': 'SYNO.Core.Certificate.CRT', 'version': 1, 'method': 'list'})
        return data.get('certificates', [])

    def import_certificate(self, cert_id, desc, key_pem, cert_pem, chain_pem, as_default):
        """Replace certificate cert_id (services bound to it keep using it)."""
        boundary = uuid.uuid4().hex
        parts = []
        for name, filename, content in (('key', 'privkey.pem', key_pem),
                                        ('cert', 'cert.pem', cert_pem),
                                        ('inter_cert', 'chain.pem', chain_pem)):
            parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; '
                         f'filename="{filename}"\r\nContent-Type: application/octet-stream\r\n\r\n'
                         f'{content}\r\n')
        for name, value in (('id', cert_id), ('desc', desc), ('as_default', 'true' if as_default else '')):
            parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n')
        body = (''.join(parts) + f'--{boundary}--\r\n').encode()
        return self._call('entry.cgi', {'api': 'SYNO.Core.Certificate', 'version': 1, 'method': 'import'},
                          body=body, content_type=f'multipart/form-data; boundary={boundary}')
