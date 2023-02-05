#!/bin/sh
# (c) Martin Erzberger 2019
# Test script for various purposes

# Import the variables and change into CA directory
DIR="$( cd "$( dirname "$0" )" >/dev/null 2>&1 && pwd )"
cd $DIR
source ./variables.sh

echo 'Openssl version:' $($OPENSSL version)
echo Domain: $DOMAIN
echo 'Project directory contents' $(ls $PROJECTROOT)

