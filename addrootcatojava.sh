#!/bin/bash
# (c) Martin Erzberger 2024
# Adds the required key / certificate to the Java certstore

# Import the variables and change into CA directory
DIR="$( cd "$( dirname "$0" )" >/dev/null 2>&1 && pwd )"
cd $DIR
source ./variables.sh

$JAVA_HOME/bin/keytool -importcert -alias homeca -trustcacerts -noprompt -cacerts -storepass changeit -file rootca/certs/ca.cert.pem -v