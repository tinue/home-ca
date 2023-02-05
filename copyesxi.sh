#!/bin/bash
# (c) Martin Erzberger 2019
# Copies the required key / certificate to an ESXi instance

# Import the variables and change into CA directory
DIR="$( cd "$( dirname "$0" )" >/dev/null 2>&1 && pwd )"
cd $DIR
source ./variables.sh

# Check if an argument has been provided
if [ $# -eq 0 ]
  then
    echo "The name of the certificate must be supplied (without domain), e.g. 'www'."
    exit 1
fi

# Read-in the password for the server key
read -sp 'Server private key password: ' SERVERKEYPWD
echo ''
export SERVERKEYPWD

# Decrypt the key for copy to the server. Delete the decrypted version after copying.
cd issuingca
$OPENSSL rsa -in private/$1.$DOMAIN.key.pem -passin env:SERVERKEYPWD -out private/$1.$DOMAIN.key.open.pem
# Copy the certificates over
scp private/$1.$DOMAIN.key.open.pem root@$1.$DOMAIN:/etc/vmware/ssl/rui.key
scp certs/$1.$DOMAIN.cert.pem root@$1.$DOMAIN:/etc/vmware/ssl/rui.crt
# Delete the unprotected key
rm private/$1.$DOMAIN.key.open.pem
