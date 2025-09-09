#!/bin/bash
# (c) Martin Erzberger 2025
# Create a wildcard certificate

# Import the variables and change into CA directory
DIR="$( cd "$( dirname "$0" )" >/dev/null 2>&1 && pwd )"
cd $DIR
source ./variables.sh

# Check if an argument has been provided
if [ $# -eq 0 ]
  then
    echo "The name of the domain must be supplied, e.g. 'example.com'."
    exit 1
fi

# Read-in the old password for the issuing key
read -sp 'Existing issuing CA private key password: ' ISSUINGKEYPWD
echo ''
export ISSUINGKEYPWD
# Read-in the new password for the server key
read -sp 'New wildcard certificate private key password: ' SERVERKEYPWD
echo ''
export SERVERKEYPWD

cd issuingca
# Make the signing request
$OPENSSL req -newkey rsa:2048 -keyout private/$1.key.pem \
      -config openssl.cnf \
      -passout env:SERVERKEYPWD \
      -subj "/CN=*.$1" \
      -addext "subjectAltName=DNS.1:*.$1,DNS.2:$1" \
      -new -sha256 -out csr/$1.csr.pem
# Sign the certificate; Validity is the maximum allowed under any modern browser (e.g. Chrome)
# Use 397, not 398, see https://support.apple.com/en-us/HT211025
$OPENSSL ca -batch -config openssl.cnf \
      -extensions server_cert -days 397 -notext -md sha256 \
      -in csr/$1.csr.pem \
      -passin env:ISSUINGKEYPWD \
      -out certs/$1.cert.pem
# Add the issuing CA to the certificate. This way, the clients only have to import the Root CA.
cat certs/issuing.cert.pem >> certs/$1.cert.pem
# Readable by all (certificates are public by design)
chmod 444 certs/$1.cert.pem
# Validate the certificate
$OPENSSL verify -CAfile ../rootca/certs/ca.cert.pem -untrusted certs/$1.cert.pem \
      certs/$1.cert.pem
# Decrypt the key for import to the server. Delete the decrypted version after importing!
$OPENSSL rsa -in private/$1.key.pem -passin env:SERVERKEYPWD -out private/$1.key.open.pem
