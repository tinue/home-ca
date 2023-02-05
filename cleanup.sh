#!/bin/sh
# (c) Martin Erzberger 2019
# Cleanup everything (use with care!)

# Change into CA directory
DIR="$( cd "$( dirname "$0" )" >/dev/null 2>&1 && pwd )"
cd $DIR

read -p "This will delete all certificates, including CA and Issuing CA! Are you sure? " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]
then
  source ./variables.sh
  # Cleanup Root CA
  cd $PROJECTROOT/rootca
  rm -rf certs crl newcerts private
  rm -f index.txt* serial
  # Recreate directories
  mkdir certs crl newcerts private
  chmod 700 private
  touch index.txt
  echo 1000 > serial
  # Cleanup Issuing CA
  cd $PROJECTROOT/issuingca
  rm -rf certs crl csr newcerts private
  rm -f index.txt* serial crlnumber
  # Recreate directories
  mkdir certs crl csr newcerts private
  chmod 700 private
  touch index.txt
  echo 1000 > serial
  echo 1000 > crlnumber
  exit 0
fi
echo "Aborted"
exit 1