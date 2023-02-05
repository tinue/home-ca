#!/bin/bash
# (c) Martin Erzberger 2019
# Create a server certificate

# Import the variables and change into CA directory
DIR="$( cd "$( dirname "$0" )" >/dev/null 2>&1 && pwd )"
cd $DIR
source ./variables.sh

# Check if an argument has been provided
if [ $# -eq 0 ]
  then
    echo "The name of the certificate must be supplied (without domain), e.g. 'example'."
    exit 1
fi

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
$OPENSSL req -newkey rsa:2048 -keyout private/$1.$DOMAIN.key.pem \
      -config openssl.cnf \
      -passout env:SERVERKEYPWD \
      -subj "/CN=$1.$DOMAIN" \
      -addext "subjectAltName = DNS:$1.$DOMAIN" \
      -new -sha256 -out csr/$1.$DOMAIN.csr.pem
# Sign the certificate; Validity is the maximum allowed under any modern browser (e.g. Chrome)
$OPENSSL ca -batch -config openssl.cnf \
      -extensions server_cert -days 825 -notext -md sha256 \
      -in csr/$1.$DOMAIN.csr.pem \
      -passin env:ISSUINGKEYPWD \
      -out certs/$1.$DOMAIN.cert.pem
# Add the issuing CA to the certificate. This way, the clients only have to import the Root CA.
cat certs/issuing.cert.pem >> certs/$1.$DOMAIN.cert.pem
# Readable by all (certificates are public by design)
chmod 444 certs/$1.$DOMAIN.cert.pem
# Validate the certificate
$OPENSSL verify -CAfile ../rootca/certs/ca.cert.pem -untrusted certs/$1.$DOMAIN.cert.pem \
      certs/$1.$DOMAIN.cert.pem
# Decrypt the key for import to the server. Delete the decrypted version after importing!
$OPENSSL rsa -in private/$1.$DOMAIN.key.pem -passin env:SERVERKEYPWD -out private/$1.$DOMAIN.key.open.pem
