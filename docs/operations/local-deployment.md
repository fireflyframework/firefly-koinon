<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
# Start a local koinon environment

This guide prepares a **new local development environment**. It does not adopt or reset an existing installation. The Compose template supplies PostgreSQL 17.11 with pgvector 0.8.7 and Keycloak 26.8.1. The native shared cache uses the primary PostgreSQL datasource. The API and conversation worker run separately on your machine; Angular is optional.

The commands use a POSIX shell on Linux or macOS. On Windows, use a Linux environment such as WSL 2 with Docker integration and keep these paths in that environment. The Compose template was structurally checked; it was not executed during qualification. Equivalent private services were tested separately. See [qualification](qualification.md) for those boundaries.

## 1. Install the backend environment

Start in a checkout of the repository. Install Python 3.13, `uv`, Docker and the Docker Compose plugin, then run:

```sh
uv sync --project backend --python 3.13 --locked
```

This creates `backend/.venv` and installs the backend with its document, structured-data and local-storage dependencies. The SDKs used by a host product do not need this backend environment. Cloud storage is optional; install only the relevant extra when configuring an existing provider, for example `--extra storage-azure`, `--extra storage-gcs` or `--extra storage-s3`. Read [storage configuration](storage.md) before selecting cloud storage.

Check that the local ports are free before continuing:

| Service | Loopback port |
| --- | ---: |
| PostgreSQL | 18783 |
| Keycloak | 18784 |
| API | 18781 |
| Optional management frontend | 18782 |

## 2. Create private configuration and storage

Choose a **new** location outside the repository. The example uses your home directory and does not require writing under `/var/lib` or `/private`:

```sh
umask 077
export KOINON_LOCAL_DIR="$HOME/.local/share/koinon/local-development"
backend/.venv/bin/python deploy/generate_local_configuration.py "$KOINON_LOCAL_DIR/secrets"
export KOINON_SECRETS_DIR="$KOINON_LOCAL_DIR/secrets"
```

The generator refuses an existing secret directory. It creates mode-0600 files in a mode-0700 directory, with separate database credentials, local identity credentials and an encryption master key. Keep this directory: generating another one is not a credential rotation or a recovery procedure.

Create explicit local roots for original documents, structured objects and private chat files:

```sh
backend/.venv/bin/python - <<'PY'
import json
import os
from pathlib import Path

os.umask(0o077)
base = Path(os.environ["KOINON_LOCAL_DIR"])
roots = {name: base / "data" / name for name in ("documents", "structured", "attachments")}
for root in roots.values():
    root.mkdir(mode=0o700, parents=True, exist_ok=False)

configuration = {
    "koinon": {
        "storage": {
            "documents": {"backend": "localfs", "root": str(roots["documents"]), "store_originals": True},
            "structured": {"backend": "local", "root": str(roots["structured"])},
            "attachments": {"backend": "local", "root": str(roots["attachments"])},
        },
        "attachments": {"worker_enabled": True},
    }
}
with (base / "secrets" / "configuration.json").open("x") as target:
    json.dump(configuration, target, indent=2)
    target.write("\n")
PY
```

Select the generated configuration:

```sh
export KOINON_CONFIG_FILE="$KOINON_SECRETS_DIR/configuration.json"
```

The block refuses existing storage roots and configuration. Reuse the saved configuration when restarting; do not rerun initialization over retained data. The same paths and credentials must reach the API and every worker. This profile enables scheduled private-file parsing; it does not configure a model provider or grant anyone access.

## 3. Start infrastructure and migrate

```sh
docker compose -f deploy/compose.yaml up -d --build
docker compose -f deploy/compose.yaml ps
```

Wait for PostgreSQL to become healthy and Keycloak to finish its realm import. You can check the configured local issuer without exposing credentials:

```sh
curl --fail --silent --show-error \
  http://127.0.0.1:18784/realms/koinon/.well-known/openid-configuration > /dev/null
```

Realm import initializes a new realm; it does not update an existing one. The generated environment files use literal `KEY=VALUE` lines, including JSON. Pass them through `deploy/run.py`; do not source them into a shell.

Provision roles, migrate all three histories and check the resulting grants:

```sh
backend/.venv/bin/python deploy/run.py --env-file "$KOINON_SECRETS_DIR/migration.env" -- backend/.venv/bin/python deploy/provision_roles.py
backend/.venv/bin/python deploy/run.py --env-file "$KOINON_SECRETS_DIR/migration.env" -- backend/.venv/bin/python deploy/migrate.py
backend/.venv/bin/python deploy/run.py --env-file "$KOINON_SECRETS_DIR/migration.env" -- backend/.venv/bin/python deploy/provision_roles.py --grant
backend/.venv/bin/python deploy/run.py --env-file "$KOINON_SECRETS_DIR/migration.env" -- backend/.venv/bin/python deploy/migrate.py --check
backend/.venv/bin/python deploy/run.py --env-file "$KOINON_SECRETS_DIR/migration.env" -- backend/.venv/bin/python deploy/provision_roles.py --check
```

Migration authority stays in `migration.env`. API and worker commands below receive only `runtime.env`. Runtime startup validates the schema and does not run migrations. Read [schema and role changes](migrations.md) before upgrading retained data.

## 4. Bootstrap the first administrator

Identity-provider sign-in does not create product membership. For the generated local realm, the fictional `admin` user has the stable subject below:

```sh
backend/.venv/bin/python deploy/run.py --env-file "$KOINON_SECRETS_DIR/runtime.env" -- backend/.venv/bin/python deploy/bootstrap.py --tenant-id north --name "Local knowledge organization" --subject "http://127.0.0.1:18784/realms/koinon|8c85d9a1-6168-4fb0-ae11-1b8a41227a01"
```

This operator command creates only a new organization and its first administrator, records an audit event and refuses an existing organization. For a different identity provider, verify the actual issuer and stable subject before bootstrapping. Use **People & access** for subsequent memberships. The local realm's `admin`, `analyst`, `editor`, `viewer` and `outsider` accounts use generated test credentials; they do not all receive product membership automatically. Do not import these fictional users into production.

For the first local browser sign-in, use username `admin` and the password in your generated `demo_password` file. The separate `keycloak_admin_password` belongs to Keycloak administration, not the application account. Keep both in the private secret directory.

## 5. Run the API and conversation worker

In the first terminal, from the repository root:

```sh
backend/.venv/bin/python deploy/run.py --env-file "$KOINON_SECRETS_DIR/runtime.env" -- backend/.venv/bin/python -m koinon.serve
```

The native PyFly launcher and MCP endpoint use the same `PYFLY_SERVER_HOST` and `PYFLY_SERVER_PORT`. Newly generated local configuration binds `127.0.0.1:18781` and enables MCP at `http://127.0.0.1:18781/mcp`. Existing runtime files are not rewritten. Set these listener variables explicitly when updating an older local configuration.

For a reverse proxy, configure the exact HTTPS endpoint with `KOINON_MCP_PUBLIC_URL`, including `/mcp`. Without that setting, the endpoint follows the configured listener. A wildcard listener is advertised through loopback and labeled local-only. Native HTTPS requires both `pyfly.server.ssl_certfile` and `pyfly.server.ssl_keyfile`. Request `Host` and forwarding headers never determine the announced endpoint. Actual external client access still requires verification.

The fallback port belongs to the listener inside the process. Docker port mappings, container ingress, and public proxies can expose a different address or port. Set `KOINON_MCP_PUBLIC_URL` to that exact external URL ending in `/mcp`. Use HTTPS outside loopback development. A local-only endpoint is a connection hint for the process environment. It does not prove that a browser, container host, or external client can reach it.

Fresh local configuration also enables MCP OAuth and creates a dedicated private `mcp_oauth_key`. Its runtime variables are `KOINON_MCP_OAUTH_ENABLED` and `KOINON_MCP_OAUTH_ENCRYPTION_KEY`. This key is separate from the master key and must be preserved with the other installation secrets. An empty application registry grants no client access. Organization administrators register exact client callbacks and knowledge scope ceilings through the authenticated application administration API.

Existing installations are not rewritten. An operator must provision the MCP OAuth encryption key and enable the endpoint once before OAuth connections become available. The organization readiness response reports missing configuration without returning keys. Administrators cannot change the installation issuer or encryption key. Deployment-supplied static registrations remain read-only; managed application registration does not enable dynamic OAuth client registration.

In a **second terminal**, set the same three path variables and start the worker:

```sh
export KOINON_LOCAL_DIR="$HOME/.local/share/koinon/local-development"
export KOINON_SECRETS_DIR="$KOINON_LOCAL_DIR/secrets"
export KOINON_CONFIG_FILE="$KOINON_SECRETS_DIR/configuration.json"
backend/.venv/bin/python deploy/run.py --env-file "$KOINON_SECRETS_DIR/runtime.env" -- backend/.venv/bin/python -m koinon.assistants.worker
```

The API accepts requests; the independent worker consumes queued conversations. A healthy API without this worker can leave an answer queued. Private attachment parsing additionally needs its enabled setting, storage, database and extraction prerequisites; the configuration above enables its scheduled processing.

Check the API from another terminal:

```sh
curl --fail --silent --show-error http://127.0.0.1:18781/health
curl --fail --silent --show-error http://127.0.0.1:18781/ready
```

`/health` reports process liveness. `/ready` queries the catalog database. Neither proves that a model or cloud provider is ready. Authorized headless clients use `/api/v1/context` and `/api/v1/capabilities`; see the [SDK guides](../guides/headless.md).

## 6. Open the interface and configure knowledge

For optional frontend development, use Node 24 and the repository's npm 11.16.0 toolchain. In a third terminal:

```sh
npm ci --prefix sdk/typescript --ignore-scripts
npm run build --prefix sdk/typescript
npm ci --prefix frontend --ignore-scripts
npm start --prefix frontend
```

The frontend development configuration uses `http://127.0.0.1:18782` and proxies the backend on 18781. Start sign-in at `http://127.0.0.1:18781/oauth2/authorization/koinon`; its exact registered callback is `http://127.0.0.1:18781/login/oauth2/code/koinon`. Browser calls use `/bff/api/v1/**` and session/CSRF protection. Headless calls use `/api/v1/**` and bearer credentials; do not mix the two.

Follow the [visual walkthrough](../guides/interface-tour.md) to create a workspace and destination folder, configure providers and knowledge models, and select the organization chat default. No model is configured automatically. Test one small fictional file using the appropriate [intake mode and limits](../guides/intake-formats.md), then inspect its processing state and source evidence before importing more.

When stopping development, preserve database volumes, all three storage roots, configuration and encryption keys. Stop the foreground API and worker normally; `docker compose -f deploy/compose.yaml stop` stops infrastructure without removing its volumes. Use [backup and recovery](backup-restore.md) before changing retained state. The local realm, loopback settings and development servers are not production configuration; use the separate [production guide](production.md).
