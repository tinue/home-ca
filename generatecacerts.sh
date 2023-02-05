#!/bin/sh
# (c) Martin Erzberger 2019
# Generates the Root- and Issuing CA certificates

# Import the variables and change into CA directory
DIR="$( cd "$( dirname "$0" )" >/dev/null 2>&1 && pwd )"
cd $DIR
source ./variables.sh
# Read-in the passwords for the two keys (root and issuing)
read -sp 'Root CA Private key password: ' ROOTKEYPWD
echo ''
export ROOTKEYPWD
read -sp 'Issuing CA Private key password: ' ISSUINGKEYPWD
echo ''
export ISSUINGKEYPWD

# Start with the Root CA
cd rootca
# Generate the private key
$OPENSSL genpkey -aes256 -pass env:ROOTKEYPWD -out private/ca.key.pem -algorithm RSA -pkeyopt rsa_keygen_bits:4096
# Protect access
chmod 400 private/ca.key.pem
# Generate and self-sign the certificate; Valid for 20 years
$OPENSSL req -config openssl.cnf \
      -key private/ca.key.pem \
      -passin env:ROOTKEYPWD \
      -new -x509 -days 7300 -sha256 -extensions v3_ca \
      -out certs/ca.cert.pem
# Enable read for all (the certificate is public)
chmod 444 certs/ca.cert.pem

# Follow-up with the issuing CA
cd ../issuingca
# Generate the private key
$OPENSSL genpkey -aes256 -pass env:ISSUINGKEYPWD -out private/issuing.key.pem -algorithm RSA -pkeyopt rsa_keygen_bits:4096
# Protect access
chmod 400 private/issuing.key.pem
# Generate the certificate signing request
$OPENSSL req -config openssl.cnf -new -sha256 \
      -key private/issuing.key.pem \
      -passin env:ISSUINGKEYPWD \
      -out csr/issuing.csr.pem
# Make and sign the certificate; Valid for 10 years
$OPENSSL ca -config ../rootca/openssl.cnf -batch -extensions v3_intermediate_ca \
      -days 3650 -notext -md sha256 \
      -passin env:ROOTKEYPWD \
      -in csr/issuing.csr.pem \
      -out certs/issuing.cert.pem

# Dump both certificatea for visual inspection
echo
echo ------------------------------------------------------
echo 'Root CA:'
$OPENSSL x509 -noout -text -in ../rootca/certs/ca.cert.pem
echo
echo ------------------------------------------------------
echo 'Issuing CA:'
$OPENSSL x509 -noout -text -in certs/issuing.cert.pem
# Check the chain
echo
echo ------------------------------------------------------
echo 'Is the chain valid?'
$OPENSSL verify -CAfile ../rootca/certs/ca.cert.pem certs/issuing.cert.pem