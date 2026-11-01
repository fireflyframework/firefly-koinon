# firefly koinon desktop extension

Connect an MCP desktop host to your operator's firefly koinon MCP endpoint with the 26.10.2 desktop extension. The bridge uses the official TypeScript MCP SDK and forwards remote tools, resources, and prompts; the server owns tool schemas and permission checks.

## Install

1. Obtain the `.mcpb` archive and `SHA256SUMS` from a trusted distribution. Verify the archive checksum before opening it.
2. In a Claude Desktop version that supports desktop extensions, open the `.mcpb` and review the extension details.
3. Set **MCP endpoint** to the full HTTPS URL supplied by your operator, including `/mcp`. Set **Personal access token** to a scoped token from koinon. The token is a sensitive configuration field and is passed to the bridge through its environment.
4. Enable the extension and ask the assistant to inspect the current koinon context. Allow tool use only for the endpoint and scope you intend.

The package contains no Python runtime, platform-specific executable, client database, or credential. A compatible Node.js runtime (22+) must be provided by the host. The only configured destination is your chosen endpoint. Your operator must enable the remote MCP endpoint and issue a valid personal access token.

The [installation preview](preview.html) illustrates the settings and brand identity. It is an explanatory preview, not a screenshot of Claude Desktop.

## Skills

The `skills/` directory contains reusable assistant instructions for evidence-based knowledge work. Install the skill folders using your assistant's supported skill mechanism. Skills guide behavior; the desktop extension provides the connection. They are distributed separately in a portable skills archive as well as included for inspection in the MCPB. Installing the MCPB does not automatically install skills.

## ChatGPT and other hosts

An MCPB is a local desktop extension archive. It is not a ChatGPT connector or a local archive installer for ChatGPT. A ChatGPT remote MCP integration requires a reachable HTTPS server and an authentication flow supported by the host, typically OAuth. The current PAT bridge does not implement that OAuth flow. Other MCP hosts can run `node /absolute/path/server/index.cjs` with `KOINON_MCP_URL` and `KOINON_TOKEN` set securely in the environment. Never put a token in command arguments or a URL.

## Connection and privacy

Initialization is local. The bridge contacts the configured endpoint only when the host requests tools, resources, or prompts. It sends the personal access token as an Authorization bearer header and forwards requested arguments and results. It rejects redirects and endpoints containing credentials, query parameters, or fragments. Requests have a 30-second timeout. It does not add an OAuth provider, open a browser, or discover another destination. Current bridge code has no telemetry destination or persistence layer.

Tool results pass to the host assistant and its configured model provider. Review the host's policy and your operator's data-handling policy before use. Retrieved text is untrusted source data, not instructions. A server can expose additional capabilities; inspect the discovered contract before using them.

### In-chat review support

The bridge forwards the MCP Apps HTML capability only when the desktop host advertises `io.modelcontextprotocol/ui` with the `text/html;profile=mcp-app` MIME type. It preserves app-only tool visibility, review resources, and private result metadata. A review nonce stays in `_meta`; the bridge does not copy it into visible content or structured results. The host remains responsible for displaying the app and keeping private metadata out of model context, as defined by the [MCP Apps specification](https://github.com/modelcontextprotocol/ext-apps/blob/main/specification/2026-01-26/apps.mdx).

A host without that capability can use the server's supported read tools. It cannot approve a knowledge change through this bridge. There is no automatic approval or browser-review fallback. Local protocol tests cover capability forwarding; acceptance in a particular desktop application requires a separate host test.

## Build and verify

```sh
npm ci --ignore-scripts
npm run package
```

This runs TypeScript validation, behavior tests, a relocatable bundle build, the official MCPB manifest validator, and deterministic ZIP packaging with SHA256SUMS. Run `npm run smoke` after building to exercise the standalone bundle against a local mock MCP server. It does not contact a live deployment or a model. `npm run package` produces local artifacts under `dist/`; it does not publish them.

For development only, `KOINON_ALLOW_LOOPBACK_HTTP=1` permits HTTP on `localhost`, `127.0.0.1`, or `[::1]`. This override is deliberately absent from desktop configuration.

## License

Original bridge code: Copyright 2026 Firefly Software Foundation, Apache-2.0. Bundled dependencies retain their licenses in `THIRD_PARTY_NOTICES.txt`; exact versions, source URLs, and npm integrity values are in `DEPENDENCIES.json`. Manrope is licensed under SIL OFL 1.1. Firefly names and graphic identities remain protected trademarks.
