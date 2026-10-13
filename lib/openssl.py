#!/usr/bin/env python3
# (c) Martin Erzberger 2025-2026
# Wrapper for OpenSSL commands

def setup():
  global variables
  from .common import setup
  variables = setup()


def validity(certificate):
   cert_dump = runssl('x509', '-noout', '-text', '-in', certificate)
   return cert_dump

def enddate(cert_path):
    # Returns the expiry date as a plain string, e.g. "Feb 26 10:00:00 2027 GMT"
    output = runssl('x509', '-noout', '-enddate', '-in', cert_path)
    return output.split('=', 1)[1].strip()


# Passwords are handed to OpenSSL through the environment (env:VAR),
# never on the command line where other processes could see them.
PASSIN = 'HOMECA_PASSIN'
PASSOUT = 'HOMECA_PASSOUT'


def runssl(*args, passin=None, passout=None):
  setup()
  import os, subprocess
  command = [variables.opensslpath] + list(args)
  env = dict(os.environ)
  if passin is not None:
      env[PASSIN] = passin
  if passout is not None:
      env[PASSOUT] = passout
  result = subprocess.run(command, capture_output=True, text=True, env=env)
  if result.returncode != 0:
      raise RuntimeError(
          f"OpenSSL failed (rc={result.returncode}):\n"
          f"  Command: {' '.join(command)}\n"
          f"  stderr: {result.stderr.strip()}"
      )
  return result.stdout


def key_password_ok(key_path, password):
    """True if password decrypts the private key at key_path."""
    try:
        runssl('pkey', '-in', key_path, '-passin', f'env:{PASSIN}', '-noout', passin=password)
        return True
    except RuntimeError:
        return False

def cert_validity_text(cert_path):
    text = runssl('x509', '-noout', '-text', '-in', cert_path)
    lines = text.splitlines()
    result = []
    in_validity = False
    for line in lines:
        if 'Validity' in line:
            in_validity = True
        if in_validity:
            result.append(line)
            if len(result) >= 3:  # Validity header + Not Before + Not After
                break
    return '\n'.join(result)

def signing_request(cert_name, cn, san_string, key_password):
    return runssl(
        'req', '-newkey', 'rsa:4096',
        '-keyout', f'issuingca/private/{cert_name}.key.pem',
        '-passout', f'env:{PASSOUT}',
        '-subj', f'/CN={cn}',
        '-addext', f'subjectAltName={san_string}',
        '-new', '-sha256',
        '-out', f'issuingca/csr/{cert_name}.csr.pem',
        passout=key_password,
    )

def signing_request_renew(cert_name, cn, san_string, key_password):
    return runssl(
        'req', '-key', f'issuingca/private/{cert_name}.key.pem',
        '-passin', f'env:{PASSIN}',
        '-subj', f'/CN={cn}',
        '-addext', f'subjectAltName={san_string}',
        '-new', '-sha256',
        '-out', f'issuingca/csr/{cert_name}.csr.pem',
        passin=key_password,
    )

def sign_certificate(cert_name, issuing_password, out_path=None):
    """Sign the CSR of cert_name; writes to out_path (default: the cert's path)."""
    import os
    import tempfile
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
            '-in', f'issuingca/csr/{cert_name}.csr.pem',
            '-CA', 'issuingca/certs/issuing.cert.pem',
            '-CAkey', 'issuingca/private/issuing.key.pem',
            '-CAserial', 'issuingca/serial',
            '-passin', f'env:{PASSIN}',
            '-copy_extensions', 'copy',
            '-days', '200', '-sha256',
            '-extfile', ext_file,
            '-extensions', 'ext',
            '-out', out_path or f'issuingca/certs/{cert_name}.cert.pem',
            passin=issuing_password,
        )
    finally:
        os.unlink(ext_file)

def verify_certificate(cert_name, cert_path=None):
    cert_path = cert_path or f'issuingca/certs/{cert_name}.cert.pem'
    return runssl(
        'verify',
        '-CAfile', 'rootca/certs/ca.cert.pem',
        '-untrusted', cert_path,
        cert_path,
    )

def decrypted_key(cert_name, key_password):
    """Return the unencrypted private key as PEM text, without writing a file."""
    return runssl(
        'rsa',
        '-in', f'issuingca/private/{cert_name}.key.pem',
        '-passin', f'env:{PASSIN}',
        passin=key_password,
    )

def generate_key(key_path, password, bits=4096):
    return runssl(
        'genpkey', '-aes256',
        '-pass', f'env:{PASSOUT}',
        '-out', key_path,
        '-algorithm', 'RSA',
        '-pkeyopt', f'rsa_keygen_bits:{bits}',
        passout=password,
    )

def self_sign(key_path, config_path, password, cert_path, days=7300):
    """Generate a self-signed CA certificate (root CA)."""
    return runssl(
        'req', '-new', '-x509',
        '-config', config_path,
        '-key', key_path,
        '-passin', f'env:{PASSIN}',
        '-days', str(days),
        '-sha256', '-extensions', 'v3_ca',
        '-out', cert_path,
        passin=password,
    )

def ca_csr(key_path, config_path, password, csr_path):
    """Generate a CSR for a CA certificate, taking the DN from the config file."""
    return runssl(
        'req', '-new', '-sha256',
        '-config', config_path,
        '-key', key_path,
        '-passin', f'env:{PASSIN}',
        '-out', csr_path,
        passin=password,
    )

def sign_intermediate_ca(csr_path, config_path, password, cert_path, days=3650):
    """Sign an intermediate CA CSR with a parent CA."""
    return runssl(
        'ca', '-batch',
        '-config', config_path,
        '-extensions', 'v3_intermediate_ca',
        '-days', str(days),
        '-notext', '-md', 'sha256',
        '-passin', f'env:{PASSIN}',
        '-in', csr_path,
        '-out', cert_path,
        passin=password,
    )

def verify_chain(ca_cert_path, cert_path):
    """Verify cert_path against a directly trusted CA certificate."""
    return runssl(
        'verify',
        '-CAfile', ca_cert_path,
        cert_path,
    )


def verify_server_cert(der, host):
    """Verify a server certificate (DER) against our Root CA and host name, ignoring expiry,
    since a server usually still serves the expired certificate being replaced.
    Raises RuntimeError if it does not verify."""
    import os, ssl, tempfile
    fd, path = tempfile.mkstemp(suffix='.pem')
    try:
        with os.fdopen(fd, 'w') as f:
            f.write(ssl.DER_cert_to_PEM_cert(der))
        runssl('verify', '-no_check_time', '-CAfile', 'rootca/certs/ca.cert.pem',
               '-untrusted', 'issuingca/certs/issuing.cert.pem', '-verify_hostname', host, path)
    finally:
        os.unlink(path)


def subject_cn(cert_path):
    """Return the CN from the certificate subject, or an empty string."""
    import re
    output = runssl('x509', '-noout', '-subject', '-in', cert_path)
    m = re.search(r'\bCN\s*=\s*(.+?)(?:\s*[,/]|\s*$)', output.strip())
    return m.group(1).strip() if m else ''


def _parse_ext_lines(output):
    """Extract the value lines from an 'openssl x509 -ext ...' block."""
    lines = []
    for line in output.strip().splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith('X509v3'):
            lines.append(stripped)
    return lines


def san_list(cert_path):
    """Return SANs as a list of strings, e.g. ['DNS:*.example.com', ...]."""
    output = runssl('x509', '-noout', '-ext', 'subjectAltName', '-in', cert_path)
    entries = []
    for line in _parse_ext_lines(output):
        entries.extend(e.strip() for e in line.split(',') if e.strip())
    return entries


def key_usage(cert_path):
    """Return the Key Usage value string, or None if not present."""
    output = runssl('x509', '-noout', '-ext', 'keyUsage', '-in', cert_path)
    lines = _parse_ext_lines(output)
    return ', '.join(lines) if lines else None


def extended_key_usage(cert_path):
    """Return the Extended Key Usage value string, or None if not present."""
    output = runssl('x509', '-noout', '-ext', 'extendedKeyUsage', '-in', cert_path)
    lines = _parse_ext_lines(output)
    return ', '.join(lines) if lines else None
