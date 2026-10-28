# Local infrastructure and API

The local profile uses PostgreSQL 17.11 with pgvector 0.8.7, Redis 8.2.3 and Keycloak 26.8.1. Ports bind to loopback: PostgreSQL 18783, identity 18784, Redis 18787, API 18781. Confirm these ports are free. The Compose template targets a new local deployment; it was structurally checked but not executed during qualification. Equivalent privately installed services were tested directly.

Run from the repository root with Python 3.13 and the backend environment installed. Generate a new secret directory outside the repository:

```sh
backend/.venv/bin/python deploy/generate_local_configuration.py /private/koinon-local
export KOINON_SECRETS_DIR=/private/koinon-local
docker compose -f deploy/compose.yaml up -d --build
```

The generator refuses an existing directory. Files have mode 0600 and the directory mode 0700. It generates distinct database credentials, identity fixture credentials, a Redis password and a 32-byte encryption master key. Keycloak resolves realm environment placeholders on import, as documented in [Keycloak import/export](https://www.keycloak.org/server/importExport). Import initializes a new realm; it does not update an existing realm.

Provision roles, migrate, grant scoped tables, then start the headless backend:

```sh
backend/.venv/bin/python deploy/run.py --env-file /private/koinon-local/migration.env -- backend/.venv/bin/python deploy/provision_roles.py
backend/.venv/bin/python deploy/run.py --env-file /private/koinon-local/migration.env -- backend/.venv/bin/python deploy/migrate.py
backend/.venv/bin/python deploy/run.py --env-file /private/koinon-local/migration.env -- backend/.venv/bin/python deploy/provision_roles.py --grant
backend/.venv/bin/python deploy/run.py --env-file /private/koinon-local/migration.env -- backend/.venv/bin/python deploy/migrate.py --check
backend/.venv/bin/python deploy/run.py --env-file /private/koinon-local/runtime.env -- backend/.venv/bin/python -m uvicorn koinon.main:app --host 127.0.0.1 --port 18781
```

The runtime file excludes migration authority. `deploy/run.py` reads literal KEY=VALUE lines without shell evaluation, preserving JSON. Do not source its runtime file into a shell. The local profile explicitly allows only loopback model hosts; no model provider is automatically configured or accepted.

Headless consumers call `/api/v1/context` with a valid access token for the configured API audience. `/api/v1/capabilities` reports prerequisites. `/health` checks process health; `/ready` reads the real catalog database. No frontend is required.

For optional browser development, run the frontend on 18782 and start `/oauth2/authorization/koinon`. The exact callback is `http://127.0.0.1:18781/login/oauth2/code/koinon`. Browser calls use `/bff/api/v1/**`; `/api/v1/**` requires bearer authentication. BFF requests reject Authorization headers. Cookie mutations and POST `/logout` require the matching XSRF token.

The local realm has fictional admin, analyst, editor, viewer and outsider users with generated passwords. Identity grants no product membership. Bootstrap an initial canonical `issuer|sub` administrator after confirming that user's stable subject claim in the identity provider. For the generated local realm, the fictional admin ID is `8c85d9a1-6168-4fb0-ae11-1b8a41227a01`:

```sh
backend/.venv/bin/python deploy/run.py --env-file /private/koinon-local/runtime.env -- backend/.venv/bin/python deploy/bootstrap.py --tenant-id north --name "Local workspace organization" --subject "http://127.0.0.1:18784/realms/koinon|8c85d9a1-6168-4fb0-ae11-1b8a41227a01"
```

This offline operator command creates only a new tenant and its first admin in one native transaction, records an audit event, and refuses existing tenants. Use the authorized member API for later changes. Database/identity roles do not confer product permissions. Do not import fictional users into production.

Persistent volumes retain state. Stop services without removing volumes when preserving data. Do not initialize unrelated databases or delete volumes as a troubleshooting shortcut.

Copyright 2026 Firefly Software Foundation. Licensed under Apache-2.0. Made with <3.
