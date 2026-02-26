#!/usr/bin/env python3
# (c) Martin Erzberger 2025-2026
# Wraps shared variables, reading the values from a config file

class Variables:
    import os
    import yaml

    # Load defaults from file
    if os.path.exists('defaults.yaml'):
        with open('defaults.yaml', 'r') as f:
            defaults = yaml.full_load(f)
    else:
         print("Make a copy of defaults_example.yaml to defaults.yaml and adapt the file to your needs!")
         with open('defaults_example.yaml', 'r') as f:
            defaults = yaml.full_load(f)       
    
    # Generic variables
    opensslpath = defaults.get('opensslpath') # Path to OpenSSL
    domain = defaults.get('domain') # Name of the domain for which the certificates are issued
    domains = defaults.get('domains', [domain])  # fallback keeps backward compat
    domainalias=defaults.get('domainalias') # Reverse version of the domain, used to name certain elements
    zipfilename=defaults.get('zipfilename')
    rootcaname=defaults.get('rootcaname')
    issuingcaname=defaults.get('issuingcaname')

    # Variables used to install certificates
    dockerhost=defaults.get('dockerhost') # The machine in my homelab that provides Intel based docker services
    dockerpihost=defaults.get('dockerpihost') # The Raspberry Pi in my homelab that provides ARM based docker services
    dockerdir=defaults.get('dockerdir')

    # Project root path, calculated
    projectroot=os.path.dirname(os.path.abspath(__file__)) # Project root path

    # Properties of the certificates
    cert_properties={}
    # The yaml parser creates a list of dicts with one entry per dict. Convert into a proper dict.
    for entry in defaults.get('certproperties'):
       cert_properties.update(entry)
    country = cert_properties.get('country')
    state = cert_properties.get('state')
    city = cert_properties.get('city')
    org = cert_properties.get('org')
    orgunit = cert_properties.get('orgunit')
    email = cert_properties.get('email')

