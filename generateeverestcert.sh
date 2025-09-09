#!/bin/bash
# (c) Martin Erzberger 2025
# Create a combined internal / external certificate for the home server

# Import the variables and change into CA directory
DIR="$( cd "$( dirname "$0" )" >/dev/null 2>&1 && pwd )"
cd $DIR
source ./variables.sh

# Check if an argument has been provided
export SERVERNAME=everest

# Read-in the old password for the issuing key
read -sp 'Existing issuing CA private key password: ' ISSUINGKEYPWD
echo ''
export ISSUINGKEYPWD
# Read-in the new password for the server key
read -sp 'New server private key password: ' SERVERKEYPWD
echo ''
export SERVERKEYPWD

cd issuingca
# Make the signing request
$OPENSSL req -newkey rsa:2048 -keyout private/$SERVERNAME.$DOMAIN.key.pem \
      -config openssl.cnf \
      -passout env:SERVERKEYPWD \
      -subj "/CN=$SERVERNAME.$DOMAIN" \
      -addext "subjectAltName=DNS.1:$SERVERNAME.$DOMAIN,DNS.2:$DOMAIN2,DNS.3:$DOMAIN3" \
      -new -sha256 -out csr/$SERVERNAME.$DOMAIN.csr.pem
# Sign the certificate; Validity is the maximum allowed under any modern browser (e.g. Chrome)
# Use 397, not 398, see https://support.apple.com/en-us/HT211025
$OPENSSL ca -batch -config openssl.cnf \
      -extensions server_cert -days 397 -notext -md sha256 \
      -in csr/$SERVERNAME.$DOMAIN.csr.pem \
      -passin env:ISSUINGKEYPWD \
      -out certs/$SERVERNAME.$DOMAIN.cert.pem
# Add the issuing CA to the certificate. This way, the clients only have to import the Root CA.
cat certs/issuing.cert.pem >> certs/$SERVERNAME.$DOMAIN.cert.pem
# Readable by all (certificates are public by design)
chmod 444 certs/$SERVERNAME.$DOMAIN.cert.pem
# Validate the certificate
$OPENSSL verify -CAfile ../rootca/certs/ca.cert.pem -untrusted certs/$SERVERNAME.$DOMAIN.cert.pem \
      certs/$SERVERNAME.$DOMAIN.cert.pem
# Decrypt the key for import to the server. Delete the decrypted version after importing!
$OPENSSL rsa -in private/$SERVERNAME.$DOMAIN.key.pem -passin env:SERVERKEYPWD -out private/$SERVERNAME.$DOMAIN.key.open.pem
