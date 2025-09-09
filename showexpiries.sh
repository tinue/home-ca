#!/bin/bash
# (c) Martin Erzberger 2023
# Show the expiry date of all certificates found in the respecting directories

# exit when any command fails
set -e

# Import the variables and change into CA directory
DIR="$( cd "$( dirname "$0" )" >/dev/null 2>&1 && pwd )"
cd $DIR
source ./variables.sh

# Generated certs
for file in issuingca/certs/*
do
# Dump the validity
  printf '%-35s' "${file##*/}"
  $OPENSSL x509 -noout -text -in $file | grep "Not After :" | cut -c24-
done

