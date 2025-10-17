#!/usr/bin/env python3
# (c) Martin Erzberger 2025
# Wrapper for OpenSSL commands

# This part needs to be duplicated in each script
def setup():
  global variables
  from common import setup
  variables = setup()

def version():
    return runssl('--version')

def validity(certificate):
   cert_dump =  runssl('x509', '-noout', '-text', '-in', certificate)
   #| grep "Not After :" | cut -c24-
   return cert_dump

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
  import subprocess

  command = [variables.opensslpath]
  for arg in args:
     command.append(arg)
  output = subprocess.run(command, capture_output=True, text=True)
  return output.stdout