#!/usr/bin/env python3
# (c) Martin Erzberger 2025-2026
# Wrapper for OpenSSL commands

import os
import re
import ssl
import subprocess
import tempfile

from .common import (HomeCAError, ISSUING_CERT, ISSUING_KEY, PROJECT_ROOT, ROOT_CERT, config,
                     csr_path, key_path)

# Passwords are handed to OpenSSL through a pipe (fd:N), never on the command line or in
# the environment. Callers put these placeholders where OpenSSL expects a password source,
# e.g. '-passin', PASSIN; runssl replaces them with the pipe.
# (env:VAR failed intermittently with OpenSSL 4.0 on macOS, while a pipe kept working.)
PASSIN = '<passin>'
PASSOUT = '<passout>'


def _environment():
    """Variables the openssl.cnf files read ($ENV::...)."""
    c = config()
    return {
        'PROJECTROOT': PROJECT_ROOT,
        'COUNTRY': c.country, 'STATE': c.state, 'CITY': c.city, 'ORG': c.org,
        'ORGUNIT': c.orgunit, 'EMAIL': c.email,
        'ROOTCANAME': c.rootcaname, 'ISSUINGCANAME': c.issuingcaname,
    }


def runssl(*args, passin=None, passout=None):
    command = [config().opensslpath, *args]
    pipes = []
    try:
        for placeholder, password in ((PASSIN, passin), (PASSOUT, passout)):
            if placeholder in command:
                if password is None:
                    raise HomeCAError(f'OpenSSL needs a password for {placeholder}, none given.')
                read_end, write_end = os.pipe()
                pipes.append(read_end)
                with os.fdopen(write_end, 'w') as f:   # a password fits the pipe buffer
                    f.write(password + '\n')
                command[command.index(placeholder)] = f'fd:{read_end}'
        result = subprocess.run(command, capture_output=True, text=True,
                                env={**os.environ, **_environment()}, pass_fds=pipes)
    finally:
        for fd in pipes:
            os.close(fd)
    if result.returncode != 0:
        raise HomeCAError(
            f"OpenSSL failed (rc={result.returncode}):\n"
            f"  Command: {' '.join(command)}\n"
            f"  stderr: {result.stderr.strip()}"
        )
    return result.stdout


def text(cert_path):
    """The full human-readable dump of a certificate."""
    return runssl('x509', '-noout', '-text', '-in', cert_path)


def enddate(cert_path):
    # Returns the expiry date as a plain string, e.g. "Feb 26 10:00:00 2027 GMT"
    output = runssl('x509', '-noout', '-enddate', '-in', cert_path)
    return output.split('=', 1)[1].strip()


def leaf_pem(cert_path):
    """The first certificate of a cert file (our cert files hold leaf + issuing CA)."""
    with open(cert_path) as f:
        return f.read().split('-----END CERTIFICATE-----')[0] + '-----END CERTIFICATE-----\n'


def key_password_ok(path, password):
    """True if password decrypts the private key at path."""
    try:
        runssl('pkey', '-in', path, '-passin', PASSIN, '-noout', passin=password)
        return True
    except HomeCAError:
        return False


def signing_request(cert_name, cn, san_string, key_password, new_key):
    """Write the CSR of cert_name, with its existing key or (new_key) a new RSA 4096 key."""
    if new_key:
        key_args = ['-newkey', 'rsa:4096', '-keyout', key_path(cert_name), '-passout', PASSOUT]
    else:
        key_args = ['-key', key_path(cert_name), '-passin', PASSIN]
    return runssl(
        'req', *key_args,
        '-subj', f'/CN={cn}',
        '-addext', f'subjectAltName={san_string}',
        '-new', '-sha256',
        '-out', csr_path(cert_name),
        passin=key_password, passout=key_password,
    )


def sign_certificate(cert_name, issuing_password, out_path):
    """Sign the CSR of cert_name with the issuing CA into out_path."""
    # Write CA-added extensions to a temp file; -addext is not supported
    # by all OpenSSL 3.x builds when combined with x509 -req.
    ext_content = (
        "[ext]\n"
        "basicConstraints=CA:FALSE\n"
        "keyUsage=critical,digitalSignature,keyEncipherment\n"
        "extendedKeyUsage=serverAuth\n"
        "subjectKeyIdentifier=hash\n"
        "authorityKeyIdentifier=keyid,issuer:always\n"
    )
    fd, ext_file = tempfile.mkstemp(suffix='.cnf')
    try:
        with os.fdopen(fd, 'w') as f:
            f.write(ext_content)
        return runssl(
            'x509', '-req',
            '-in', csr_path(cert_name),
            '-CA', ISSUING_CERT,
            '-CAkey', ISSUING_KEY,
            '-CAserial', 'issuingca/serial',
            '-passin', PASSIN,
            '-copy_extensions', 'copy',
            '-days', '200', '-sha256',
            '-extfile', ext_file,
            '-extensions', 'ext',
            '-out', out_path,
            passin=issuing_password,
        )
    finally:
        os.unlink(ext_file)


def verify_certificate(cert_path):
    """Verify a cert file (leaf + issuing CA) against our Root CA."""
    return runssl('verify', '-CAfile', ROOT_CERT, '-untrusted', cert_path, cert_path)


def decrypted_key(cert_name, key_password):
    """Return the unencrypted private key as PEM text, without writing a file."""
    return runssl('rsa', '-in', key_path(cert_name), '-passin', PASSIN, passin=key_password)


def generate_key(path, password, bits=4096):
    return runssl(
        'genpkey', '-aes256',
        '-pass', PASSOUT,
        '-out', path,
        '-algorithm', 'RSA',
        '-pkeyopt', f'rsa_keygen_bits:{bits}',
        passout=password,
    )


def self_sign(key, config_path, password, cert_path, days=7300):
    """Generate a self-signed CA certificate (root CA)."""
    return runssl(
        'req', '-new', '-x509',
        '-config', config_path,
        '-key', key,
        '-passin', PASSIN,
        '-days', str(days),
        '-sha256', '-extensions', 'v3_ca',
        '-out', cert_path,
        passin=password,
    )


def ca_csr(key, config_path, password, csr):
    """Generate a CSR for a CA certificate, taking the DN from the config file."""
    return runssl(
        'req', '-new', '-sha256',
        '-config', config_path,
        '-key', key,
        '-passin', PASSIN,
        '-out', csr,
        passin=password,
    )


def sign_intermediate_ca(csr, config_path, password, cert_path, days=3650):
    """Sign an intermediate CA CSR with a parent CA."""
    return runssl(
        'ca', '-batch',
        '-config', config_path,
        '-extensions', 'v3_intermediate_ca',
        '-days', str(days),
        '-notext', '-md', 'sha256',
        '-passin', PASSIN,
        '-in', csr,
        '-out', cert_path,
        passin=password,
    )


def verify_chain(ca_cert_path, cert_path):
    """Verify cert_path against a directly trusted CA certificate."""
    return runssl('verify', '-CAfile', ca_cert_path, cert_path)


def verify_server_cert(der, host):
    """Verify a server certificate (DER) against our Root CA and host name, ignoring expiry,
    since a server usually still serves the expired certificate being replaced.
    Raises HomeCAError if it does not verify."""
    fd, path = tempfile.mkstemp(suffix='.pem')
    try:
        with os.fdopen(fd, 'w') as f:
            f.write(ssl.DER_cert_to_PEM_cert(der))
        runssl('verify', '-no_check_time', '-CAfile', ROOT_CERT,
               '-untrusted', ISSUING_CERT, '-verify_hostname', host, path)
    finally:
        os.unlink(path)


def subject_cn(cert_path):
    """Return the CN from the certificate subject, or an empty string."""
    output = runssl('x509', '-noout', '-subject', '-in', cert_path)
    m = re.search(r'\bCN\s*=\s*(.+?)(?:\s*[,/]|\s*$)', output.strip())
    return m.group(1).strip() if m else ''


def _ext_lines(cert_path, extension):
    """The value lines of one extension, from 'openssl x509 -ext'."""
    output = runssl('x509', '-noout', '-ext', extension, '-in', cert_path)
    return [s for s in (line.strip() for line in output.splitlines())
            if s and not s.startswith('X509v3')]


def san_list(cert_path):
    """Return SANs as a list of strings, e.g. ['DNS:*.example.com', ...]."""
    return [e.strip() for line in _ext_lines(cert_path, 'subjectAltName')
            for e in line.split(',') if e.strip()]


def key_usage(cert_path):
    """Return the Key Usage value string, or None if not present."""
    return ', '.join(_ext_lines(cert_path, 'keyUsage')) or None


def extended_key_usage(cert_path):
    """Return the Extended Key Usage value string, or None if not present."""
    return ', '.join(_ext_lines(cert_path, 'extendedKeyUsage')) or None
