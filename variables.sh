#!/bin/sh
# (c) Martin Erzberger 2025
# Edit this file to setup everything the way you like it

# Full path to the openssl executable
OPENSSL=/opt/homebrew/bin/openssl

# The domain name of your intranet
DOMAIN=home.erzi.ch
DOMAIN2=erzi.synology.me
DOMAIN3=services.erzi.ch
DOMAINALIAS=ch.erzi.home

# Hosts to be used in the 'installcerts.sh'-script
DOCKERHOST=docker  # The machine in my homelab that provides Intel based docker services
DOCKERPIHOST=dockerpi  # The Raspberry Pi in my homelab that provides ARM based docker services
DOCKERDIR=/home/me/Docker/erzi-home

# Project root path
export PROJECTROOT=~/Development/public/home-ca

# Properties of the certificates
export COUNTRY=CH
export STATE=ZH
export CITY=Zurich
export ORG=Private
export ORGUNIT=Private
export EMAIL=martin@erzberger.ch
export ROOTCANAME='Erzberger Root CA'
export ISSUINGCANAME='Erzberger Issuing CA'