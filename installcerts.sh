#!/bin/bash
# (c) Martin Erzberger 2024
# Install the various certificates to their target servers / locations
#
# This file is highly specific to my home lab! Use it as an example for your own
# servers and services that you need to provide with certificates.
#

# Import the variables and change into CA directory
DIR="$( cd "$( dirname "$0" )" >/dev/null 2>&1 && pwd )"
cd $DIR
source ./variables.sh

# Preparatipn phase: Import the variables and change into CA directory
DIR="$( cd "$( dirname "$0" )" >/dev/null 2>&1 && pwd )"
cd $DIR
source ./variables.sh

# FQDN of docker host
DOCKERHOSTFQDN=$DOCKERHOST.$DOMAIN

# Copy server wildcard certificate and its private key to the docker host
ssh $DOCKERHOSTFQDN "rm -rf $DOCKERDIR/certs"
ssh $DOCKERHOSTFQDN "mkdir -p $DOCKERDIR/certs"
scp issuingca/certs/$DOMAIN.cert.pem $DOCKERHOSTFQDN:$DOCKERDIR/certs/$DOMAIN.cert
scp issuingca/private/$DOMAIN.key.open.pem $DOCKERHOSTFQDN:$DOCKERDIR/certs/$DOMAIN.key
ssh $DOCKERHOSTFQDN "chmod 444 $DOCKERDIR/certs/$DOMAIN.cert"
ssh $DOCKERHOSTFQDN "chmod 400 $DOCKERDIR/certs/$DOMAIN.key"

# Copy server certificates and their private keys to the docker host for ARM services
# To do, no certs so far.

# Adds home CA root certificate to the Java keystore
$JAVA_HOME/bin/keytool -delete -alias $DOMAINALIAS -cacerts -storepass changeit -v
$JAVA_HOME/bin/keytool -importcert -alias $DOMAINALIAS -trustcacerts -noprompt -cacerts -storepass changeit -file rootca/certs/ca.cert.pem -v

# Copy certificates to the Proxmox server
# To do; For now do this via GUI
