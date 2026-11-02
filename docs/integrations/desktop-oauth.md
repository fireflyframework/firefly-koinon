<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Desktop extension OAuth

!!! note "Unreleased source candidate"
    These instructions describe the OAuth implementation in source. The published 26.11.10 MCPB still uses the [PAT installation walkthrough](desktop.md). OAuth package publication and installed-host acceptance have not been established. Building this source with the unchanged version string does not reproduce the published archive.

The local koinon MCPB extension can sign in through a browser without asking the user to create or copy a personal access token. Its OAuth client runs inside the local bridge. It uses the same koinon browser login, consent, authorized-application records, workspace permissions and revocation checks as remote OAuth clients.

This implementation keeps access tokens in memory for the lifetime of the bridge process. It has no refresh tokens or persistent credential store. Users reconnect after a restart, token expiry or server revocation. A server's OAuth registration is separate from a user's consent: registering the extension does not grant it access to any account or workspace.

## Operator setup

Enable the MCP endpoint and MCP OAuth using the installation's existing configuration, including its protected encryption key. Create a **public** OAuth client in the organization's MCP application settings, or provision a static public client through `koinon.mcp.oauth.clients`. The client must have no client secret and must include `catalog:read` plus only the operation scopes the organization permits.

For the package's default client ID and callback port, the static registration entry is:

```yaml
client_id: firefly-koinon-desktop
name: koinon desktop
redirect_uris:
  - http://127.0.0.1:42839/oauth/callback
scopes:
  - catalog:read
  - knowledge:search
  - evidence:read
```

This is one entry inside the existing `koinon.mcp.oauth.clients` list, not a replacement for the installation configuration. For an organization-managed registration, copy the generated public client ID into the extension instead. Match the exact callback URI, including scheme, IP literal, port and path. Do not register a wildcard or a host connector's callback for this local client.

The default port must be free on the user's computer. To use another port, choose a port from 1024 to 65535, register its exact callback URI, and configure that same port in the extension. The bridge fails safely if the port belongs to another process. It does not kill the process, pick an unregistered port, or bind to other network interfaces.

Distribute these non-secret settings to users:

| Setting | Value |
| --- | --- |
| MCP endpoint | The installation's full HTTPS `/mcp` URL |
| Authentication mode | `oauth` |
| Public OAuth client ID | The registered public client ID |
| OAuth callback port | The port in the registered callback |
| Personal access token | Empty |

The extension does not dynamically register clients or discover a client ID from the endpoint. Operators may distribute a package configured with their non-secret defaults, but must still register the matching client. Preserve package provenance and use the approved distribution process when customizing a package.

## User journey

1. Install the MCPB in a compatible desktop host and enter the operator's settings.
2. Ask the assistant to run `koinon_desktop_connect`. Installation and tool discovery do not open a browser or start sign-in.
3. Open the returned authorization link yourself. The assistant must not fetch it or approve consent for you. It expires after two minutes.
4. Sign in through koinon's existing login and review the account, application, workspace and permissions. Initial access requests `catalog:read`.
5. After the browser confirms the connection, run `koinon_desktop_status`. The bridge notifies the host that its tool list changed, and authorized remote tools, resources and prompts become available.

If the host does not refresh its tool list after the notification, refresh the connection using that host's supported UI. Do not restart solely to preserve a session: a restart deliberately discards the token and requires another sign-in. Installed-host behavior must be verified separately from the bridge's protocol tests.

The callback validates an unpredictable one-use state, the exact local host/path and the koinon issuer. S256 binds the code to a verifier retained only in the bridge process. The browser receives a plain completion page; no access token is placed in its URL or page.

## Additional permissions and failures

When koinon returns its trusted pre-execution `insufficient_scope` challenge, the extension records the necessary scopes and tells the user to connect again. The new consent request includes the previously granted scopes and the required scopes. The user must approve it before requesting the original operation again. The bridge never replays a tool call automatically, including writes.

Ordinary role, resource or workspace denials do not become scope-upgrade requests. The server remains authoritative even after consent. Unknown scopes, foreign metadata URLs and malformed challenges cannot widen the local request. A failed or cancelled sign-in leaves remote tools unavailable; the user can inspect status and start a fresh connection.

Server `401` responses invalidate the local session. Expiry also removes the local credential without a silent refresh. Tokens and PKCE material stay in memory; there is no plaintext credential cache or operating-system command receiving a secret argument.

## Disconnect and revocation

`koinon_desktop_disconnect` stops pending authorization, closes the upstream connection and clears the token from this bridge. To revoke the grant on the server, open koinon account settings and disconnect the entry under **Authorized applications**. The server currently has no OAuth revocation endpoint for this bridge to invoke.

The existing server replacement policy is unchanged: a new authorization for the same user, client, resource and workspace replaces the active connection. Connecting a second computer with the same public client can invalidate the first computer's token. Organization administrators can disable or revise the registered application through the existing administration flow.

## PAT compatibility and remote connectors

To retain an existing personal-token workflow, explicitly select `pat` and provide a scoped token in the sensitive configuration field. The extension rejects a nonempty token field in OAuth mode. PAT tokens are sent only to the configured MCP endpoint; local OAuth controls are unavailable in PAT mode.

This MCPB runs locally over stdio. A hosted Claude or ChatGPT connector uses that host's own OAuth registration, callback and network path. The local client ID and loopback callback do not establish a hosted connector or make a private endpoint reachable from a cloud service.
