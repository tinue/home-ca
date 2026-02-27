#!/usr/bin/env python3
# (c) Martin Erzberger 2025-2026
# Wraps shared variables, reading the values from a config file

import os
import sys
import yaml

_LIB_DIR      = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_LIB_DIR)


class Variables:
    def __init__(self):
        defaults_path = os.path.join(_LIB_DIR, 'defaults.yaml')

        if not os.path.exists(defaults_path):
            sys.exit(f"{defaults_path} not found. Run python initca.py to create it.")

        with open(defaults_path, 'r') as f:
            defaults = yaml.full_load(f)

        # Project root path
        self.projectroot = _PROJECT_ROOT

        # Generic variables
        self.opensslpath   = defaults.get('opensslpath')
        self.domains       = defaults.get('domains', [])
        self.domain        = self.domains[0] if self.domains else None
        self.domainalias   = defaults.get('domainalias')
        self.zipfilename   = defaults.get('zipfilename')
        self.rootcaname    = defaults.get('rootcaname')
        self.issuingcaname = defaults.get('issuingcaname')

        # Variables used to install certificates
        self.dockerhost   = defaults.get('dockerhost')
        self.dockerpihost = defaults.get('dockerpihost')
        self.dockerdir    = defaults.get('dockerdir')

        # Properties of the certificates
        cert_properties = {}
        for entry in defaults.get('certproperties'):
            cert_properties.update(entry)
        self.country = cert_properties.get('country')
        self.state   = cert_properties.get('state')
        self.city    = cert_properties.get('city')
        self.org     = cert_properties.get('org')
        self.orgunit = cert_properties.get('orgunit')
        self.email   = cert_properties.get('email')
