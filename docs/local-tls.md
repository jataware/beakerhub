# Local TLS for Development

Local BeakerHub runs over HTTPS on `beakerhub.internal` and serves spawned
notebook sessions on subdomains (`*.beakerhub.internal`). Those sessions connect
back over secure WebSockets (`wss://`) and are embedded in an iframe, so your
browser must **trust** the TLS certificate — not just let you click past a
warning.

This is why a plain self-signed certificate is not enough: a browser lets you
click through an "untrusted certificate" warning for a page you navigate to
directly, but it **silently blocks** untrusted certificates on WebSocket and
iframe connections, with no prompt to accept them. Since notebook subdomains are
created on the fly, there is no page to visit and accept first — the connection
just fails.

The fix is a local **Certificate Authority (CA)**. You install the CA once; the
browser then trusts every certificate the CA signs, including all
`*.beakerhub.internal` subdomains, with no per-host steps.

There are two ways to get one.

## Option A: mkcert (fully automatic, recommended)

[mkcert](https://github.com/FiloSottile/mkcert) creates a local CA, installs it
into your system and browser trust stores for you, and issues the certificate.
Nothing to import by hand.

Install mkcert and its browser trust-store dependency before running
`make dev-setup`. On Linux, mkcert uses the NSS `certutil` command. Install the
package for your distribution:

```bash
# Debian or Ubuntu
sudo apt install libnss3-tools

# Fedora or RHEL
sudo dnf install nss-tools

# Arch Linux
sudo pacman -S nss

# macOS (installs mkcert and NSS)
brew install mkcert nss
```

Install mkcert itself through your package manager or from its release page,
then create and trust the CA before creating the cluster:

```bash
mkcert -install

make -C helm install-certs
```

`make dev-setup` also runs the local installation path, which creates the
certificate when mkcert is on your `PATH`. If it is, you can stop reading here.

## Option B: openssl + manual CA import (no mkcert)

If you would rather not install mkcert, generate the CA and certificate with
openssl and import the CA into your browser yourself. You only import it once.
Run this before `make dev-setup`; the setup will install the generated
certificate in the cluster.

```bash
make -C helm openssl-certs
```

This creates:

| File | Purpose |
|------|---------|
| `helm/kind/certs.d/rootCA.pem` | The CA certificate — **this is the file you import.** |
| `helm/kind/certs.d/rootCA-key.pem` | The CA private key — stays on your machine, never shared. |
| `helm/kind/certs.d/tls.crt` / `tls.key` | The server (leaf) certificate, signed by the CA and loaded into the cluster. |

The command prints the absolute path to `rootCA.pem` when it finishes. Import
that file using the instructions for your browser/OS below.

### Firefox (any OS)

Firefox uses its own trust store on every platform.

1. `Settings` → `Privacy & Security` → scroll to `Certificates` → `View
   Certificates…`
2. `Authorities` tab → `Import…`
3. Select `rootCA.pem`.
4. Check **"Trust this CA to identify websites."** → `OK`.

### Chrome / Edge / Chromium on Linux

These use their own NSS store on Linux (not the system store).

1. `Settings` → `Privacy and security` → `Security` → `Manage certificates`.
2. `Authorities` tab → `Import`.
3. Select `rootCA.pem`.
4. Check **"Trust this certificate for identifying websites."** → `OK`.

### Chrome / Edge / Safari on macOS

These trust the system Keychain.

1. Open **Keychain Access**, select the **login** (or **System**) keychain.
2. `File` → `Import Items…` → select `rootCA.pem`.
3. Double-click the imported **"BeakerHub Local Dev CA"** entry → expand
   **Trust** → set **"When using this certificate"** to **Always Trust** → close
   (you will be asked for your password).

Command-line equivalent:

```bash
sudo security add-trusted-cert -d -r trustRoot \
  -k /Library/Keychains/System.keychain helm/kind/certs.d/rootCA.pem
```

### Chrome / Edge on Windows

These trust the Windows certificate store.

1. Double-click `rootCA.pem` → `Install Certificate…`.
2. Choose **Current User** → **Place all certificates in the following store** →
   **Trusted Root Certification Authorities** → `Finish`.

> Restart the browser after importing so it picks up the new trust anchor.

## Notes and caveats

- **Import once.** The CA is valid for 10 years and is reused to sign new
  certificates, so a single import covers subdomains, re-issued certs, and
  cluster recreations. "Once" is per trust store you use — e.g. a Firefox user
  imports into Firefox; a Chrome-on-macOS user imports into the Keychain.
- **Regenerating the CA.** `make openssl-certs` reuses the existing CA if one is
  present. If you delete `rootCA.pem`/`rootCA-key.pem`, a new CA is created and
  you must re-import it. The top-level `make full-clean` deletes these local CA
  files; `make clean` keeps them.
- **Subdomain depth.** The certificate covers `beakerhub.internal` and one level
  of subdomain (`*.beakerhub.internal`). That matches how notebook sessions are
  named; deeper names like `a.b.beakerhub.internal` are not covered.
- **Security.** The CA private key (`rootCA-key.pem`) can sign a certificate for
  *any* website on machines that trust it. Keep it local, never commit or share
  it, and remove the CA from your trust store (and delete the key) when you are
  done developing. The generated cert/key files are git-ignored.
