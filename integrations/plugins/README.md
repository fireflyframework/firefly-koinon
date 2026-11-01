<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
# koinon plugin packages and marketplace

An external agent connects to your installation's koinon MCP endpoint as the user. The server checks current membership, role, scopes and selected space on each operation. A plugin supplies instructions and connection metadata; it cannot grant access or approve a content change.

The repository marketplace contains a **skills-only** plugin with the canonical koinon instructions and branded assets. It includes no universal server URL, token, client secret or application ID. Configure a hosted OAuth connection to your own installation separately. The existing [desktop extension](../mcp-desktop/README.md) remains a separate PAT alternative.

## Choose a package

| Package | Contents | Connection setup |
| --- | --- | --- |
| Repository marketplace | Portable root `plugin.json`, Claude-compatible manifest, shared skills, icons and legal notices | Connect your own installation separately |
| Generated Claude Code profile | Shared skills and `.mcp.json` with an exact HTTPS URL, public client ID, callback port and explicit scopes | Operator registers the exact localhost callback; the user completes OAuth |
| Generated portable profile | Root `plugin.json` and `mcp.json` with an exact HTTPS URL and documented provided-client OAuth settings | Host account linking and workspace policy still apply |
| Optional registered-app reference | Shared skills and `.app.json` referencing an operator-supplied existing technical app ID | Does not create or verify an app, grant access or guarantee web availability |

Cloud Claude connectors use their host's redirect and account setup. Do not assume a Claude Code localhost callback profile configures a cloud connector. For ChatGPT, imported plugins declaring MCP servers may be marked **Desktop only**, even with an HTTPS URL. Adding an app reference does not guarantee that label disappears. These distinctions follow the [Claude MCP reference](https://code.claude.com/docs/en/mcp), [OpenAI packaging reference](https://developers.openai.com/plugins/build/plugins) and [ChatGPT marketplace guide](https://learn.chatgpt.com/docs/enterprise/plugin-management).

## Install or sync from GitHub

For Claude Code, register the repository marketplace and select the koinon plugin through the client's plugin controls:

```text
/plugin marketplace add fireflyframework/firefly-koinon
/plugin install koinon@firefly-koinon
```

The catalog lives at the repository root in `.claude-plugin/marketplace.json`; its entry points to `integrations/plugins/catalog/koinon`. Review the repository and chosen revision before installation. Use a client version that supports the declared manifest fields.

In a ChatGPT workspace, an authorized workspace administrator can import `https://github.com/fireflyframework/firefly-koinon` under **Admin > Plugins**, leaving **Path** empty. Choose a branch for subsequent updates, or a tag/commit to pin the source. Importing and syncing does not configure application access or link members' accounts. Workspace policy and individual account authorization remain separate. [Import and sync instructions](https://learn.chatgpt.com/docs/enterprise/plugin-management).

Use the client's sync/update controls after reviewing a source change. Removing a plugin is separate from revoking its credentials: revoke the authorized application in koinon, or revoke the separately issued PAT, when access should end. No command in this repository writes global client settings or performs an account login.

## Build a deployment-specific profile offline

The builder uses Python, Pydantic and JSON Schema validation. Run it in an isolated environment with `pydantic>=2.14.1,<3` and `jsonschema==4.26.0`. It performs no network discovery, registration, credential acquisition or server request.

Obtain the exact HTTPS MCP endpoint and a registered **public** OAuth client ID from your operator. For Claude Code, register the selected callback port as `http://localhost:8765/callback` in this example. Keep callback and client registration consistent with the actual host. Write a JSON profile using your own public configuration values:

```json
{
  "name": "team",
  "server_url": "https://knowledge.example.com/mcp",
  "public_client_id": "YOUR_REGISTERED_PUBLIC_CLIENT_ID",
  "callback_port": 8765,
  "scopes": ["catalog:read"]
}
```

The URL and client identifier above are placeholders, not a registered service. Profiles reject credentials, client secrets, URL user information, query strings, fragments and unsupported scope names. The default scope is only `catalog:read`. If the user needs organizational writes, the operator may explicitly include `catalog:write`; the user must still authorize the requested scope and possess the required role and space grant. The builder never adds it automatically.

Build into a new directory:

```sh
python integrations/plugins/plugin_build.py --profile /protected/team-profile.json --output /protected/team-plugin-build
```

An existing output directory is rejected. Keep generated deployment profiles under your operator's control; they contain your installation URL and public client metadata. The directory contains the profile variants, deterministic ZIPs, `SHA256SUMS`, and `BUILD.json` with per-file hashes and validation results. No secret is written into a package.

Only request `--include-existing-app` after adding an `application_id` copied from an existing host registration to the profile. The builder validates its shape; it does not contact the host to prove the registration exists. Never invent that identifier. Omit the option when no existing registration is available.

## Validation and portability limits

The exact published Agent Plugins 1.0.0 schemas are preserved under `schemas/`, with origin hashes and upstream license attribution. The portable plugin manifest is validated against that schema. The generic marketplace package has no MCP server configuration.

There is a current schema discrepancy: the OpenAI documentation places provided-client authentication in a server's `extensions.com.openai.auth`, while the published Agent Plugins 1.0.0 MCP schema rejects additional server properties. The generated portable OAuth profile therefore receives **two separate checks**: the exact portable MCP base, and a strict bounded local contract for the documented host extension. `BUILD.json` explicitly does not claim full MCP standard conformance for that variant. The OAuth configuration remains present in the package. See [the official provided-client fields](https://developers.openai.com/plugins/build/plugins).

Local qualification with Claude Code 2.1.260 accepts the manifest with an `icon` warning. The [current reference](https://code.claude.com/docs/en/plugins-reference) documents that field, and notes that older validators warn and lack newer MCP checks. This is not proof of import, account linking or tools working in a real client.

The skill distinguishes ordinary user-requested organization from publication of AI-derived content. Exact timestamps and parent checks remain required; an unknown create result must not be automatically retried. Content and file publication keep their explicit MCP Apps review requirement. Hosts without that review capability can use supported reads and catalog organization, but cannot complete those publication operations. [Operation and policy guide](../../docs/guides/external-agent-management.md).

## Maintain canonical inputs

The checked-in catalog is generated from `integrations/mcp-desktop/skills`, canonical brand exports and the existing desktop package version. Do not hand-edit copied skill or icon files. Check parity, or explicitly refresh the tracked generated catalog after reviewing an input change:

```sh
python integrations/plugins/plugin_build.py --check-catalog
python integrations/plugins/plugin_build.py --refresh-catalog
python -m pytest integrations/plugins/tests -q
```

Refreshing the source catalog updates only its declared generated inventory and rejects unexpected files. Deployment output directories are always new. The desktop extension's runtime and packaging scripts remain unchanged.
