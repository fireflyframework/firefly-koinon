<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
# Desktop MCP extension

The firefly koinon 26.11.10 desktop extension connects a compatible MCP desktop host to an operator-managed koinon MCP endpoint. The bridge uses the official TypeScript MCP SDK and forwards remote tools, resources, and prompts. The server remains responsible for schemas, permissions, and knowledge access.

## Download the published package

Download these files from the **same release**, currently 26.11.10:

| Download | Use it for |
| --- | --- |
| [Claude Desktop extension (.mcpb)](https://github.com/fireflyframework/firefly-koinon/releases/download/v26.11.10/firefly-koinon-desktop-26.11.10.mcpb) | Install the branded local bridge in a compatible desktop host |
| [Portable skills (.zip)](https://github.com/fireflyframework/firefly-koinon/releases/download/v26.11.10/firefly-koinon-skills-26.11.10.zip) | Obtain the separate `koinon-evidence` instructions for a host with a supported skill installer |
| [SHA256SUMS](https://github.com/fireflyframework/firefly-koinon/releases/download/v26.11.10/SHA256SUMS) | Check that the downloaded files match the published artifacts |
| [Release notes and all assets](https://github.com/fireflyframework/firefly-koinon/releases/tag/v26.11.10) | Review the version, provenance and other distributions |

You do not need to clone the repository, install Python or build the extension. Keep the `.mcpb` filename and extension unchanged. The generic package contains no organization's URL or credential; you supply those during setup.

For a newer version, open [all releases](https://github.com/fireflyframework/firefly-koinon/releases) and select the MCPB and checksum file from that release together. The [plugin marketplace guide](plugins.md) covers Claude Code and ChatGPT GitHub imports, which use a different installation method.

## 1. Prepare your koinon account

Sign in to your organization's koinon installation. In Library, select the workspace you want Claude to use. Open your avatar menu, choose **API tokens**, and select **Create a token**. Follow [Create a personal access token](../guides/create-personal-token.md) for each field, scope selection, expiry and the one-time copy step.

For document retrieval, select **Browse knowledge** and **Search documents**. Add **Query datasets** only when you need structured queries. Use **Limit to current workspace** for a connection restricted to that workspace. Your role must already permit the requested operations.

Copy the new secret into a password manager until you enter it in the extension. A model-provider API key, OAuth client secret or token prefix from the list is not a personal access token. Each person should create their own credential.

Obtain the full HTTPS MCP endpoint from your administrator or the installation's MCP connection panel. It ends in `/mcp`, for example `https://knowledge.example.org/mcp`. That is an example, not a hosted service. The server must have MCP enabled and be reachable from the computer running Claude Desktop.

## 2. Check the downloaded file

Open a terminal in the directory where you saved the MCPB and `SHA256SUMS`. Calculate the file's SHA-256:

=== "macOS or Linux"

    ```sh
    shasum -a 256 firefly-koinon-desktop-26.11.10.mcpb
    ```

=== "Windows PowerShell"

    ```powershell
    Get-FileHash .\firefly-koinon-desktop-26.11.10.mcpb -Algorithm SHA256
    ```

Compare the result with the line for that exact filename in `SHA256SUMS`. It must match; letter case in a hexadecimal hash does not matter. If it differs, download the file again from the release before installing it. The checksum file includes other release assets, so checking every line would require downloading those other files too.

## 3. Open Claude Desktop's extension installer

1. Open Claude Desktop and its **Settings**.
2. Select **Desktop app**, then **Manage** beside **Extensions**. Older layouts place **Extensions** directly in Settings.
3. Open **Advanced settings** and find the **Extension Developer** section.
4. Choose **Install Extension…** and select the downloaded `firefly-koinon-desktop-26.11.10.mcpb`.
5. Review **firefly koinon**, its version and publisher before continuing.

These steps follow [Anthropic's custom desktop extension instructions](https://support.claude.com/en/articles/10949351-getting-started-with-local-mcp-servers-on-claude-desktop). An organization's desktop policy may require its owner to allow or distribute the extension first. The package needs Node.js 22 or later from the host; a separate Python environment is not required.

## 4. Fill in the two connection fields

| Field in the installer | What to enter |
| --- | --- |
| **MCP endpoint** | Your installation's complete HTTPS URL ending in `/mcp`; include no token, query string or fragment |
| **Personal access token** | The full secret copied when you created the token in koinon |

Complete the installation and enable the extension. Its token field is marked sensitive so the host can use protected storage. Do not place the token in a conversation, screenshot, server URL or shared configuration file.

The branded installation preview shipped in the archive illustrates these settings. It is explanatory artwork, not a screenshot of Claude Desktop or proof of a completed installation.

## 5. Verify the first connection

In a new Claude conversation, use its connector/tool controls to check that koinon is available. Ask:

> Use the koinon connection. Call `koinon_context` and tell me which space I can access. Then list the available sources without changing anything.

Review the actual tool result and compare the returned scope with the workspace selected when creating the token. Next, ask a question about a document you can already open in Library, requesting its source and version. Successful installation alone does not prove server access or evidence retrieval.

For uploads or updates, follow [in-chat knowledge management](../guides/mcp-knowledge-management.md). You need the corresponding write permissions and a host that displays the explicit human-review component. No knowledge is published merely by installing the extension or enabling its tools.

## 6. Update, replace a token or disconnect

For an extension update, download and verify the new release's MCPB, then install it using the same custom-extension flow. This GitHub distribution does not promise automatic updates from Anthropic's directory. Review the saved endpoint and token afterward and repeat the scope check.

For an expiring or lost token, create a replacement in koinon, open **firefly koinon** in Claude's extension settings and replace **Personal access token**. Verify the new credential, then revoke the old one. If the old credential was exposed, revoke it immediately instead of waiting for the replacement check.

To disconnect, revoke the token in koinon's **API tokens** list and disable or remove the extension in Claude. This PAT connection is managed under **API tokens**, not **Authorized applications**, which is for OAuth grants.

## If something does not work

| Symptom | Next step |
| --- | --- |
| Custom installation is unavailable | Check the Claude Desktop version and your organization's extension policy |
| Installed, but no tools appear | Confirm both fields, enable the extension, and restart Claude Desktop if its registry needs refreshing |
| A request returns `401` | Check token expiry/revocation and use the complete secret, not the visible prefix |
| A request returns `403` | Review the scopes, current role and selected workspace/file restrictions in koinon |
| The server cannot be reached | Check the computer's network access and the exact HTTPS `/mcp` URL |
| A knowledge change has no review panel | Leave content unchanged; the host must support the required review capability |

Use the extension's connection status and logs for diagnosis, keeping credentials out of any report. [Anthropic's troubleshooting guidance](https://support.claude.com/en/articles/10949351-getting-started-with-local-mcp-servers-on-claude-desktop) explains where these controls appear in current and older layouts.

## Reusable skill

The [portable skills archive](https://github.com/fireflyframework/firefly-koinon/releases/download/v26.11.10/firefly-koinon-skills-26.11.10.zip) includes `koinon-evidence`, which guides document retrieval, schema inspection, bounded dataset queries, answer audit interpretation, provenance, and citation. Install the folder through your assistant's supported skill mechanism. MCPB installation does not automatically install skills. A skill provides instructions and does not establish a connection or grant access. For Claude Code or a managed ChatGPT workspace, use the [documented plugin installation steps](plugins.md) instead of guessing an archive importer.

## ChatGPT and other MCP hosts

MCPB is a local desktop extension format. It does not provide a local archive installer or connector for ChatGPT. A ChatGPT remote MCP integration requires a reachable HTTPS endpoint and a host-supported authentication flow, typically OAuth. The current personal-access-token bridge does not implement OAuth.

Other compatible MCP hosts can launch the extracted `server/index.cjs` with Node.js, setting `KOINON_MCP_URL` and `KOINON_TOKEN` through secure environment configuration. Keep tokens out of arguments, URLs, source control, and logs. Use the host's own policy and setup documentation to determine supported transports and authentication.

## Connection behavior

The bridge initializes locally and contacts the configured endpoint only when the host requests tools, resources, or prompts. It rejects redirects and URLs containing credentials, query parameters, or fragments. Requests use a 30-second timeout. HTTPS is required; an explicit environment-only loopback HTTP override exists for development and is absent from desktop configuration.

Read the [integration data flow and privacy notes](privacy.md) before connecting sensitive knowledge. For build instructions, packaging checks, and dependency provenance, see `integrations/mcp-desktop/README.md` in the repository.

## Reviewed knowledge management

A host without MCP Apps can still retrieve evidence and perform supported user-requested catalog organization, such as renaming, tagging or moving an ordinary folder. Those operations require the corresponding current scopes, role and resource access. They do not authorize content publication. Follow the [catalog operation walkthrough](../guides/external-agent-management.md) for exact timestamps, metadata replacement and recovery from an uncertain response.

A compatible host can render the remote server's embedded review for text creation/updates and file uploads. The bridge forwards tool results and resources; the host must preserve MCP Apps private metadata and app-only visibility. Installation alone does not establish that capability. A PAT needs the exact write and supporting-evidence scopes, intersected with the current user's role and resource bounds. See [managing knowledge inside an MCP conversation](../guides/mcp-knowledge-management.md) and the dedicated [Claude](../guides/connect-claude.md) and [ChatGPT](../guides/connect-chatgpt.md) connection guides.

The [plugin marketplace and profile guide](plugins.md) explains GitHub distribution, canonical skills and deployment-specific OAuth metadata. Packages do not replace account authorization or supported human review.
