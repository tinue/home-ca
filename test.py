#!/usr/bin/env python3
# (c) Martin Erzberger 2025
# Temp script to test stuff

# This part needs to be duplicated in each script
def setup():
  global variables
  from common import setup
  variables = setup()

def test():
  import os
  import common
  import openssl

  print("Content of project root directory:")
  common.print_list(os.listdir(variables.projectroot))
  print("\nOpenssl Version: " + openssl.version())
  print("Domain: " + variables.domain)

if __name__ == "__main__":
  setup()
  test()