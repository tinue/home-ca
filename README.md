# Certification Authority for home use

For some use cases, self-signed SSL certificates are necessary. If you don't know why you need
such certificates, you most probably don't — consider [Let's Encrypt](https://letsencrypt.org)
instead.

If you know what you are doing, this collection of scripts and configuration files helps in
operating a small home-use certification authority: a Root CA, an Issuing CA signed by it, and
server certificates signed by the Issuing CA. All private key passwords live in 1Password;
unencrypted private keys are never written to disk.

# Requirements

**OpenSSL 3.x** is required. On macOS, install via Homebrew (`brew install openssl`) and set
the path in `lib/defaults.yaml` (see below). The scripts run on macOS and should work on any
Linux system. Not tested on Windows, but should work in WSL.

**Python 3.15** or newer is required; uv (see below) downloads it automatically if it is not
installed. The only third-party dependency is [PyYAML](https://pypi.org/project/PyYAML/).

**1Password CLI** (`op`, `brew install 1password-cli`) holds the passwords of all private keys.
Enable *Integrate with 1Password CLI* in the 1Password app, so `op` unlocks with Touch ID. The
configured vault contains one *Password* item per key, titled after it:

| Item | Protects | Created by |
|---|---|---|
| `root-ca` | `rootca/private/ca.key.pem` | you, after `initca.py` |
| `issuing-ca` | `issuingca/private/issuing.key.pem`; also holds the backup ZIP as attachment | you, after `initca.py` |
| `<cert name>`, e.g. `home.example.com` | `issuingca/private/<cert name>.key.pem` | `gencert.py` |

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
(or simply run `uv run initca.py`, which does this for you). The example file comments every
setting:

| Setting | Purpose |
|---|---|
| `opensslpath` | Path to the OpenSSL 3 binary |
| `domains` | Domains you issue certificates for. The first one is the default for `-d` and is used by the `docker` deployment |
| `certproperties`, `rootcaname`, `issuingcaname` | Subject fields and names of the CA certificates |
| `zipfilename` | Name of the backup ZIP |
| `onepassword.vault` | 1Password vault holding the key passwords |
| `dockerhost`, `dockerdir` | Target of `installcerts.py docker` (optional) |
| `domainalias` | Alias of the Root CA in the Java truststore, `installcerts.py java` (optional) |
| `synology`, `proxmox`, `unifi` | Targets of the corresponding `installcerts.py` deployments (optional) |

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

`initca.py` asks for the Root CA and Issuing CA passwords (each twice for confirmation). Choose
strong passwords and store them in 1Password as the Password items `root-ca` and `issuing-ca` —
`gencert.py` and `backup.py` need them. Afterwards, the following files exist:

| File | Description |
|---|---|
| `rootca/certs/ca.cert.pem` | Root CA certificate, valid 20 years. Import this into your devices and browsers |
| `rootca/private/ca.key.pem` | Root CA private key (encrypted) |
| `issuingca/certs/issuing.cert.pem` | Issuing CA certificate, valid 10 years |
| `issuingca/private/issuing.key.pem` | Issuing CA private key (encrypted) |

Once the 1Password items exist, run `uv run backup.py`.

# Issuing and renewing server certificates

```
uv run gencert.py NAME [-s SAN]... [-m] [--force]
```

`NAME` is a configured domain (or `*.domain`) for a wildcard certificate (SANs `*.domain` and
`domain`), or `host.domain` for a single host. The script decides what to do:

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

The certificate file contains the Issuing CA certificate as well, so clients only need to trust
the Root CA. Certificates are issued with a **200-day validity**, the maximum the CA/Browser
Forum permits since March 2026. Use `uv run showexpiries.py` to see which certificates are due.

After each run a backup is written (see [Backup and restore](#backup-and-restore)). Deploy the
certificate with `uv run installcerts.py`.

### Examples

```sh
uv run gencert.py home.example.com                      # wildcard *.home.example.com
uv run gencert.py myserver.home.example.com             # single host
uv run gencert.py myserver.home.example.com -s myserver.local -s localhost
uv run gencert.py myserver.home.example.com -m          # + all other configured domains
```

# Deploying certificates

```
uv run installcerts.py TARGET...      # TARGET: docker, java, synology, proxmox, unifi, or all
```

An error in one target is reported and the others still run; with several targets, a summary
lists each target's result. Private keys are decrypted in memory with the password from
1Password and transferred directly; no unencrypted key file is written locally. The targets are
**specific to one home lab**: configure the ones you use and treat the script as a template for
others. For systems no target covers, `uv run decryptkey.py` prints a key for manual import.

### Docker host

`installcerts.py docker` copies the wildcard certificate of the first configured domain over
ssh to `<dockerhost>.<domain>`, into `<dockerdir>/certs/` as `<domain>.cert` and `<domain>.key`.
The directory is replaced on every run.

### Java truststore

`installcerts.py java` imports the Root CA certificate into the truststore (`cacerts`) of the JDK
in `$JAVA_HOME`, under the alias `domainalias`, replacing an earlier entry. Without
`JAVA_HOME`, the target is skipped. Run it again after a JDK upgrade.

### Synology DSM

`installcerts.py synology` replaces certificates in DSM 7 through its Web API (the same calls as
the acme.sh `synology_dsm` hook). Each certificate listed under `synology.certificates` replaces
the DSM certificate with the same CN, keeping its description, default flag and service
assignments; import it once in the DSM GUI first. `uv run installcerts.py --list-synology`
lists the certificates installed in DSM and the services using them.

The DSM login comes from the 1Password item in `synology.login` (username, password, and the
one-time password if 2FA is enabled). DSM is only trusted if its current certificate chains to
your Root CA (its expiry is not checked).

### Proxmox VE

`installcerts.py proxmox` installs the certificate in `proxmox.certificate` as the custom
`pveproxy` certificate (web UI and API, port 8006) on each node listed under `proxmox.nodes`.
The node entries are ssh destinations: root login without a password, with user and hostname
optionally taken from `~/.ssh/config`. For each node the key and certificate are copied to a
private temporary directory, installed with `pvenode cert set … --force 1 --restart 1` (the
supported way, which writes `/etc/pve/nodes/<node>/pveproxy-ssl.{pem,key}`), and then deleted.
Afterwards the script checks that the node's FQDN serves the new certificate, trusted via your
Root CA. The cluster-internal `pve-ssl.*` certificates are not touched.

### UniFi OS

`installcerts.py unifi` installs the certificate in `unifi.certificate` as the console certificate
of a UniFi OS console (UniFi OS 4.1 or newer, e.g. a UCG, UDM or Cloud Key) through the API the web
UI uses (Settings > Control Plane > Console > Certificates; undocumented by Ubiquiti, checked on
UniFi OS 5.1). It uploads the certificate with its chain, activates it, and deletes the previously
active certificate if it was an uploaded one with the same CN. A certificate that is already
uploaded is only activated.

The login comes from the 1Password item in `unifi.login`: a **local** console account (username,
password, and the one-time password if 2FA is enabled); UI.com SSO accounts cannot log in
locally. The console is only trusted if its current certificate chains to your Root CA, and
afterwards the script checks that it serves the new certificate.

# Backup and restore

| Command | Description |
|---|---|
| `uv run backup.py [FILE]` | Creates a compressed ZIP of all keys, certificates, CA database files (`serial`, `index.txt`, …) and `lib/defaults.yaml`. The previous ZIP is kept as `FILE.previous`, and the new one is attached to the 1Password item `issuing-ca`, replacing the previous attachment. FILE defaults to `zipfilename` |
| `uv run backup.py --restore [FILE]` | Restores from a ZIP backup and resets file permissions |
| `uv run backup.py --restore --from-1password [--vault VAULT] [FILE]` | Restores from the backup attached to `issuing-ca` |

The keys in the backup are encrypted; their passwords are in 1Password, not in the ZIP.
To set up the CA on a new machine, install the requirements, then restore from 1Password. Without
`lib/defaults.yaml`, give the vault and the attachment name; the restore brings the configuration
back as well:

```sh
uv run backup.py --restore --from-1password --vault "Home CA" certbackup.zip
```

# Utilities

| Command | Description |
|---|---|
| `uv run showexpiries.py` | Lists the expiry dates of all certificates; on a terminal, expired ones are red and those expiring within 60 days yellow |
| `uv run dumpcertificate.py [-d DOMAIN] [-H HOST]` | Shows CN, SANs, expiry, key usage and extended key usage of a certificate |
| `uv run decryptkey.py [-d DOMAIN] [-H HOST]` | Prints a certificate's decrypted private key to stdout, for manual imports, e.g. `uv run decryptkey.py -H nas \| pbcopy`. No file is written |
| `uv run cleanup.py` | Removes all issued certificates and keys while keeping the CA intact; useful when changing domain names |
| `uv run cleanup.py --full` | **Destructive**: deletes everything including CA keys, certificates, and database files (`serial`, `crlnumber`, `index.txt`); re-run `uv run initca.py` afterwards |
| `uv run cleanup.py --clobber` | **Destructive**: like `--full`, but also deletes `lib/defaults.yaml`; re-run `uv run initca.py` to recreate it from the example file |

`-d` defaults to the first configured domain, `-H` to `*` (the wildcard certificate); so
`-H nas` means `nas.<first domain>`.

`cleanup.py` does not touch 1Password. A certificate created again under the same name reuses
its existing item; after `--full`, update the `root-ca` and `issuing-ca` items with the new
passwords you choose in `initca.py`.

# Limitations

- Only certificates for keys generated here can be issued; signing a third-party CSR is not
  supported.
- No certificate revocation lists are published.

# References

- [OpenSSL Certificate Authority](https://jamielinux.com/docs/openssl-certificate-authority/introduction.html)
