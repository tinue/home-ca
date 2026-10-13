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

**Python 3.15** or newer is required for the Python scripts; uv (see below) downloads it
automatically if it is not installed. The only third-party dependency is
[PyYAML](https://pypi.org/project/PyYAML/). All other imports (`argparse`, `getpass`, `os`,
`shutil`, `subprocess`, `zipfile`, …) are part of the Python standard library.

**1Password CLI** (`op`, `brew install 1password-cli`) holds the passwords of all private keys.
Enable *Integrate with 1Password CLI* in the 1Password app, so `op` unlocks with Touch ID. The
configured vault contains one *Password* item per key, titled after it:

| Item | Protects |
|---|---|
| `root-ca` | `rootca/private/ca.key.pem` |
| `issuing-ca` | `issuingca/private/issuing.key.pem` |
| `<cert name>`, e.g. `home.example.com` | `issuingca/private/<cert name>.key.pem` |

`gencert.py` creates the items for new certificates itself. `initca.py` still asks for the
Root CA and Issuing CA passwords; store them as `root-ca` and `issuing-ca` afterwards.

# Setting up the Python environment

The project is managed with [uv](https://docs.astral.sh/uv/). Dependencies are declared in
`pyproject.toml` and pinned in `uv.lock`. Install uv once if not already present:

```sh
curl -LsSf https://astral.sh/uv/install.sh | sh   # or: brew install uv
```

Then create the virtual environment and install the dependencies:

```sh
uv sync                                 # installs Python 3.15 and creates .venv/ from uv.lock
```

Run the scripts with `uv run`, which uses `.venv` automatically (and syncs it if needed):

```sh
uv run gencert.py
uv run backup.py
```

The scripts are executable and use `uv run` as their interpreter, so `./gencert.py` works too.
Alternatively, activate the environment (`source .venv/bin/activate`) and use `python` directly.

# Configuration

`lib/defaults.yaml` controls all scripts. It is gitignored and must never be committed.
Copy `lib/defaults_example.yaml` to `lib/defaults.yaml` and edit it to match your environment
(or simply run `uv run initca.py`, which does this automatically).

Besides paths and certificate properties, it sets the 1Password vault (`onepassword.vault`) and,
optionally, the Synology DSM deployment (`synology`, see `installcerts.py`).

# One-time setup

```sh
uv run initca.py
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

This is a good time to run `uv run backup.py`.

# Issuing and renewing server certificates

```
uv run gencert.py NAME [-s SAN]... [-m] [--force]
```

`NAME` is a configured domain (or `*.domain`) for a wildcard certificate, or `host.domain` for a
single host. The script decides what to do:

| Situation | Action |
|---|---|
| No certificate | **Create**: a password is generated in 1Password, then key and certificate |
| Expired, or expires within 60 days | **Renew** with the same key, CN and SANs |
| Valid for more than 60 days | Nothing; prints the expiry date (`--force` renews anyway) |

| Option | Description |
|---|---|
| `-s SAN` | Extra DNS SAN, repeatable. For new certificates, or with `--force` (replaces the SANs) |
| `-m` | Multi-domain: add all other configured domains as SANs. Same restriction as `-s` |
| `--force` | Renew a certificate that is still valid |

The key passwords are read from 1Password and checked against the key files before anything is
changed. The new certificate is signed into a temporary file, verified against the Root CA, and
only then replaces the old one, which is kept as `<name>.cert.pem.backup`. If anything fails,
the existing certificate and key stay untouched; a failed creation can simply be re-run.

Certificates are issued with a **200-day validity** (the maximum permitted by the CA/Browser
Forum, effective 2026). Use `uv run showexpiries.py` to see which certificates are due.

After each run:
- the unencrypted key is in `issuingca/private/<name>.key.open.pem` (mode 600) for deployment.
  **Delete it after installing the certificate.**
- a backup is written (see `backup.py`); the previous backup is kept as `<zip>.previous`.

### Examples

```sh
uv run gencert.py home.example.com                      # wildcard *.home.example.com
uv run gencert.py myserver.home.example.com             # single host
uv run gencert.py myserver.home.example.com -s myserver.local -s localhost
uv run gencert.py myserver.home.example.com -m          # + all other configured domains
```

# Utilities

| Script | Description |
|---|---|
| `uv run showexpiries.py` | Lists expiry dates of all issued certificates |
| `uv run dumpcertificate.py [-d DOMAIN] [-H HOST]` | Dumps key fields of an issued certificate: CN, SANs, expiry, key usage, extended key usage |
| `uv run backup.py [FILE]` | Creates a compressed ZIP of all keys, certificates and CA database files (`serial`, `index.txt`, …; excludes unencrypted keys); keeps the previous ZIP as `FILE.previous`. FILE defaults to the configured backup filename |
| `uv run backup.py --restore [FILE]` | Restores from a ZIP backup and resets file permissions; FILE defaults to the configured backup filename |
| `uv run cleanup.py` | Removes all issued certificates and keys while keeping the CA intact; useful when changing domain names |
| `uv run cleanup.py --full` | **Destructive**: deletes everything including CA keys, certificates, and database files (`serial`, `crlnumber`, `index.txt`); re-run `uv run initca.py` afterwards |
| `uv run cleanup.py --clobber` | **Destructive**: like `--full`, but also deletes `lib/defaults.yaml`; re-run `uv run initca.py` to recreate it from the example file |
| `uv run decryptkey.py [-d DOMAIN] [-H HOST]` | Re-decrypts a certificate's private key (password from 1Password) — use if the deployment key was already deleted |
| `uv run installcerts.py [TARGET...]` | Deploys certificates; targets `docker`, `java`, `synology` (default: all). **Highly specific to your infrastructure**, use as a template |
| `uv run installcerts.py --list-synology` | Lists the certificates installed in Synology DSM and the services using them |

### Synology DSM

`installcerts.py synology` replaces certificates in DSM 7 through its Web API (the same calls as
the acme.sh `synology_dsm` hook). Each certificate listed under `synology.certificates` replaces
the DSM certificate with the same CN, keeping its description, default flag and service
assignments; import it once in the DSM GUI first. The DSM login comes from the 1Password item in
`synology.login` (username, password, and the one-time password if 2FA is enabled). DSM is only
trusted if its current certificate chains to our Root CA (its expiry is not checked).

# References

- [OpenSSL Certificate Authority](https://jamielinux.com/docs/openssl-certificate-authority/introduction.html)

# TODO

- Sign a 3rd-party CSR

# History

- October 2019: Initial version
- January 2022: Certificate renewal
- 2025: Rewrite to Python
- February 2026: Unified `gencert.py` replaces individual cert generation scripts; `initca.py` replaces `generatecacerts.sh` and `init.sh` for the Python workflow; internal information removed from repository
- October 2026: Key passwords in 1Password; `gencert.py NAME` renews or creates automatically; Synology DSM deployment
