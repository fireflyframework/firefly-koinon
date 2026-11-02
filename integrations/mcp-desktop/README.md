<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
# firefly koinon desktop extension

The 26.11.11 source candidate adds browser OAuth to the koinon desktop extension. It has not been published: the released 26.11.10 archive still uses the PAT setup documented in the [published-package walkthrough](../../docs/integrations/desktop.md). Local package checks and installed-host acceptance are separate release gates; a source build is not a published artifact.

The bridge uses the official TypeScript MCP SDK and forwards remote tools, resources, and prompts; the server owns tool schemas and permission checks. The instructions below describe this source candidate.

## Install

1. Obtain the `.mcpb` archive and `SHA256SUMS` from a trusted distribution. Verify the archive checksum before opening it.
2. In a Claude Desktop version that supports desktop extensions, open the `.mcpb` and review the extension details.
3. Set **MCP endpoint** to the full HTTPS URL supplied by your operator, including `/mcp`. Keep **Authentication mode** as `oauth`. Enter the operator-registered **Public OAuth client ID** and **OAuth callback port**; the defaults work only if the operator registered them. Leave **Personal access token** empty.
4. Enable the extension and ask the assistant to run `koinon_desktop_connect`. Open the returned sign-in link in your browser, sign in to koinon, and review the account, workspace, and requested permissions. The link expires after two minutes. The extension never opens a browser during installation or discovery.
5. Run `koinon_desktop_status` after the browser reports success. Remote tools then become available. Access tokens remain in memory only: reconnect after the bridge restarts or the token expires. The host must refresh its tool list when notified; host behavior requires separate acceptance testing.

The package contains no Python runtime, platform-specific executable, client database, or credential. A compatible Node.js runtime (22+) must be provided by the host. Your operator must enable MCP OAuth and register the public client with its exact loopback callback. There is no automatic registration or endpoint-only client discovery. See [OAuth deployment and lifecycle](../../docs/integrations/desktop-oauth.md).

For explicit PAT compatibility, choose `pat` in **Authentication mode** and enter a scoped personal access token. The host treats that configuration field as sensitive and passes it through the environment. OAuth mode rejects a configured PAT instead of silently using it. Existing PAT installations must select `pat` when upgrading.

Legacy manual stdio configurations with `KOINON_TOKEN` and no `KOINON_AUTH_MODE` continue to use PAT mode. New MCPB configuration explicitly defaults to OAuth.

The [installation preview](preview.html) illustrates PAT compatibility settings and brand identity. It is an explanatory preview, not a screenshot of Claude Desktop or an OAuth installation.

## Skills

The `skills/` directory contains reusable assistant instructions for evidence-based knowledge work. Install the skill folders using your assistant's supported skill mechanism. Skills guide behavior; the desktop extension provides the connection. They are distributed separately in a portable skills archive as well as included for inspection in the MCPB. Installing the MCPB does not automatically install skills.

## ChatGPT and other hosts

An MCPB is a local desktop extension archive. It is not a ChatGPT connector or a local archive installer for ChatGPT. Remote connectors use their host's OAuth client and callback; this bridge's local callback does not configure them. Other stdio MCP hosts can run `node /absolute/path/server/index.cjs` with `KOINON_MCP_URL`, `KOINON_AUTH_MODE=oauth`, `KOINON_OAUTH_CLIENT_ID`, and `KOINON_OAUTH_CALLBACK_PORT` in the environment. PAT compatibility uses `KOINON_AUTH_MODE=pat` and `KOINON_TOKEN`. Never put credentials in command arguments or URLs.

## Connection and privacy

Initialization is local. In OAuth mode, discovery exposes only `koinon_desktop_connect`, `koinon_desktop_status`, and `koinon_desktop_disconnect` until sign-in completes. An explicit connect request fetches the exact same-origin koinon protected-resource and authorization-server metadata, validates resource, issuer, endpoints and S256 support, and starts a one-use callback listener on `127.0.0.1`. Browser login uses the existing koinon account and consent flow. The official MCP SDK creates the PKCE challenge and exchanges the returned code. Tokens, codes, state and verifiers are never written to files or process arguments.

Authenticated requests send a bearer header only to the exact configured MCP endpoint. Metadata and public-client token requests carry no bearer credentials. All programmatic requests reject redirects; OAuth requests have a 10-second timeout and a 64 KiB response limit, and MCP requests have a 30-second timeout. There is no telemetry destination, credential persistence or refresh-token support.

If a tool returns koinon's trusted pre-execution scope challenge, the bridge asks for explicit reconnection and consent to the existing permissions plus the required scopes. It never retries the tool automatically. Role or workspace denials do not request wider access. An ambiguous failure or unknown write outcome must be inspected before a user requests the operation again.

`koinon_desktop_disconnect` cancels pending sign-in, closes the remote connection and forgets the local credential. It does **not** revoke the server grant: use **Authorized applications** in koinon account settings for that. Uninstalling or restarting also does not revoke server grants. The existing server policy replaces an active grant for the same user, client and workspace; connecting another computer with that client can disconnect the first.

Tool results pass to the host assistant and its configured model provider. Review the host's policy and your operator's data-handling policy before use. Retrieved text is untrusted source data, not instructions. A server can expose additional capabilities; inspect the discovered contract before using them.

### In-chat review support

The bridge forwards the MCP Apps HTML capability only when the desktop host advertises `io.modelcontextprotocol/ui` with the `text/html;profile=mcp-app` MIME type. It preserves app-only tool visibility, review resources, and private result metadata. A review nonce stays in `_meta`; the bridge does not copy it into visible content or structured results. The host remains responsible for displaying the app and keeping private metadata out of model context, as defined by the [MCP Apps specification](https://github.com/modelcontextprotocol/ext-apps/blob/main/specification/2026-01-26/apps.mdx).

A host without that capability can use supported reads and the dedicated user-requested catalog organization tools, subject to current scopes and resource permissions. It cannot approve generated content or file publication through this bridge. Renaming or moving a folder does not publish knowledge content. There is no automatic approval or browser-review fallback. See the [operation walkthrough](../../docs/guides/external-agent-management.md) for timestamp preconditions and unknown outcomes. Local protocol tests cover capability forwarding; acceptance in a particular desktop application requires a separate host test.

## Build and verify

```sh
npm ci --ignore-scripts
npm run package
```

This runs TypeScript validation, behavior tests, a relocatable bundle build, the official MCPB manifest validator, and deterministic ZIP packaging with SHA256SUMS. Run `npm run smoke` after building to exercise the standalone bundle against a local mock MCP server. It does not contact a live deployment or a model. `npm run package` produces local artifacts under `dist/`; it does not publish them.

For development only, `KOINON_ALLOW_LOOPBACK_HTTP=1` permits HTTP on `localhost`, `127.0.0.1`, or `[::1]`. This override is deliberately absent from desktop configuration.

## License

Original bridge code: Copyright 2026 Firefly Software Foundation, Apache-2.0. Bundled dependencies retain their licenses in `THIRD_PARTY_NOTICES.txt`; exact versions, source URLs, and npm integrity values are in `DEPENDENCIES.json`. Manrope is licensed under SIL OFL 1.1. Firefly names and graphic identities remain protected trademarks.
