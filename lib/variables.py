#!/usr/bin/env python3
# (c) Martin Erzberger 2025-2026
# Wraps shared variables, reading the values from a config file

import os
import yaml

from .common import DEFAULTS_PATH, HomeCAError


class Variables:
    def __init__(self):
        if not os.path.exists(DEFAULTS_PATH):
            raise HomeCAError(f"{DEFAULTS_PATH} not found. Run uv run initca.py to create it.")

        with open(DEFAULTS_PATH, 'r') as f:
            defaults = yaml.full_load(f)

        # Generic variables
        self.opensslpath   = defaults.get('opensslpath')
        self.domains       = defaults.get('domains', [])
        self.domain        = self.domains[0] if self.domains else None
        self.domainalias   = defaults.get('domainalias')
        self.zipfilename   = defaults.get('zipfilename')
        self.rootcaname    = defaults.get('rootcaname')
        self.issuingcaname = defaults.get('issuingcaname')

        # Variables used to install certificates
        self.dockerhost = defaults.get('dockerhost')
        self.dockerdir  = defaults.get('dockerdir')

        # 1Password vault holding one Password item per private key
        self.onepassword_vault = (defaults.get('onepassword') or {}).get('vault')

        # Synology DSM certificate deployment (optional)
        self.synology = defaults.get('synology') or {}

        # Proxmox VE certificate deployment (optional)
        self.proxmox = defaults.get('proxmox') or {}

        # UniFi OS console certificate deployment (optional)
        self.unifi = defaults.get('unifi') or {}

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
