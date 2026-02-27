# Certification Authority for home use

For some use cases, self-signed SSL certificates are necessary. If you don't know why you need
such certificates, you most probably don't — consider [Let's Encrypt](https://letsencrypt.org)
instead.

If you know what you are doing, this collection of scripts and configuration files helps in
operating a small home-use certification authority.

# Preconditions

**OpenSSL 3.x** is required. On macOS, install via Homebrew (`brew install openssl`) and set
the path in `lib/defaults.yaml` (see below). The scripts were developed on macOS but should
work on any Linux system. Not tested on Windows, but should work in WSL.

**Python 3.x** is required for the Python scripts. The only third-party dependency is
[PyYAML](https://pypi.org/project/PyYAML/). All other imports (`argparse`, `getpass`, `os`,
`shutil`, `subprocess`, `zipfile`, …) are part of the Python standard library.

# Setting up the Python environment

## Option A — pip + venv

```sh
python3 -m venv .venv
source .venv/bin/activate      # macOS / Linux
# .venv\Scripts\activate       # Windows / WSL cmd

pip install -r requirements.txt
```

## Option B — uv

[uv](https://docs.astral.sh/uv/) is a fast Python package and project manager.
Install it once if not already present:

```sh
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then set up the environment:

```sh
uv venv                                 # creates .venv/
source .venv/bin/activate               # macOS / Linux
uv pip install -r requirements.txt
```

Alternatively, skip the explicit activation and prefix every command with `uv run`:

```sh
uv run python gencert.py
uv run python backup.py
```

# Configuration

`lib/defaults.yaml` controls all scripts. It is gitignored and must never be committed.
Copy `lib/defaults_example.yaml` to `lib/defaults.yaml` and edit it to match your environment
(or simply run `python initca.py`, which does this automatically).

# One-time setup

```sh
python initca.py
```

Run this command once, and again after editing the configuration:

1. **First run** — if `lib/defaults.yaml` does not yet exist, it is copied from `lib/defaults_example.yaml`
   and opened in your editor (`$VISUAL` / `$EDITOR` / vi). The script then exits so you can
   finish editing (necessary for GUI editors that return immediately).
2. **Second run** — once `lib/defaults.yaml` is in place, the CA directory structure is created
   and Root CA and Issuing CA keys and certificates are generated.

Steps that have already been completed are skipped safely — the script can be re-run without
overwriting existing keys.

Passwords for the Root CA and Issuing CA private keys are each asked twice for confirmation.
Use a password manager to generate and store them. After finishing, the following files exist:

| File | Description |
|---|---|
| `rootca/certs/ca.cert.pem` | Root CA certificate (import this into your devices/browsers) |
| `rootca/private/ca.key.pem` | Root CA private key — keep offline and secure |
| `issuingca/certs/issuing.cert.pem` | Issuing CA certificate |
| `issuingca/private/issuing.key.pem` | Issuing CA private key |

This is a good time to run `python backup.py`.

# Issuing and renewing server certificates

All certificate operations are handled by a single script:

```
python gencert.py [-d DOMAIN] [-H HOST] [-s SAN] [-m]
```

| Option | Description |
|---|---|
| `-d DOMAIN` | Domain to issue cert for (default: first entry in the `domains` list). Choices are validated against that list. |
| `-H HOST` | Hostname, or `*` for wildcard (default: `*`) |
| `-s SAN` | Extra SAN entry, repeatable |
| `-m` | Multi-domain: add all other configured domains as additional SANs |

The script auto-detects whether a certificate already exists and switches between **create** and
**renew** automatically. Renewal reuses the existing private key.

Certificates are issued with a **200-day validity** (the maximum permitted by the CA/Browser
Forum, effective 2026). Plan to renew every ~6 months. Use `python showexpiries.py` to monitor
expiry dates across all issued certificates.

After each run, an unencrypted private key is written to
`issuingca/private/<name>.key.open.pem` for deployment.
**Delete this file immediately after importing it to the target system.**

### Cert modes

| Mode | Command | CN | SANs |
|---|---|---|---|
| Wildcard | `python gencert.py` | `*.domain` | `*.domain`, `domain` |
| Single host | `python gencert.py -H myserver` | `myserver.domain` | `myserver.domain` |
| Extra SANs | `python gencert.py -H myserver -s myserver.local` | `myserver.domain` | `myserver.domain`, `myserver.local` |
| Multi-domain | `python gencert.py -H myserver -m` | `myserver.domain` | `myserver.domain` + all other domains |

### Examples

```sh
# Wildcard cert for the default domain (create or renew)
python gencert.py

# Wildcard cert for a secondary domain
python gencert.py -d dmz.example.com

# Single-host cert
python gencert.py -H myserver

# Single-host cert with additional SANs
python gencert.py -H myserver -s myserver.local -s localhost

# Multi-domain cert covering all configured domains
python gencert.py -H everest -m
```

# Utilities

| Script | Description |
|---|---|
| `python showexpiries.py` | Lists expiry dates of all issued certificates |
| `python dumpcertificate.py [-d DOMAIN] [-H HOST]` | Dumps key fields of an issued certificate: CN, SANs, expiry, key usage, extended key usage |
| `python backup.py [FILE]` | Creates a compressed ZIP of all keys and certificates (excludes unencrypted keys); FILE defaults to the configured backup filename |
| `python backup.py --restore [FILE]` | Restores from a ZIP backup and resets file permissions; FILE defaults to the configured backup filename |
| `python cleanup.py` | Removes all issued certificates and keys while keeping the CA intact; useful when changing domain names |
| `python cleanup.py --full` | **Destructive**: deletes everything including CA keys, certificates, and database files (`serial`, `crlnumber`, `index.txt`); re-run `python initca.py` afterwards |
| `python cleanup.py --clobber` | **Destructive**: like `--full`, but also deletes `lib/defaults.yaml`; re-run `python initca.py` to recreate it from the example file |
| `python decryptkey.py [-d DOMAIN] [-H HOST]` | Re-decrypts a certificate's private key — use if the deployment key was already deleted |
| `python installcerts.py` | Deploys certificates to target servers; **highly specific to your infrastructure**, use as a template |

# References

- [OpenSSL Certificate Authority](https://jamielinux.com/docs/openssl-certificate-authority/introduction.html)

# TODO

- Sign a 3rd-party CSR

# History

- October 2019: Initial version
- January 2022: Certificate renewal
- 2025: Rewrite to Python
- February 2026: Unified `gencert.py` replaces individual cert generation scripts; `initca.py` replaces `generatecacerts.sh` and `init.sh` for the Python workflow; internal information removed from repository
