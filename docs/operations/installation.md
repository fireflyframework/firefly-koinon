<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
# Install koinon

Install one versioned backend, connect its infrastructure, then configure an organization. The management interface is optional: an application can use the same authorized API through an SDK without installing Angular.

| Your starting point | Follow this path |
|---|---|
| Evaluate or develop on your machine | [Local environment](local-deployment.md): a repository checkout, development infrastructure and separate API/worker terminals. |
| Install a released runtime | Use the release packages below, then follow [first start](first-start.md). |
| Upgrade an existing installation | Preserve configuration and data; follow [migrations](migrations.md) and the [upgrade sequence](first-start.md#8-back-up-upgrade-and-recover-deliberately). |
| Add knowledge features to another product | Install its [typed SDK or embedded components](../guides/integrations.md). The consumer does not install the backend runtime. |

The [reference architecture](../concepts/architecture.md#reference-deployment) shows which processes and persistent services an installation needs. These guides apply to a host, virtual machine or container platform; choose the platform, identity provider and storage services independently.

## 1. Choose one release

Obtain packages from [the official releases](https://github.com/fireflyframework/firefly-koinon/releases). Keep the selected release notes, asset checksums and configuration with your installation record. The example names below use `26.11.1`; do not combine runtime wheels from different versions.

| Release asset | What it provides |
|---|---|
| `koinon-26.11.1-source.tar.gz` | Versioned deployment scripts, migrations, configuration examples and editable source. Deployment scripts are not installed by the runtime wheel. |
| `firefly_koinon-26.11.1-py3-none-any.whl` | API, authorization, catalog and conversations. |
| `firefly_koinon_documents-26.11.1-py3-none-any.whl` | Document knowledge services. |
| `firefly_koinon_structured-26.11.1-py3-none-any.whl` | Structured knowledge services. |
| `firefly_koinon_storage-26.11.1-py3-none-any.whl` | Shared object-storage ports and adapters. |
| `koinon-management-26.10.2.tar.gz` | Optional prebuilt browser application; no Node build is needed to serve it. |
| `SHA256SUMS` | Checksums for that release's assets. |

Compare the downloaded files with the release checksum manifest before installation. On Linux, `sha256sum FILE` prints a file's digest; on macOS, use `shasum -a 256 FILE`. `sha256sum --check SHA256SUMS` checks the complete downloaded asset set; it reports missing files if only part of the release was downloaded. Preserve the supplied licenses, notices and font licenses when redistributing a package or serving the browser build.

## 2. Install an isolated Python runtime

Use Python **3.13** for the product runtime. Keep its environment separate from consumer applications and from other installations. Starting in the directory containing the four selected wheels:

```sh
python3.13 -m venv .venv
.venv/bin/python -m pip install \
  ./firefly_koinon_storage-26.11.1-py3-none-any.whl \
  ./firefly_koinon_documents-26.11.1-py3-none-any.whl \
  ./firefly_koinon_structured-26.11.1-py3-none-any.whl \
  ./firefly_koinon-26.11.1-py3-none-any.whl
.venv/bin/python -m pip check
```

This installs the runtime dependencies; it does not start a service or create infrastructure. For a controlled package mirror or offline environment, prepare the compatible dependency set separately. Select only the storage extras required by your installation; see [provider installation](storage-configuration.md). Do not use a consumer SDK wheel as the backend runtime.

Verify the installed product versions without starting the application:

```sh
.venv/bin/python - <<'PY'
from importlib.metadata import version

for distribution in (
    "firefly-koinon", "firefly-koinon-documents",
    "firefly-koinon-structured", "firefly-koinon-storage",
):
    installed = version(distribution)
    assert installed == "26.11.1", (distribution, installed)
    print(distribution, installed)
PY
```

Unpack the inspected source archive into a **new** release directory to obtain `deploy/`. Keep that source directory, installed environment and persistent data distinct. For repository development with the committed dependency lock, use `uv sync --project backend --python 3.13 --locked` instead, as described in the local guide.

The examples in older deployment guides use `backend/.venv/bin/python`. For a wheel installation, replace that path with your installed `.venv/bin/python` and run deployment scripts from the matching release's `deploy/` directory. Adapt service-template paths consistently; do not add source directories to `PYTHONPATH` to make an installed runtime work.

## 3. Configure the installation before serving traffic

Prepare these dependencies explicitly:

- **PostgreSQL and roles:** the five named runtime/control datasource bindings, plus separate migration authority. Runtime startup validates schema; it does not apply migrations.
- **Persistent object storage:** original documents, structured artifacts and private attachments. Every process that uses a file must see its recorded storage identity.
- **Identity:** issuer, API audience, exact browser callback and the endpoint settings required by your OIDC provider.
- **Secrets and keys:** separate provider, corporate identity and optional MCP OAuth encryption keys. Keep recovery material outside database archives.
- **Network and process policy:** public HTTPS origin, trusted ingress, provider egress, connection budgets and independent API/worker lifecycles. Set `KOINON_PROCESS_ROLE=api` for the API and `worker` for the complete worker process.

Start from `deploy/production/configuration.yaml.example` and `runtime.env.example`. They contain placeholders, not working credentials. Set `KOINON_CONFIG_FILE` to the private YAML, TOML or JSON file. Product environment aliases override matching file values. [Operator configuration](configuration.md) explains precedence, bounded settings and observations.

For literal mode-0600 `KEY=VALUE` files, use the supplied `deploy/run.py`; do not source them into a shell. A service manager's environment-file quoting rules may differ. Keep migration credentials out of the API and worker environments.

## 4. Migrate, start and establish the first administrator

Continue with [first start](first-start.md), which orders the remaining work:

1. Provision the database roles, apply all migration histories, grant privileges and run checks.
2. Start the API through `python -m koinon.serve` and route its browser sign-in through the public HTTPS origin.
3. Choose a reviewed initialization mode: bootstrap from the exact signed-in `/auth/me` subject, or seed pending direct-Entra identity grants and let verified first sign-in bind the canonical subjects. Both create only a new organization.
4. Start the complete worker with `python -m koinon.worker` and complete [guided organization setup](../guides/knowledge-setup.md).
5. Upload a small fictional source, inspect its cited answer and audit evidence, then verify backup and restore.

A healthy API does not prove that a worker is consuming jobs, that storage persists after replacement, or that a configured model can answer. Check those outcomes independently before admitting normal traffic.

## 5. Add the optional management interface

Serve the prebuilt management archive as read-only static files behind the same public HTTPS origin as the API. Its archive root contains `index.html`; set the static document root accordingly. Keep API, sign-in, callback, MCP, discovery and browser-session routes on the backend. Missing static assets must return 404 rather than the application index.

The [production proxy guide](production.md#serve-the-management-application) provides a template. Its source-build commands are for changing the frontend; they are unnecessary when using the matching prebuilt management asset. SDK-only deployments can omit this static application entirely.

Copyright 2026 Firefly Software Foundation. Licensed under Apache-2.0.
