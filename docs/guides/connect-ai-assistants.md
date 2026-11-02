<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
# Use koinon from your AI assistant

You can stay in your preferred assistant while using koinon as the repository for your organization's knowledge. The assistant calls koinon's MCP server to discover sources, retrieve evidence and carry out supported changes. Your koinon account determines which spaces and operations it can access.

This walkthrough helps you choose the right installation, connect your account and check the first result. You do not need to configure an AI model in koinon to install a client plugin; the external assistant uses its own model. The repository's search and ingestion services must still be configured for the operations you want to use.

## 1. Choose your client

| Where you work | What to set up | Detailed walkthrough |
| --- | --- | --- |
| Claude in the browser or its remote connector interface | A remote MCP connector with your own account | [Connect Claude](connect-claude.md) |
| Claude Desktop with a local extension | The branded MCPB, your installation URL and a scoped personal token | [Install the desktop extension](../integrations/desktop.md) |
| Claude Code | The koinon skills plugin and a separately configured connection, or an operator-generated connection profile | [Install the plugin](../integrations/plugins.md#install-in-claude-code) |
| ChatGPT | A custom MCP plugin and account linking; workspace administrators can also distribute the instruction plugin from GitHub | [Connect ChatGPT](connect-chatgpt.md) |
| Grok | A custom remote MCP connector; team provisioning may be required first | [Connect Grok](connect-grok.md) |
| Another MCP host | Its supported remote connection or MCPB installation method | [Authentication requirements](../operations/mcp-authentication.md) |

The **skill** teaches an assistant how to use evidence and handle changes. A **connection profile** identifies your server and its public client configuration. The **desktop extension** runs a local bridge. None of these supplies your account permissions. Choose the package your client supports; a Claude MCPB is not a ChatGPT or Grok installer.

## 2. Get your installation's connection details

Ask your administrator for the MCP URL shown by your installation, the supported connection method and the space you should use. Hosted clients need to reach that endpoint from their own infrastructure. A local URL working in your browser does not establish that a cloud client can reach it.

For OAuth, the operator registers the client and its exact callback first. You then sign in as yourself and review the requested access. For the desktop PAT bridge, create a personal token with only the intended scopes and space restrictions, and enter it in the extension's protected configuration. A personal token is not an OAuth client secret. Never paste either into a conversation or include it in a URL.

Follow the selected client's guide before continuing. If its authentication options do not support the server's pre-registered OAuth client, ask the operator to resolve that mismatch. Installing a different instruction package cannot repair account linking.

## 3. Install the instructions where supported

Use [Plugin marketplaces](../integrations/plugins.md) for Claude Code and ChatGPT workspace installation. The same canonical `koinon-evidence` skill is included in the portable skills archive. It explains retrieval, source attribution, catalog changes, publication review and uncertain outcomes.

For a host without a documented skill-package importer, use the workflow examples in its connection guide. Do not rename the archive to another extension or assume it installs as a native plugin. The [Grok guide](connect-grok.md) uses its documented custom-connector flow.

## 4. Confirm the connected account and evidence

Start with a source you know and can already open in Library. Ask:

> Use koinon to show which space I am connected to. Find the document I name, read the relevant passages and answer using only that evidence. Include the source and version identifiers. If you cannot find the answer, say what is missing.

Replace the document description with your own. The assistant should obtain scope from `koinon_context`, discover authorized IDs and retrieve the supporting content. Compare the cited source with Library. A plausible answer without a successful tool result does not verify the connection.

For structured data, ask for a calculation with a known result. The assistant should inspect the dataset schema before querying and preserve the returned source identity and SQL evidence. See [external-agent management](external-agent-management.md) for tool names, scopes and examples.

## 5. Try a change deliberately

First try a reversible organizational task, such as creating a clearly named test folder in an authorized project. Check its destination in Library. For an update, retrieve the current object first so the assistant can use the exact revision precondition; do not force a change over a newer revision.

Publishing generated knowledge or importing file content requires a separate review. Ask for a proposal, inspect the exact content and destination in the embedded review, and explicitly approve it. This needs a client that supports koinon's MCP Apps review. If the component is unavailable, the assistant must leave the knowledge unchanged. Account linking does not approve publication.

After an approved upload, check its processing status and retrieve the resulting content before treating it as searchable knowledge. A transfer acknowledgment is not proof that extraction and indexing finished. If the response is lost, inspect the existing operation rather than repeating the upload blindly.

## 6. Keep access current

OAuth connections appear under **Authorized applications** in your koinon account. Personal tokens are managed under **API tokens**. Review the selected space, permissions and expiry; reconnect or replace the appropriate credential when needed. Removing a plugin from a client does not revoke its server-side credential.

When validating a deployment, retain the client version, connection method, successful scope check, cited read result and outcome of each requested write. Also verify that a revoked grant is rejected on a new call. Keep tokens and client secrets out of screenshots and diagnostic records. The platform-specific guides distinguish repository tests from actual client sign-in and interaction.
