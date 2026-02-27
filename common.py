#!/usr/bin/env python3
# (c) Martin Erzberger 2025-2026
# Functions used in more than one script

# Helper to setup common stuff, such as variables
def setup():
  import os
  import yaml
  from variables import Variables
  
  my_vars = Variables()
  os.environ["COUNTRY"] = my_vars.country
  os.environ["STATE"] = my_vars.state
  os.environ["CITY"] = my_vars.city
  os.environ["ORG"] = my_vars.org
  os.environ["ORGUNIT"] = my_vars.orgunit
  os.environ["ROOTCANAME"] = my_vars.rootcaname
  os.environ["ISSUINGCANAME"] = my_vars.issuingcaname
  os.environ["EMAIL"] = my_vars.email

  return my_vars

# Helper to pretty print a list
def print_list(list_to_print):
  sorted_list = sorted(list_to_print)
  for entry in sorted_list:
    print(entry)