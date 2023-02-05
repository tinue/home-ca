#!/bin/sh
# (c) Martin Erzberger 2019
# Copy examples and delete existing stuff

# Change into CA directory
DIR="$( cd "$( dirname "$0" )" >/dev/null 2>&1 && pwd )"
cd $DIR

read -p "This will your customizations (file variables.sh)! Are you sure? " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]
then
  cp variables.sh.example variables.sh
  "${VISUAL:-vi}" variables.sh
  echo 'Recommended: Run cleanup.sh now'
  exit 0
fi
echo Aborted
exit 1