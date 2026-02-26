#!/usr/bin/env python3
# (c) Martin Erzberger 2025-2026
# Wrapper for OpenSSL commands

# This part needs to be duplicated in each script
def setup():
  global variables
  from common import setup
  variables = setup()

def version():
    return runssl('--version')

def validity(certificate):
   cert_dump = runssl('x509', '-noout', '-text', '-in', certificate)
   return cert_dump

def enddate(cert_path):
    # Returns the expiry date as a plain string, e.g. "Feb 26 10:00:00 2027 GMT"
    output = runssl('x509', '-noout', '-enddate', '-in', cert_path)
    return output.split('=', 1)[1].strip()

def signing_request(domain, key_password):
  setup()
  import os
  import subprocess
  # For this, we need to be in the 'issuingca' directory
  output = runssl('req', '-newkey', 'rsa:2048', '-keyout', 'issuingca/private/'+domain+'.key.pem', '-config', 'issuingca/openssl.cnf', '-passout', 'pass:'+key_password, '-subj',
         '/CN=*.'+domain, '-addext', 'subjectAltName=DNS.1:*.'+domain+',DNS.2:'+domain, '-new', '-sha256', '-out', 'issuingca/csr/'+domain+'.csr.pem')
  print(output)

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

def signing_request_new(cert_name, cn, san_string, key_password):
    return runssl(
        'req', '-newkey', 'rsa:2048',
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
    return runssl(
        'x509', '-req',
        '-in', f'issuingca/csr/{cert_name}.csr.pem',
        '-CA', 'issuingca/certs/issuing.cert.pem',
        '-CAkey', 'issuingca/private/issuing.key.pem',
        '-CAserial', 'issuingca/serial',
        '-passin', f'pass:{issuing_password}',
        '-copy_extensions', 'copy',
        '-days', '200', '-sha256',
        '-addext', 'basicConstraints=CA:FALSE',
        '-addext', 'keyUsage=critical,digitalSignature,keyEncipherment',
        '-addext', 'extendedKeyUsage=serverAuth',
        '-addext', 'subjectKeyIdentifier=hash',
        '-addext', 'authorityKeyIdentifier=keyid,issuer:always',
        '-out', f'issuingca/certs/{cert_name}.cert.pem',
    )

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
