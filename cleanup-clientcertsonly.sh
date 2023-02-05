#!/bin/bash
shopt -s extglob

# (c) Martin Erzberger 2019
# Cleanup all of the client certificates, but keep root / issuing CA intact.

# Change into CA directory
DIR="$( cd "$( dirname "$0" )" >/dev/null 2>&1 && pwd )"
cd "$DIR" || exit 1

read -p "This will delete all client certificates! Are you sure? " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]
then
  source ./variables.sh
  # Cleanup client certificates
  cd "$PROJECTROOT"/issuingca
  cd certs
  rm -fv !(issuing.cert.pem)
  cd ../csr
  rm -fv !(issuing.csr.pem)
  cd ../newcerts
  rm -fv *
  cd ../private
  rm -fv !(issuing.key.pem)
  cd ..
  rm -fv index.txt* serial crlnumber
  # Recreate certificate database
  touch index.txt
  echo 1000 > serial
  echo 1000 > crlnumber
  exit 0
fi
echo "Aborted"
exit 1