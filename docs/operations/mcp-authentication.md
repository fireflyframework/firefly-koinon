# MCP authentication

The remote endpoint is disabled by default. Configure a public HTTPS `/mcp` URL and the explicit host/origin policy before enabling it. A loopback HTTP URL is permitted for local development. Apply the reviewed native migrations `koinon_0015_mcp_authorization` and `koinon_0016_authorized_apps` through the deployment migration process before enabling OAuth; this change does not run migrations against an existing installation.

Personal tokens work with clients that support an `Authorization: Bearer` header. Use the existing API tokens page to create a token limited to the required permissions, organization, spaces and knowledge items. A browser cookie and an ordinary API JWT cannot authenticate the MCP endpoint. Never put a token in a URL, tool argument or configuration file committed to a repository.

ChatGPT and Claude remote connectors use OAuth for account linking. The OAuth path below supports pre-registered clients with the authorization-code grant and mandatory PKCE S256. It does not advertise dynamic registration, client metadata documents, refresh tokens, OIDC identity scopes or machine-to-machine grants. Operators must register each client and its exact callback URL. Client support and callback details must be checked in the client's current connection UI; local protocol tests do not establish acceptance by a hosted client.

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

Current OAuth permissions are `catalog:read`, `knowledge:search`, `query:execute`, `chat:use` and `evidence:read`. Register only those needed by that client. Dependencies such as `catalog:read` must also be registered. Consent displays readable permissions and lets the signed-in user select one authorized organization and space. The canonical permission service checks the user again during consent, token issuance and every governed tool operation. Roles are never accepted from the MCP client.

The resource publishes discovery at `/.well-known/oauth-protected-resource/mcp`. Its authorization server issuer is the configured origin plus `/oauth2/mcp`, with discovery at `/.well-known/oauth-authorization-server/oauth2/mcp`. Metadata URLs come from operator configuration and never from incoming Host or forwarded headers. The authorization endpoint is `/oauth2/mcp/authorize`; the token endpoint is `/oauth2/mcp/token`.

For a new connection, add the public MCP URL in the client's custom connector settings, choose OAuth, and supply the registered client ID and optional confidential-client secret. Use the callback URL displayed by that connection when registering the client. The user signs in through the existing Koinon identity provider, sees the requested permissions and selects a space, then approves the connection. Only a genuine browser session can approve consent; CSRF validation remains mandatory. Return URLs remain local until the registered client and its redirect URL are validated.

Authorization codes are short-lived, hashed in PostgreSQL, and bound to the client, exact redirect URL, MCP resource, PKCE challenge, scopes, canonical user and selected space. Atomic code consumption, private application-credential issuance and the durable authorization record share one native transaction, so a failed issuance leaves neither a consumed code nor a partial connection. Concurrent redemptions produce at most one token. No plaintext authorization code, canonical access token or encrypted bearer is retained in the authorization rows.

The MCP OAuth access token is an authenticated-encrypted envelope for the dedicated MCP resource. The server verifies its resource, client, expiry and current registered scopes, then revalidates the durable authorization and its private application-purpose credential. The dedicated MCP bearer is never accepted by the API or passed downstream. Only the server-owned canonical credential reaches the fixed in-process API adapter, accompanied by the original resource-bound wrapper in a private ASGI scope marker. A network header cannot supply that marker. Raw application credentials are rejected by general API and direct MCP personal-token authentication. Revocation and expiry apply immediately, and membership changes constrain the next governed operation.

Each approved connection appears in **Authorized applications**, separately from manually created API tokens. The owner can search, filter, page, inspect and revoke connections. Revocation disables the linked application credentials immediately; client-side removal alone does not notify this server. Reconnecting the same client/resource/space creates a new exact-scope authorization and atomically revokes its previous active grant, retaining history. Failed replacement rolls back and preserves the previous connection. Other applications and spaces are unaffected. Access expires after the configured lifetime; because refresh is not implemented, reconnect and approve a new grant when the client requests reauthorization. Removing a client or its permitted scopes also rejects its existing MCP OAuth envelopes. See the [account guide](../guides/authorized-applications.md).

Discovery and token responses do not set browser cookies. The OAuth token backchannel rejects browser cookies and query parameters. OAuth POST bodies are limited to 16 KiB. Keep authorization headers, token responses and OAuth request bodies out of proxy/application logs, and avoid logging authorization query strings containing codes or client state.

The implementation follows the [MCP authorization resource and audience requirements](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization) and [official OpenAI authentication documentation](https://developers.openai.com/plugins/build/auth). Hosted Claude and ChatGPT connection acceptance, production TLS, operator callback registration and external identity-provider login remain deployment qualification steps.

Copyright 2026 Firefly Software Foundation. Licensed under Apache-2.0. Made with <3.
