<!-- Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0 -->
# First start in production

Use this order for a new installation. It connects the [production deployment](production.md) with [guided organization configuration](../guides/knowledge-setup.md). Keep the release, configuration and recovery records together. An existing installation follows the upgrade procedure below and keeps its data and memberships.

## 1. Prepare persistent storage and private PostgreSQL

Choose persistent roots for original documents, structured artifacts and private chat files before starting the API or workers. All replicas must use the intended shared storage. Follow [storage configuration](storage-configuration.md) for the three independent profiles and required cloud extras.

For an Azure VM, verify the attached data disk by its expected LUN, size and disk identity using the VM attachment record and the guest's supported device mapping. NVMe guests can expose different names and Azure links from SCSI guests. Do not assume `/dev/sdc`, a SCSI LUN path or the first NVMe device is the data disk. Inspect before mounting:

```sh
lsblk -o NAME,PATH,SIZE,FSTYPE,MOUNTPOINTS,MODEL,SERIAL
findmnt --target /var/lib/koinon --output SOURCE,TARGET,FSTYPE,OPTIONS
```

Inspect `/dev/disk/azure` links if the image provides them, and resolve the chosen link to its actual device. Match that result to the attachment's LUN and disk identity. A missing SCSI link does not establish that an NVMe disk is missing. Preserve existing filesystems, UUIDs and contents; do not format a retained disk to make a setup command succeed. Mount the verified filesystem persistently, then check ownership and the service's writable paths. Confirm the storage directory resolves to that persistent filesystem, including after a restart. The systemd templates permit writes under `/var/lib/koinon`.

Keep PostgreSQL on the reviewed private network and verify its DNS resolution and firewall path from the application host. Configure all five explicit runtime datasource URLs:

| Environment variable | Purpose |
|---|---|
| `KOINON_DATABASE_URL` | Primary catalog, authorization, sessions and jobs |
| `KOINON_CANON_DATABASE_URL` | Document runtime |
| `KOINON_CANON_ADMIN_DATABASE_URL` | Scoped document provisioning |
| `KOINON_STRUCTURED_DATABASE_URL` | Structured runtime |
| `KOINON_STRUCTURED_ADMIN_DATABASE_URL` | Scoped structured provisioning |

Apply the approved TLS mode and trusted CA to **every** URL; configuring primary alone does not configure the other four. For SQLAlchemy/asyncpg URLs, the driver parameter is `ssl`, such as `?ssl=verify-full`, with the trusted CA available to the service through `PGSSLROOTCERT`. Verify the certificate hostname against the database DNS name. Migration and backup tooling have their own connection requirements: the backup wrapper accepts libpq `sslmode`/`sslrootcert` options and rejects unsupported ones. Do not copy query parameters between drivers blindly. [Operator configuration](configuration.md) explains independent pools and timeouts.

## 2. Establish secrets, roles and migrations

Prepare the protected runtime configuration from the [production templates](production.md). Configure the identity issuer, API audience, registered callback, client credentials, public HTTPS origin and trusted proxy. Generic identity providers also need the correct authorization, token and JWKS endpoints. Keep secure cookies enabled outside loopback development.

Store credentials and three independent encryption keys in the secret manager:

- `KOINON_MASTER_KEY` protects model-provider secrets.
- `KOINON_IDENTITY_MASTER_KEY` protects stored corporate identity and directory integration credentials. It does not fall back to the provider key; successful sign-in does not prove these secrets can be stored.
- `KOINON_MCP_OAUTH_ENCRYPTION_KEY` is required when MCP OAuth is enabled.

Back up each key and its recovery material independently, following the [encryption and recovery notes](production.md#operate-the-backend) and [MCP key instructions](mcp-authentication.md). Keep `KOINON_MIGRATION_DATABASE_URL` outside API and worker environments. The primary, document and structured runtime roles must not be superusers or bypass row security. The two separate control roles receive only their reviewed provisioning authority, including the required row-security bypass; neither is a general application credential.

Follow [migrations](migrations.md) in order: provision roles, apply the three migration histories, grant the current table privileges, then run migration and role checks. Runtime schema policy remains `validate`. Do not stamp, reset or recreate retained histories to bypass a failed check.

## 3. Start the API and management application

Start the migrated API with its runtime credentials and persistent storage. Serve the management build and backend routes through the reviewed HTTPS proxy. Use the [management proxy instructions](production.md#serve-the-management-application); login, callback, `/auth`, API, MCP and discovery routes must reach the backend. Confirm `/health` for liveness and `/ready` for the real database check.

The API and sign-in screen must be available **before** creating the first application tenant. A successful identity-provider login does not grant organization membership. Start the separate conversation worker before testing generated chat answers; API readiness alone does not consume that queue. See [backend operation](production.md#operate-the-backend) for worker templates and connection budgets.

## 4. Sign in, verify the subject, then bootstrap

Sign in as the person who will administer the new organization. In that authenticated browser session, open `GET /auth/me` on the same public origin. Require `authenticated: true` and copy the complete `subject` returned by the server. This is the verified issuer and `sub` joined by `|`. Do not substitute an email address, display name, directory object identifier or a subject inferred from another application.

For a repository installation, run the native bootstrap CLI from the deployed release root with that exact value and the reviewed runtime environment. A packaged installation uses its own installed Python interpreter and the distribution’s deployment-script directory. The placeholders below are operator inputs, not credentials:

```sh
KOINON_BOOTSTRAP_SUBJECT='paste-the-exact-auth-me-subject'
backend/.venv/bin/python deploy/run.py --env-file /private/runtime.env -- \
  backend/.venv/bin/python deploy/bootstrap.py \
  --tenant-id initial-organization --name 'Your organization' \
  --subject "$KOINON_BOOTSTRAP_SUBJECT"
```

`deploy/run.py` reads a mode-0600 literal `KEY=VALUE` file without shell evaluation. A systemd `EnvironmentFile` uses different quoting rules. The bootstrap validates the configured issuer prefix, creates the tenant and first administrator in one native transaction, and records an audit event. It refuses an existing tenant; use its authorized membership workflow instead of rerunning bootstrap to repair access.

Reopen or reload the management application and select the new organization. If it does not appear, compare the signed-in `/auth/me` subject with the exact bootstrap value before changing any membership.

## 5. Complete guided organization configuration

Continue with [Configure your corporate brain](../guides/knowledge-setup.md). Review **Access**, **Identity & appearance**, **Providers**, **Knowledge models**, **Knowledge behavior** and **Agents** in that order. Confirm the active organization before saving. Installation branding controls the signed-out experience; organization overrides apply after authentication.

Validate the actual provider endpoint, protocol and chosen model. Assign an explicit compatible document embedding model, dimensions and space as well as the answer and chat roles. Begin with RAG for the first document exercise. Discovery or a saved model assignment does not establish that streaming, tools or RLM work. Confirm storage observations and an actual write/read under deployment credentials; a configured bucket alone is insufficient.

## 6. Exercise upload, RAG, streaming and immutable evidence

Upload a small fictional document with a fact whose answer you know. Wait for ingestion and indexing, then ask a bounded question using that source. Check streamed text through the public proxy, the completed answer and its cited fragment. Open **Audit** to inspect actual tool outcomes, sources and recorded policy. Check the same flow with a reader account and a source it cannot access.

Replace the test document through the authorized, revision-checked flow. Ask again and confirm the new answer uses the new version while the earlier answer still resolves its original immutable source. Follow [agents and chat](../guides/agents.md) for SSE and audit, and [versions and lineage](../guides/lineage.md) for the exact replacement preconditions. A functioning stream or model action alone is insufficient factual acceptance. Publishing a proposed organizational conclusion still requires explicit user confirmation.

## 7. Connect external applications through the public endpoint

When enabling MCP, set `koinon.mcp.public_url` to the exact reachable HTTPS `/mcp` URL and review allowed hosts/origins. Use the same public resource configuration and encryption key across replicas. A loopback-derived URL cannot serve a hosted client.

For an OAuth connection, an administrator [registers the application](../guides/register-applications.md) with its exact callback and permission ceiling. The user then signs in, selects an authorized space and consents to that client. The current server does not advertise dynamic client registration; a client must use an existing registration. Confirm public discovery and the actual client's supported registration flow before testing consent. [MCP authentication](mcp-authentication.md) covers discovery paths, PKCE, secrets and revocation. Keep bearer tokens out of URLs and logs.

## 8. Back up, upgrade and recover deliberately

Schedule database and object backups, protect the encryption key and identity configuration separately, and rehearse [restore into a new isolated database](backup-restore.md). Keep the restored copy for inspection; a backup file existing is not a restore test.

For a simple upgrade, preserve the current release and protected configuration, back up retained data, test the exact new release and migrations on a restored copy, then schedule migration and restart separately. Apply current grants, check readiness and repeat the small upload/RAG/audit exercise before resuming normal traffic. Include API replicas and workers in the connection and rollout plan.

A code rollback is safe only when the previous release remains compatible with the resulting schema and data. Automatic database downgrade is disabled. If compatibility is not established, use the reviewed recovery plan and verified backups rather than deleting history, resetting counters or formatting storage. Record the exact recovery point and retain the original data for investigation.

Copyright 2026 Firefly Software Foundation. Licensed under Apache-2.0. Made with <3.
