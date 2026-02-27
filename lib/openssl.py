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


def runssl(*args):
  setup()
  import subprocess, re
  command = [variables.opensslpath] + list(args)
  result = subprocess.run(command, capture_output=True, text=True)
  if result.returncode != 0:
      safe_cmd = re.sub(r'pass:[^\s,]+', 'pass:***', ' '.join(command))
      raise RuntimeError(
          f"OpenSSL failed (rc={result.returncode}):\n"
          f"  Command: {safe_cmd}\n"
          f"  stderr: {result.stderr.strip()}"
      )
  return result.stdout

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
        '-passout', f'pass:{key_password}',
        '-subj', f'/CN={cn}',
        '-addext', f'subjectAltName={san_string}',
        '-new', '-sha256',
        '-out', f'issuingca/csr/{cert_name}.csr.pem',
    )

def signing_request_renew(cert_name, cn, san_string, key_password):
    return runssl(
        'req', '-key', f'issuingca/private/{cert_name}.key.pem',
        '-passin', f'pass:{key_password}',
        '-subj', f'/CN={cn}',
        '-addext', f'subjectAltName={san_string}',
        '-new', '-sha256',
        '-out', f'issuingca/csr/{cert_name}.csr.pem',
    )

def sign_certificate(cert_name, issuing_password):
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
            '-passin', f'pass:{issuing_password}',
            '-copy_extensions', 'copy',
            '-days', '200', '-sha256',
            '-extfile', ext_file,
            '-extensions', 'ext',
            '-out', f'issuingca/certs/{cert_name}.cert.pem',
        )
    finally:
        os.unlink(ext_file)

def verify_certificate(cert_name):
    cert_path = f'issuingca/certs/{cert_name}.cert.pem'
    return runssl(
        'verify',
        '-CAfile', 'rootca/certs/ca.cert.pem',
        '-untrusted', cert_path,
        cert_path,
    )

def decrypt_key(cert_name, key_password):
    return runssl(
        'rsa',
        '-in', f'issuingca/private/{cert_name}.key.pem',
        '-passin', f'pass:{key_password}',
        '-out', f'issuingca/private/{cert_name}.key.open.pem',
    )

def generate_key(key_path, password, bits=4096):
    return runssl(
        'genpkey', '-aes256',
        '-pass', f'pass:{password}',
        '-out', key_path,
        '-algorithm', 'RSA',
        '-pkeyopt', f'rsa_keygen_bits:{bits}',
    )

def self_sign(key_path, config_path, password, cert_path, days=7300):
    """Generate a self-signed CA certificate (root CA)."""
    return runssl(
        'req', '-new', '-x509',
        '-config', config_path,
        '-key', key_path,
        '-passin', f'pass:{password}',
        '-days', str(days),
        '-sha256', '-extensions', 'v3_ca',
        '-out', cert_path,
    )

def ca_csr(key_path, config_path, password, csr_path):
    """Generate a CSR for a CA certificate, taking the DN from the config file."""
    return runssl(
        'req', '-new', '-sha256',
        '-config', config_path,
        '-key', key_path,
        '-passin', f'pass:{password}',
        '-out', csr_path,
    )

def sign_intermediate_ca(csr_path, config_path, password, cert_path, days=3650):
    """Sign an intermediate CA CSR with a parent CA."""
    return runssl(
        'ca', '-batch',
        '-config', config_path,
        '-extensions', 'v3_intermediate_ca',
        '-days', str(days),
        '-notext', '-md', 'sha256',
        '-passin', f'pass:{password}',
        '-in', csr_path,
        '-out', cert_path,
    )

def verify_chain(ca_cert_path, cert_path):
    """Verify cert_path against a directly trusted CA certificate."""
    return runssl(
        'verify',
        '-CAfile', ca_cert_path,
        cert_path,
    )


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
