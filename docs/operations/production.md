# Production and headless deployment

The API is a standalone service. Deploy the Python backend and the five explicit database datasource credentials, run migrations in a separate privileged job, then launch the API with `python -m koinon.serve` behind an operator-managed HTTPS proxy. Angular is optional. Forge and other consumers authenticate through their registered OIDC clients and call `/api/v1/**` using access tokens for the configured API audience. SDK consumers need neither Angular nor the backend Python package installed in their application.

Begin with [Install koinon](installation.md) for released wheels and deployment scripts. For a new installation, follow [First start in production](first-start.md) for the ordered storage, migration, sign-in, verified-subject bootstrap and first answer checks.

## Serve the management application

Use `deploy/production/nginx.conf` for an API-only reverse proxy. To serve Angular and the API on one origin, use `nginx-management.conf` instead, inside your TLS server. Build the SDK and frontend with the repository's Node tooling:

```sh
npm ci --prefix sdk/typescript --ignore-scripts
npm run build --prefix sdk/typescript
npm ci --prefix frontend --ignore-scripts
npm run build --prefix frontend
```

Set the template's `root` to the read-only `frontend/dist/management/browser` output. Account screens have direct `/account/profile`, `/account/tokens` and `/account/applications` links. The static fallback returns the management index for those links, with `Cache-Control: no-store` on the index. API, browser session, login/callback, MCP and discovery requests stay on the backend; they must never receive the SPA index. Missing assets return 404. The template supplies the content types needed by scripts, styles, branding and fonts and preserves unbuffered backend responses.

The management application owns browser history. Embedded Angular components and custom elements use account-section inputs/events and leave the host application's URL alone. Embed those components or the SDK in another product; the standalone management template permits framing only from its own origin.

The dedicated proxy CI gate runs native nginx with a temporary static site and a local HTTP fixture, checking direct account links, MIME types and backend method/body/path forwarding. It does not qualify operator TLS, production hosts, identity-provider callbacks or an active deployment.

## Operate the backend

Run the API with `python -m koinon.serve` and a separate complete worker with `python -m koinon.worker`. The default process role is `api`: it registers HTTP controllers and disables scheduled background consumption. The worker has no HTTP listener or registered controllers. It runs conversations, document and structured ingestion, indexes, attachment processing, profile synchronization, callback delivery and retention. Native knowledge services follow `koinon.knowledge.enabled`; `koinon.legacy.enabled: false` disables compatibility HTTP routes without removing those services. See [Worker roles and scaling](workers.md) for durable queues, shutdown and capacity settings.

`deploy/production/conversation-worker.service` is the complete worker template; its retained filename preserves existing service installations. The older `koinon.assistants.worker` and `koinon.knowledge.indexes.worker` entrypoints also delegate to the complete worker. Start workers only after migrations and resource checks. Apply each queue's concurrency and datasource-pool budget to every replica. The systemd templates require acceptance on the target Linux host.

`deploy/production/backend.service`, `runtime.env.example` and `nginx.conf` are reviewable templates, not an accepted production deployment. Adapt service paths, writable storage, TLS certificates, proxy limits and trusted proxy addresses. The systemd EnvironmentFile uses systemd quoting rules; the literal files read by `deploy/run.py` use a different format. Quote a nonempty JSON host allowlist correctly for the chosen launcher. Require verified database TLS with operator-managed CA material outside loopback development; backup tools preserve explicit libpq TLS URL options and reject unsupported options. Do not expose the backend directly while trusting arbitrary forwarded headers. The supplied systemd template trusts only a loopback proxy and grants writes only under `/var/lib/koinon`. Configure document/blob storage there or on an explicitly managed shared storage service. Running multiple instances requires shared storage as well as shared SQL sessions.

Provision your own identity tenant and client credentials. Start the API and management sign-in first, authenticate, and copy the exact canonical `subject` from `GET /auth/me`. Then use `deploy/bootstrap.py` once with that verified value to create a new application tenant and its first administrator. The command refuses existing tenants; use the authorized member API thereafter. Set the issuer, API audience and exact registered callback. Generic providers require explicit authorization/token/JWKS URLs and may require provider-specific authorization response settings. Entra/Google interoperability was not live-qualified. Secure cookies and HTTPS are required outside loopback development. Cookie sessions and their concurrency registry use PostgreSQL; do not replace them with process memory in a multi-instance deployment.

Keep migration authority outside the API environment. Control datasource credentials intentionally permit scoped provisioning and need the same protection as other sensitive service credentials. Keep the encryption master key in an external secret manager, backed up independently from database archives. `KOINON_MASTER_KEY` is a padded base64url-encoded 32-byte master key. Native encryption derives tenant/provider-bound keys and encrypts credentials with AES-GCM. Losing it makes stored provider credentials unrecoverable. Replacing the environment key alone is not rotation: no automatic key-ring/re-encryption workflow is currently provided. A rotation requires reviewed re-encryption or re-entry of each provider secret, validation, and a coordinated restart. Retain a protected recovery copy until old ciphertext is no longer needed.

Corporate identity and directory integrations require a separate `KOINON_IDENTITY_MASTER_KEY`, also a padded base64url-encoded 32-byte key. It encrypts their stored credentials and does not fall back to `KOINON_MASTER_KEY`. Configure it before saving a corporate provider connection, retain its independent recovery copy, and preserve it across restarts and upgrades. A working sign-in session does not establish this secret-storage prerequisite. MCP OAuth uses its own `KOINON_MCP_OAUTH_ENCRYPTION_KEY`; follow the [MCP authentication guide](mcp-authentication.md) for its format and replacement behavior. Backing up a database without its required encryption keys cannot recover the encrypted integrations.

`KOINON_ASSISTANTS_ALLOWED_PROVIDER_HOSTS` defaults to `[]`. Permit explicit provider hosts only after operator review; the local profile separately opts into loopback. URLs require HTTPS except explicitly allowed loopback HTTP. Network egress controls should independently restrict model and connector destinations. Configuring a provider does not prove it is reachable, that its model exists, or that its capabilities work.

Run `/ready` probes against the real database. Use `/health` only for process liveness. Observe job leases/retries, database saturation, identity failures and provider validation independently. An available catalog does not imply a model, connector or retained compatibility operation is qualified. Compatibility routes remain closed until an operation-specific resource verifier proves all referenced domain IDs and scope.

Before serving traffic, verify migrations, role flags, tenant isolation, membership revocation, valid/wrong-audience token behavior, CSRF, shared-session logout, storage persistence and a restore drill using deployment credentials. Back up the identity database/configuration separately. The local fixture realm and `start-dev` mode are unsuitable for production.

Copyright 2026 Firefly Software Foundation. Licensed under Apache-2.0. Made with <3.
