<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
# Desktop MCP extension

The firefly koinon 26.11.11 desktop extension connects a compatible MCP desktop host to an operator-managed koinon MCP endpoint. The bridge uses the official TypeScript MCP SDK and forwards remote tools, resources, and prompts. The server remains responsible for schemas, permissions, and knowledge access.

!!! note "Versioned installation instructions"
    These instructions target 26.11.11. Install only when its release page provides the MCPB and matching checksums. The 26.11.10 archive uses PAT authentication and cannot follow the browser sign-in steps below.

## Download the matching package

Download these files from the **same release**, 26.11.11, once its assets are published:

| Download | Use it for |
| --- | --- |
| [Claude Desktop extension (.mcpb)](https://github.com/fireflyframework/firefly-koinon/releases/download/v26.11.11/firefly-koinon-desktop-26.11.11.mcpb) | Install the branded local bridge in a compatible desktop host |
| [Portable skills (.zip)](https://github.com/fireflyframework/firefly-koinon/releases/download/v26.11.11/firefly-koinon-skills-26.11.11.zip) | Obtain the separate `koinon-evidence` instructions for a host with a supported skill installer |
| [SHA256SUMS](https://github.com/fireflyframework/firefly-koinon/releases/download/v26.11.11/SHA256SUMS) | Check that the downloaded files match the published artifacts |
| [Release notes and all assets](https://github.com/fireflyframework/firefly-koinon/releases/tag/v26.11.11) | Review the version, provenance and other distributions |

You do not need to clone the repository, install Python or build the extension. Keep the `.mcpb` filename and extension unchanged. The generic package contains no organization's URL or credential; you supply those during setup.

For a newer version, open [all releases](https://github.com/fireflyframework/firefly-koinon/releases) and select the MCPB and checksum file from that release together. The [plugin marketplace guide](plugins.md) covers Claude Code and ChatGPT GitHub imports, which use a different installation method.

## 1. Prepare your koinon account

Sign in to your organization's koinon installation and confirm that you can open the intended Library space. Your role must already permit the operations you want the assistant to perform.

Obtain the full HTTPS MCP endpoint, registered public OAuth client ID and callback port from your administrator. The endpoint ends in `/mcp`, for example `https://knowledge.example.org/mcp`. That is an example, not a hosted service. Your operator must enable MCP OAuth and register the extension's exact local callback before you connect. The defaults work only if that registration exists; see [operator setup](desktop-oauth.md#operator-setup).

The server must be reachable from the computer running Claude Desktop. Browser sign-in does not require copying a personal token. If your operator chooses PAT compatibility instead, follow [Create a personal access token](../guides/create-personal-token.md) and select `pat` during extension setup.

## 2. Check the downloaded file

Open a terminal in the directory where you saved the MCPB and `SHA256SUMS`. Calculate the file's SHA-256:

=== "macOS or Linux"

    ```sh
    shasum -a 256 firefly-koinon-desktop-26.11.11.mcpb
    ```

=== "Windows PowerShell"

    ```powershell
    Get-FileHash .\firefly-koinon-desktop-26.11.11.mcpb -Algorithm SHA256
    ```

Compare the result with the line for that exact filename in `SHA256SUMS`. It must match; letter case in a hexadecimal hash does not matter. If it differs, download the file again from the release before installing it. The checksum file includes other release assets, so checking every line would require downloading those other files too.

## 3. Open Claude Desktop's extension installer

1. Open Claude Desktop and its **Settings**.
2. Select **Desktop app**, then **Manage** beside **Extensions**. Older layouts place **Extensions** directly in Settings.
3. Open **Advanced settings** and find the **Extension Developer** section.
4. Choose **Install Extension…** and select the downloaded `firefly-koinon-desktop-26.11.11.mcpb`.
5. Review **firefly koinon**, its version and publisher before continuing.

These steps follow [Anthropic's custom desktop extension instructions](https://support.claude.com/en/articles/10949351-getting-started-with-local-mcp-servers-on-claude-desktop). An organization's desktop policy may require its owner to allow or distribute the extension first. The package needs Node.js 22 or later from the host; a separate Python environment is not required.

## 4. Configure browser sign-in

| Field in the installer | What to enter |
| --- | --- |
| **MCP endpoint** | Your installation's complete HTTPS URL ending in `/mcp`; include no token, query string or fragment |
| **Authentication mode** | `oauth` for browser sign-in |
| **Public OAuth client ID** | The public client ID registered by your operator; this is not a secret |
| **OAuth callback port** | The port in that registration's exact local callback |
| **Personal access token** | Leave empty in OAuth mode |

Complete the installation and enable the extension. Installation and tool discovery do not open a browser or grant access. The bundled installation preview illustrates PAT compatibility settings; it is explanatory artwork, not a screenshot of Claude Desktop or an OAuth installation.

For PAT compatibility, explicitly choose `pat` and enter your scoped personal access token in its sensitive field. OAuth mode rejects a configured PAT. Never place a credential in a conversation, screenshot, server URL or shared configuration file.

## 5. Sign in and verify the first connection

1. In a new Claude conversation, ask the assistant to run `koinon_desktop_connect`.
2. Open the returned authorization link yourself. It expires after two minutes; the assistant must not fetch it or approve consent for you.
3. Sign in to koinon and review the account, application, workspace and requested permissions. Initial access requests `catalog:read`.
4. After the browser confirms the connection, ask the assistant to run `koinon_desktop_status`. The host must refresh its tool list when notified; use its supported refresh control if needed.

Then ask:

> Use the koinon connection. Call `koinon_context` and tell me which space I can access. Then list the available sources without changing anything.

Compare the returned scope with the workspace you authorized. Next, ask about a document you can already open in Library, requesting its source and version. A trusted scope challenge can ask you to reconnect and consent to additional permissions. The bridge does not replay the original operation automatically; request it again only after consent succeeds. Current roles and resource permissions still apply.

Successful installation alone does not prove server access, evidence retrieval or acceptance in your particular Claude Desktop version. PAT mode skips the browser sign-in controls and uses the configured token's existing scopes.

For uploads or updates, follow [in-chat knowledge management](../guides/mcp-knowledge-management.md). You need the corresponding write permissions and a host that displays the explicit human-review component. No knowledge is published merely by installing the extension or enabling its tools.

## 6. Update, reconnect or disconnect

For an extension update, download and verify the new release's MCPB, then install it using the same custom-extension flow. This GitHub distribution does not promise automatic updates from Anthropic's directory. Review the saved endpoint and authentication mode afterward. Existing PAT installations must explicitly select `pat` when upgrading, or remove that token and configure browser sign-in.

OAuth tokens remain in bridge memory only. Reconnect after a restart, expiry or server revocation; there is no silent refresh. `koinon_desktop_disconnect` closes the local connection and forgets its token. To revoke the server grant, open **Authorized applications** in your koinon account and disconnect the entry. Disabling or removing the extension alone does not revoke it. Connecting another computer with the same client and workspace can replace the first computer's authorization; see [connection lifecycle](desktop-oauth.md#disconnect-and-revocation).

For PAT compatibility, replace an expiring token in the extension settings and revoke the old token under **API tokens**. Revoke an exposed credential immediately. PAT connections do not appear as OAuth grants under **Authorized applications**.

## If something does not work

| Symptom | Next step |
| --- | --- |
| Custom installation is unavailable | Check the Claude Desktop version and your organization's extension policy |
| Installed, but remote tools do not appear | Run `koinon_desktop_connect`, complete browser consent, then check `koinon_desktop_status`; verify the host refreshes its tool list |
| A request returns `401` | Reconnect in OAuth mode; for PAT mode, inspect the configured token’s expiry and revocation |
| A request returns `403` | Review the scopes, current role and selected workspace/file restrictions in koinon |
| The server cannot be reached | Check the computer's network access and the exact HTTPS `/mcp` URL |
| A knowledge change has no review panel | Leave content unchanged; the host must support the required review capability |

Use the extension's connection status and logs for diagnosis, keeping credentials out of any report. [Anthropic's troubleshooting guidance](https://support.claude.com/en/articles/10949351-getting-started-with-local-mcp-servers-on-claude-desktop) explains where these controls appear in current and older layouts.

## Reusable skill

The [portable skills archive](https://github.com/fireflyframework/firefly-koinon/releases/download/v26.11.11/firefly-koinon-skills-26.11.11.zip) includes `koinon-evidence`, which guides document retrieval, schema inspection, bounded dataset queries, answer audit interpretation, provenance, and citation. Install the folder through your assistant's supported skill mechanism. MCPB installation does not automatically install skills. A skill provides instructions and does not establish a connection or grant access. For Claude Code or a managed ChatGPT workspace, use the [documented plugin installation steps](plugins.md) instead of guessing an archive importer.

## ChatGPT and other MCP hosts

MCPB is a local desktop extension format. It does not provide a local archive installer or connector for ChatGPT. A ChatGPT remote MCP integration requires a reachable HTTPS endpoint and a host-supported authentication flow, typically OAuth. The local bridge’s public client and loopback callback do not configure a hosted connector.

Other compatible MCP hosts can launch the extracted `server/index.cjs` with Node.js, setting `KOINON_MCP_URL`, `KOINON_AUTH_MODE=oauth`, `KOINON_OAUTH_CLIENT_ID` and `KOINON_OAUTH_CALLBACK_PORT` through their environment configuration. Explicit PAT compatibility uses `KOINON_AUTH_MODE=pat` and `KOINON_TOKEN`. Keep tokens out of arguments, URLs, source control, and logs. Use the host's own policy and setup documentation to determine supported transports and authentication.

## Connection behavior

The bridge initializes locally. Explicit browser sign-in reads the configured installation’s OAuth metadata and token endpoints; authenticated MCP operations send a bearer token only to the configured MCP endpoint. It rejects redirects and URLs containing credentials, query parameters, or fragments. OAuth requests have a 10-second timeout; MCP requests have a 30-second timeout. HTTPS is required; an explicit environment-only loopback HTTP override exists for development and is absent from desktop configuration.

Read the [integration data flow and privacy notes](privacy.md) before connecting sensitive knowledge. For build instructions, packaging checks, and dependency provenance, see `integrations/mcp-desktop/README.md` in the repository.

## Reviewed knowledge management

A host without MCP Apps can still retrieve evidence and perform supported user-requested catalog organization, such as renaming, tagging or moving an ordinary folder. Those operations require the corresponding current scopes, role and resource access. They do not authorize content publication. Follow the [catalog operation walkthrough](../guides/external-agent-management.md) for exact timestamps, metadata replacement and recovery from an uncertain response.

A compatible host can render the remote server's embedded review for text creation/updates and file uploads. The bridge forwards tool results and resources; the host must preserve MCP Apps private metadata and app-only visibility. Installation alone does not establish that capability. The connection needs the exact write and supporting-evidence scopes, intersected with the current user's role and resource bounds. See [managing knowledge inside an MCP conversation](../guides/mcp-knowledge-management.md) and the dedicated [Claude](../guides/connect-claude.md) and [ChatGPT](../guides/connect-chatgpt.md) connection guides.

The [plugin marketplace and profile guide](plugins.md) explains GitHub distribution, canonical skills and deployment-specific OAuth metadata. Packages do not replace account authorization or supported human review.
