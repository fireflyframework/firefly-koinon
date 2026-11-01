# MCP authentication

Organization administrators register clients in **Settings**, under **Applications**. The [registration guide](../guides/register-applications.md) covers exact callbacks, permission ceilings, one-time secrets, revisions and revocation. Ordinary members discover enabled registrations for their organization in the account connection panel. Installation-managed static clients remain supported as read-only configuration; the YAML below describes that compatibility path, not a requirement to edit deployment files for every new application.

The remote endpoint is disabled by default. Configure a reachable HTTPS `/mcp` URL and explicit host/origin policy for remote clients. Without an explicit endpoint, the product derives a local URL from the native PyFly listener and marks it `local_only`; that is not a reachable cloud connector. A loopback HTTP URL is permitted for local development. Apply the reviewed native migrations `koinon_0015_mcp_authorization` and `koinon_0016_authorized_apps` through the deployment migration process before enabling OAuth; this change does not run migrations against an existing installation.

The fresh-install local configuration helper enables MCP and OAuth, creates an independent encryption key and leaves the client registry empty until an administrator signs in. It does not replace existing configuration. Organization-managed registrations require `koinon_0021_mcp_oauth_clients` after the preceding migrations. Its nullable registration pins preserve legacy static connections without inventing organization ownership. All replicas must share the same database, encryption key and public resource configuration.

Personal tokens work with clients that support an `Authorization: Bearer` header. Use the existing API tokens page to create a token limited to the required permissions, organization, spaces and knowledge items. A browser cookie and an ordinary API JWT cannot authenticate the MCP endpoint. Never put a token in a URL, tool argument or configuration file committed to a repository.

ChatGPT and Claude remote connectors use OAuth for account linking. The OAuth path below supports pre-registered clients with the authorization-code grant and mandatory PKCE S256. It does not advertise dynamic registration, client metadata documents, refresh tokens, OIDC identity scopes or machine-to-machine grants. Each application and its exact callback must be registered before it connects. Organization administrators do this in Settings; operators manage static installation clients. Client support and callback details must be checked in the client's current connection UI; local protocol tests do not establish acceptance by a hosted client.

```yaml
koinon:
  mcp:
    enabled: true
    public_url: https://knowledge.example.com/mcp
    oauth:
      enabled: true
      encryption_key: ${KOINON_MCP_OAUTH_ENCRYPTION_KEY}
      code_ttl_seconds: 120
      access_ttl_seconds: 3600
      clients:
        - client_id: organization-chat-client
          name: Organization Chat Client
          redirect_uris:
            - https://client.example.com/exact-callback
          scopes:
            - catalog:read
            - knowledge:search
```

Replace the example URLs with the exact public service and callback URLs. Generate an independent Fernet key with `cryptography.fernet.Fernet.generate_key()` and store it in the deployment secret manager. Keep the same key across service instances. Replacing the key invalidates existing MCP OAuth access tokens; their authorization records remain visible and can be revoked from Authorized applications. The configuration loader resolves native `${...}` environment placeholders.

Clients without `client_secret_hash` use public-client authentication (`none`) with PKCE. To register a confidential client, generate a high-entropy client secret in a secret manager and store only its lowercase SHA-256 digest in `client_secret_hash`. Give the original secret directly to that client's secure OAuth settings. The token endpoint accepts `client_secret_basic` and `client_secret_post` for confidential clients. Never use a human password as a client secret. Client IDs, redirect URLs and supported permissions are operator configuration, not end-user authority.

For organization-managed registrations, the service generates the immutable client ID and any confidential secret itself. Only its hash is persisted. Changing a registration, disabling it or rotating its secret atomically revokes linked authorizations and credentials. Authorization requests, codes, connections and bearer envelopes pin the registration revision and configuration digest; every governed use checks the current registration. Re-enabling a client cannot resurrect a revoked grant. Registration management requires the organization's `identity:manage` permission and an ordinary verified identity. Personal tokens and application credentials cannot manage the registry.

Current OAuth permissions are `catalog:read`, `knowledge:search`, `query:execute`, `chat:use`, `evidence:read`, `activity:read`, `catalog:write` and `ingest:write`. Register only those needed by that client. Personal activity summaries require `activity:read` together with `catalog:read`. The example above is read-only. To permit reviewed text changes and file uploads, additionally register `catalog:write` and `ingest:write` and have the user consent to those scopes within their current role. Apply `koinon_0020_external_reviews` before enabling that workflow; it stores private external reviews and append-only MCP source receipts. See [in-chat knowledge management](../guides/mcp-knowledge-management.md) for the embedded review, bounded private staging and operator cleanup. Dependencies such as `catalog:read` must also be registered. Consent displays readable permissions and lets the signed-in user select one authorized organization and space. The canonical permission service checks the user again during consent, token issuance and every governed tool operation. Roles are never accepted from the MCP client.

Management tools require negotiated MCP Apps support with `text/html;profile=mcp-app`; ordinary retrieval remains available without it. Native pyfly retains legacy initialization metadata in the primary repository, bound to the actual authenticated credential and configured MCP resource. Defaults are `koinon.mcp.max_sessions: 128` across instances and `session_idle_timeout_seconds: 900`. Every request authenticates again; stored capabilities never grant permissions. Modern capability envelopes remain per-request and require no session record.

The native transport uses stateless JSON requests for the modern protocol and reconstructs legacy connections from shared initialization metadata. Routing successive requests to different healthy API replicas does not require session affinity. An open response remains on its selected replica; neither transport mode stores responses for replay. Reinitialization after a disconnect must not resubmit an uncertain knowledge change as a new operation. Inspect its original review, operation status and receipt under current authorization.

Apply native migration `koinon_0026_mcp_sessions` before enabling this transport in a validation-only production schema. All replicas must use the same primary database, public MCP URL, OAuth encryption key and limits. Initialization can occur on one replica and subsequent requests on another; metadata survives an instance restart. Legacy GET returns 405, DELETE removes shared metadata, and missing/expired/incompatible IDs return 404 so clients initialize again. Canonical reviews, private one-use nonces and ingestion state remain in their repositories. Never replay an uncertain write merely because transport metadata was lost. The endpoint provides JSON tools/resources/prompts and MCP Apps capability context, without arbitrary MCP Tasks, subscriptions or response replay.

The resource publishes discovery at `/.well-known/oauth-protected-resource/mcp`. Its authorization server issuer is the configured origin plus `/oauth2/mcp`, with discovery at `/.well-known/oauth-authorization-server/oauth2/mcp`. Metadata URLs come from operator configuration and never from incoming Host or forwarded headers. The authorization endpoint is `/oauth2/mcp/authorize`; the token endpoint is `/oauth2/mcp/token`.

For a new connection, add the public MCP URL in the client's custom connector settings, choose OAuth, and supply the registered client ID and optional confidential-client secret. Use the callback URL displayed by that connection when registering the client. The user signs in through the existing Koinon identity provider, sees the requested permissions and selects a space, then approves the connection. Only a genuine browser session can approve consent; CSRF validation remains mandatory. Return URLs remain local until the registered client and its redirect URL are validated.

Authorization codes are short-lived, hashed in PostgreSQL, and bound to the client, exact redirect URL, MCP resource, PKCE challenge, scopes, canonical user and selected space. Atomic code consumption, private application-credential issuance and the durable authorization record share one native transaction, so a failed issuance leaves neither a consumed code nor a partial connection. Concurrent redemptions produce at most one token. No plaintext authorization code, canonical access token or encrypted bearer is retained in the authorization rows.

The MCP OAuth access token is an authenticated-encrypted envelope for the dedicated MCP resource. The server verifies its resource, client, expiry and current registered scopes, then revalidates the durable authorization and its private application-purpose credential. The dedicated MCP bearer is never accepted by the API or passed downstream. Only the server-owned canonical credential reaches the fixed in-process API adapter, accompanied by the original resource-bound wrapper in a private ASGI scope marker. A network header cannot supply that marker. Raw application credentials are rejected by general API and direct MCP personal-token authentication. Revocation and expiry apply immediately, and membership changes constrain the next governed operation.

Each approved connection appears in **Authorized applications**, separately from manually created API tokens. The owner can search, filter, page, inspect and revoke connections. Revocation disables the linked application credentials immediately; client-side removal alone does not notify this server. Reconnecting the same client/resource/space creates a new exact-scope authorization and atomically revokes its previous active grant, retaining history. Failed replacement rolls back and preserves the previous connection. Other applications and spaces are unaffected. Access expires after the configured lifetime; because refresh is not implemented, reconnect and approve a new grant when the client requests reauthorization. Removing a client or its permitted scopes also rejects its existing MCP OAuth envelopes. See the [account guide](../guides/authorized-applications.md).

Discovery and token responses do not set browser cookies. The OAuth token backchannel rejects browser cookies and query parameters. OAuth POST bodies are limited to 16 KiB. Keep authorization headers, token responses and OAuth request bodies out of proxy/application logs, and avoid logging authorization query strings containing codes or client state.

The implementation follows the [MCP authorization resource and audience requirements](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization) and [official OpenAI authentication documentation](https://developers.openai.com/plugins/build/auth). Hosted Claude and ChatGPT connection acceptance, production TLS, operator callback registration and external identity-provider login remain deployment qualification steps.

Copyright 2026 Firefly Software Foundation. Licensed under Apache-2.0. Made with <3.


## Organization-wide operational reads

The `koinon_platform_health` and `koinon_system_information` tools require a current organization-wide administrator PAT with `catalog:read` and `audit:read`, without workspace, asset or resource bounds. Discovery checks current authority on each request and hides these two tools when it cannot establish that authority. Invocation independently repeats the check through the canonical API. `audit:read` is not an OAuth-requestable scope. Workspace-bound OAuth connections cannot use these tools; their consent remains workspace-bound. See [Platform health](platform-health.md) for observation limits and unknown evidence.
