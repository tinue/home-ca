#!/usr/bin/env python3
# (c) Martin Erzberger 2025
# Generates a wildcard certificate for a domain 

# This part needs to be duplicated in each script
def setup():
  global variables
  from common import setup
  variables = setup()

def generate_wildcard_cert(domain):
      import openssl
      # Read-in the old password for the issuing key
      issuing_password = input("Existing issuing CA private key password: ")
      # Read-in the new password for the server key
      key_password = input("New wildcard certificate private key password: ")

      # Make the signing request
      openssl.signing_request(domain, key_password)

# Sign the certificate; Validity is the maximum allowed under any modern browser (e.g. Chrome)
# Use 397, not 398, see https://support.apple.com/en-us/HT211025
'ca -batch -config openssl.cnf -extensions server_cert -days 397 -notext -md sha256 -in csr/$1.csr.pem -passin env:ISSUINGKEYPWD -out certs/$1.cert.pem'
# Add the issuing CA to the certificate. This way, the clients only have to import the Root CA.
#cat certs/issuing.cert.pem >> certs/$1.cert.pem
# Readable by all (certificates are public by design)
#chmod 444 certs/$1.cert.pem
# Validate the certificate
'verify -CAfile ../rootca/certs/ca.cert.pem -untrusted certs/$1.cert.pem certs/$1.cert.pem'
# Decrypt the key for import to the server. Delete the decrypted version after importing!
'rsa -in private/$1.key.pem -passin env:SERVERKEYPWD -out private/$1.key.open.pem'

# Program starts here
if __name__ == "__main__":
  import sys
  setup()
  if len(sys.argv) != 2:
    print("Usage: generatewildcardcert [domain]")
    exit(1)
  generate_wildcard_cert(sys.argv[1])
