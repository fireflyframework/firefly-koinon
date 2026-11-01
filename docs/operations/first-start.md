<!-- Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0 -->
# First start in production

Use this order after [installing a matching release](installation.md). It connects the [production deployment](production.md) with [guided organization configuration](../guides/knowledge-setup.md). Keep the release, configuration and recovery records together. An existing installation follows the upgrade procedure below and keeps its data and memberships.

## 1. Prepare persistent storage and private PostgreSQL

Choose persistent roots for original documents, structured artifacts and private chat files before starting the API or workers. All replicas must use the intended shared storage. Follow [storage configuration](storage-configuration.md) for the three independent final-content profiles and required cloud extras. Queued Library uploads additionally require [bulk staging](durable-bulk.md) under its own configuration prefix. Prepare that private namespace before accepting file batches; configuring only the final document store is insufficient.

For a filesystem-backed deployment, identify the intended persistent volume using
your platform's attachment record and the host's supported device mapping. Match
its identity, size and existing filesystem before mounting. On Linux, inspect:

```sh
lsblk -o NAME,PATH,SIZE,FSTYPE,MOUNTPOINTS,MODEL,SERIAL
findmnt --target /var/lib/koinon --output SOURCE,TARGET,FSTYPE,OPTIONS
```

Device names vary across hosts and storage drivers. Do not assume a particular
disk name or format a retained volume to make setup succeed. For containers,
verify the persistent volume and its mount inside the running workload; a
container's writable layer is not durable storage. Confirm ownership, service
write permissions and persistence after replacement. The systemd templates
permit writes under `/var/lib/koinon`; adapt that path for your platform.

Keep PostgreSQL on the reviewed private network and verify its DNS resolution and firewall path from the application host. Configure all five explicit runtime datasource URLs:

| Environment variable | Purpose |
|---|---|
| `KOINON_DATABASE_URL` | Primary catalog, authorization, sessions and jobs |
| `KOINON_CANON_DATABASE_URL` | Document runtime |
| `KOINON_CANON_ADMIN_DATABASE_URL` | Scoped document provisioning |
| `KOINON_STRUCTURED_DATABASE_URL` | Structured runtime |
| `KOINON_STRUCTURED_ADMIN_DATABASE_URL` | Scoped structured provisioning |

Apply the approved TLS mode and trusted CA to **all five datasources**. Use the database DNS name covered by its certificate. The connection options depend on the driver: runtime `postgresql+asyncpg` profiles accept `connect-args.ssl: true`, while psycopg migration tooling uses `sslmode=verify-full` and `sslrootcert`. These options are not interchangeable. Follow the [driver-specific TLS steps](configuration.md#postgresql-tls-by-driver) before starting either process; that guide also explains CA loading and independent connection pools.

The [shared cache](postgresql-cache.md) also uses the registered primary PostgreSQL datasource. Keep `pyfly.cache.enabled: true`, `pyfly.cache.provider: postgres` and `pyfly.cache.postgres.datasource: primary`. Apply native migration 34 and the current runtime grants before starting the application. Replay responses, corpus pages and shared rolling limits use separate namespaces and retain their state across replica replacement.

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

The API and sign-in screen must be available for the first interactive login. A successful identity-provider login alone does not grant organization membership. Establish that membership through one of the explicit initialization modes below. Start the complete background process with `python -m koinon.worker` before testing generated chat answers or scheduled work. Set `KOINON_PROCESS_ROLE=worker` for that process and `api` for the HTTP process. API readiness alone does not consume queues or run maintenance. See [backend operation](production.md#operate-the-backend) for worker templates and connection budgets.

Enable only the bulk consumers this deployment needs. Queued Library file processing requires `PYFLY_KOINON_KNOWLEDGE_BULK_WORKER_ENABLED=true` on its worker replicas. Query batches have the separate `PYFLY_KOINON_KNOWLEDGE_BULK_QUERY_WORKER_ENABLED` opt-in. Both default to false and must remain off on API replicas. Follow [worker roles](workers.md) for these flags, shared heavy-operation admission and database connection sizing.

## 4. Establish the first administrators

Choose one initialization mode for a **new** organization. Both use the native primary database and record an audit event. Neither repairs or replaces an existing organization.

- **Verified subject:** sign in first and copy the exact canonical subject from the application. This mode supports the configured identity provider.
- **Pending direct-Entra identities:** an operator seeds reviewed immutable directory object IDs before their first login. The application learns each canonical subject only from that person's verified interactive OIDC ID token.

### Pending direct-Entra identities

Use this mode only when the native sign-in client connects directly to the Entra tenant. The configured issuer must be exactly `https://login.microsoftonline.com/<tenant UUID>/v2.0`, with the reviewed server-side browser client ID. Brokered connections and other providers use the verified-subject mode below. Do not infer `sub` from an object ID, email address or another application's token.

After migrations and role provisioning, prepare a private JSON file with the exact configured issuer/client and the operator-verified tenant/object UUIDs. Each grant explicitly requests `admin` and expires within the next seven days according to the database clock. The file supports 1–100 unique identities and rejects additional fields. These fictional UUIDs and date are syntax examples; replace them with reviewed values and a current expiry:

```json
{
  "issuer": "https://login.microsoftonline.com/11111111-1111-4111-8111-111111111111/v2.0",
  "client_id": "reviewed-native-browser-client-id",
  "entra_tenant_id": "11111111-1111-4111-8111-111111111111",
  "grants": [
    {
      "object_id": "22222222-2222-4222-8222-222222222222",
      "role": "admin",
      "expires_at": "2026-11-02T12:00:00Z"
    }
  ]
}
```

Protect this file with mode 0600. Run the CLI from the deployed release with an explicitly reviewed **operator** environment. It contains the normal application configuration, but its primary datasource uses an operator credential authorized to insert the new organization, audit and pending grants. Keep that credential outside API/worker environments; the normal runtime role can select grants and update only their three activation columns. It cannot seed, rewrite identities or expiry, delete, or truncate grants.

Bootstrap creates the normal application context. Preserve its runtime database driver and TLS profile when substituting the authorized operator credential. In an asyncpg installation, the operator primary URL must still use `postgresql+asyncpg`; do not copy the psycopg migration URL into it. Keep the other four datasource roles and profiles explicit.

```sh
backend/.venv/bin/python deploy/run.py --env-file /private/bootstrap-operator.env -- \
  backend/.venv/bin/python deploy/bootstrap.py \
  --tenant-id initial-organization --name 'Your organization' \
  --identity-grants-file /private/initial-administrators.json
```

The operator command creates the organization with pending grants and **no membership yet**. Each listed person then signs in through the normal public sign-in screen. Only the strict native interactive OIDC callback can activate a matching grant: the ID token must verify signature, nonce, issuer and browser audience, and its signed `tid`/`oid` must match the seed. API JWTs, PATs, userinfo, request headers and email addresses cannot activate it. Activation atomically creates the organization-wide administrator membership, audit and configured welcome admission, and consumes the grant. No email is sent by this command.

Consumption is permanent. Removing or revoking the membership, restarting, changing branding or moving the public domain never restores it. Pending expired grants do not activate; conflicting existing memberships require authorized review. A serializable conflict may require a new normal login attempt. There is no runtime reseed or recovery endpoint. Preserve consumed rows during backup/restore and use the authorized membership workflow for subsequent changes. Issuer/client migrations require a separate reviewed identity migration.

### Verified subject after sign-in

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

Corporate directory synchronization is optional. Native Entra sign-in and the pending administrator grants above require the verified OIDC identity, not Microsoft Graph application permission. Start with local organization/workspace roles, knowledge, chat and MCP while no corporate directory connection is active. Directory group grants, profile/position refresh and recipient-bound email invitations are separate features; configure their directory credential and consent later. An unavailable directory must not become an invented email/subject identity or a deployment-wide requirement.

Leave a new connection in **Draft**, or do not create one yet. When ready, configure and test the real directory connection with the current organization administrator, review group-to-role mappings and profile sources, then activate it through the existing validation flow. Saving the form does not grant Graph consent or activate synchronization. Directory-dependent actions remain unavailable until their prerequisites pass. See [corporate profile synchronization](../guides/corporate-profile-sync.md).

For an already active managed-access policy, directory failure or provider disablement does not turn its managed grants into local memberships. Expired or invalid managed grants stop authorizing access; independently assigned local memberships retain their own authority. Do not disable freshness checks to make a directory-dependent account work during an outage.

Continue with [Configure your corporate brain](../guides/knowledge-setup.md). Review **Access**, **Identity & appearance**, **Providers**, **Knowledge models** and **Agents** in that order. **Knowledge behavior** is the first panel within **Knowledge models**, followed by model-role assignments. Confirm the active organization before saving. Installation branding controls the signed-out experience; organization overrides apply after authentication.

Validate the actual provider endpoint, protocol and chosen model. Assign an explicit compatible document embedding model, dimensions and space as well as the answer and chat roles. Begin with RAG for the first document exercise. Discovery or a saved model assignment does not establish that streaming, tools or RLM work. Confirm storage observations and an actual write/read under deployment credentials; a configured bucket alone is insufficient.

## 6. Exercise upload, RAG, streaming and immutable evidence

Upload a small fictional document with a fact whose answer you know. Wait for ingestion and indexing, then ask a bounded question using that source. Check streamed text through the public proxy, the completed answer and its cited fragment. Open **Audit** to inspect actual tool outcomes, sources and recorded policy. Check the same flow with a reader account and a source it cannot access.

Replace the test document through the authorized, revision-checked flow. Ask again and confirm the new answer uses the new version while the earlier answer still resolves its original immutable source. Follow [agents and chat](../guides/agents.md) for SSE and audit, and [versions and lineage](../guides/lineage.md) for the exact replacement preconditions. A functioning stream or model action alone is insufficient factual acceptance. Publishing a proposed organizational conclusion still requires explicit user confirmation.

Repeat the [representative acceptance exercise](../guides/knowledge-setup.md#complete-the-first-acceptance-exercise) for a dataset, a reader outside the source's scope, an insufficient-evidence question and a completed SSE reconnect. The server releases exact authorized source excerpts and verified typed values; it does not use general model knowledge as fallback factual content. Tool activity may stream before the final evidence selection passes, but unvalidated model drafts remain private. See [knowledge-only responses](../reference/knowledge-only-responses.md) for the output receipt and historical-response behavior.

Use [Platform health](platform-health.md#diagnose-a-problem-in-order) to locate a missing prerequisite. Its passive observations do not run a model, send email, prove worker liveness or perform a cloud write. Keep a deployment acceptance record with the exact release, storage routes, processing outcomes, source versions, question, expected result and permissions tested. Record an external client journey separately when that client is enabled.

## 7. Connect external applications through the public endpoint

When enabling MCP, set `koinon.mcp.public_url` to the exact reachable HTTPS `/mcp` URL and review allowed hosts/origins. Use the same public resource configuration and encryption key across replicas. A loopback-derived URL cannot serve a hosted client.

For an OAuth connection, an administrator [registers the application](../guides/register-applications.md) with its exact callback and permission ceiling. The user then signs in, selects an authorized space and consents to that client. The current server does not advertise dynamic client registration; a client must use an existing registration. Confirm public discovery and the actual client's supported registration flow before testing consent. [MCP authentication](mcp-authentication.md) covers discovery paths, PKCE, secrets and revocation. Keep bearer tokens out of URLs and logs.

## 8. Back up, upgrade and recover deliberately

Schedule database and object backups, protect the encryption key and identity configuration separately, and rehearse [restore into a new isolated database](backup-restore.md). Keep the restored copy for inspection; a backup file existing is not a restore test.

For a simple upgrade, preserve the current release and protected configuration, back up retained data, test the exact new release and migrations on a restored copy, then schedule migration and restart separately. Apply current grants, check readiness and repeat the small upload/RAG/audit exercise before resuming normal traffic. Include API replicas and workers in the connection and rollout plan.

A code rollback is safe only when the previous release remains compatible with the resulting schema and data. Automatic database downgrade is disabled. If compatibility is not established, use the reviewed recovery plan and verified backups rather than deleting history, resetting counters or formatting storage. Record the exact recovery point and retain the original data for investigation.

Copyright 2026 Firefly Software Foundation. Licensed under Apache-2.0. Made with <3.
