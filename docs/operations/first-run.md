# LabGoblin first-run setup

## Install target

A dedicated Debian or Ubuntu VM is recommended. Start with 2 vCPU, 4 GiB RAM, 30 GiB storage, a static address, DNS, and outbound access to GitHub and container registries. Direct installation on a Proxmox host is development-only because Docker can change host networking and firewall behavior.

## Public repository installation

```bash
curl -fsSL https://raw.githubusercontent.com/wagnerks1990/labgoblin/main/deploy/install.sh | sudo sh
```

To install directly on a Proxmox host, download the installer and explicitly pass `--allow-proxmox-host`. Do not use this override on a host you cannot rebuild.

The installer creates `/opt/labgoblin/app`, stores runtime state under `/var/lib/labgoblin`, creates the `labgoblin-updater` service/group, generates independent database, JWT, encryption, updater, and bootstrap secrets, starts the Compose services, runs migrations, and waits for `/api/ready`.

## Create the first administrator

Use an administrator email and password; no separate username is required in the
browser. The email is the sign-in and password-recovery identifier. Existing
installer/API clients may still provide a legacy username.

At completion, the installer prints the application URL and a random bootstrap token. Open the URL, enter that token, and create the first administrator. Enrollment is refused after an active administrator exists. The bootstrap token is never put in a URL.

After successful enrollment, remove `BOOTSTRAP_ADMIN_TOKEN` from the protected `.env` file and recreate the API. The token is optional after enrollment; when the variable is absent, the bootstrap endpoint fails closed:

```bash
cd /opt/labgoblin/app
sudo docker compose --env-file .env up -d --force-recreate api
```

Keep `.env` mode `0600`. Back it up separately from PostgreSQL; losing `CONFIG_ENCRYPTION_KEY` makes encrypted Proxmox credentials unrecoverable.

The development installer serves HTTP and sets `AUTH_COOKIE_SECURE=false`. Put
the appliance behind trusted HTTPS and set it to `true` before any real student
pilot. Configure `CORS_ALLOWED_ORIGINS` only when a separate trusted frontend
origin is required; wildcard credentialed CORS is not supported.

## Private repository deploy key

If the repository becomes private, create a dedicated read-only SSH key on the deployment host, add its public half under **Repository settings → Deploy keys**, leave **Allow write access** disabled, and pin the repository URL to its SSH form. Never reuse a personal key or add a GitHub token to `.env`.

## Required post-install checks

1. Sign in with the new administrator and confirm LabGoblin branding.
2. Configure and validate the Proxmox VE cluster using a least-privilege API token.
3. Import one approved template and confirm node/storage/network readiness.
4. Create a test class, lab, run, assignment, and VM.
5. Verify console access, VM power actions, run expiration, and cleanup.
6. Run an update check without applying it.
7. Create and restore a test backup before relying on rollback.
