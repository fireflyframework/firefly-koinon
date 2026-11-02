<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
# Connect Grok to koinon

Use your installation's remote HTTPS `/mcp` endpoint to let Grok discover koinon tools. The connection must use the actual user's identity and permissions. It does not turn Grok into an organization administrator or bypass a selected knowledge space.

Grok's official documentation supports adding a custom MCP connector under its connector settings. Business and Enterprise teams require administrator provisioning before members connect their accounts. The endpoint must be publicly reachable. These are documented host capabilities; they are not evidence that a particular koinon deployment and Grok account completed linking. See [Grok connectors](https://docs.x.ai/grok/connectors) and [connector management](https://docs.x.ai/grok/connector-management).

## Prepare authentication

Obtain the exact MCP URL and an operator-approved, pre-registered OAuth client from koinon's connection panel. Follow the host's actual authentication flow and register its exact displayed callback with the koinon administrator. koinon supports authorization code with PKCE and pre-registered clients; it does not implement automatic client registration. The reviewed Grok setup documentation does not establish every field needed for this pre-registered-client path. If the host cannot accept that setup, stop and report the compatibility gap instead of inventing a client ID, callback or credential.

Each user still signs in through the organization's identity provider and consents to the exact requested scopes and space. Never substitute a koinon PAT for an OAuth client secret, expose a token in the chat, or put credentials in the MCP URL. Scope and role changes constrain the next governed operation; revocation does not require restarting koinon.

## Add the connector step by step

1. For a Business or Enterprise team, ask a team administrator to open the cloud console, select the team, then open **Grok Business** and **Connectors**. Choose **Add Connector**, select **Other**, and supply the installation's MCP URL. Complete the supported authentication setup.
2. Open [Grok connectors](https://grok.com/connectors) with your own account. For an individually configured connector, choose **New Connector**, then **Custom**, and enter the same MCP URL. For a managed team, select the connector your administrator made available.
3. Complete the offered authentication flow. If the required pre-registered client or callback cannot be configured, stop here and ask the operator to resolve compatibility.
4. At koinon's consent screen, check your account, the requesting application, selected space and requested permissions before connecting.
5. Start a conversation and ask Grok to use the koinon connector explicitly. Verify the returned scope before retrieving documents.

The navigation above follows [Grok's connector setup](https://docs.x.ai/grok/connectors) and [team provisioning instructions](https://docs.x.ai/grok/connector-management). It does not establish support for koinon's complete OAuth or embedded-review contract in your particular account. The repository does not distribute a Grok-specific MCPB or claim a native Grok skill installer.

## Start with a bounded task

After an actual connection succeeds, ask Grok to call `koinon_context`, browse authorized objects and inspect evidence before answering. For a user-requested folder operation, use the dedicated organization tools with the current IDs and timestamp preconditions. See [external-agent management](external-agent-management.md) for the exact read/write boundary.

For the first read, choose a document you can already open in Library:

> Use koinon only for this request. Find the policy I name, read the relevant passages and explain what it says. Cite the returned source and version. Tell me if the evidence is missing or I cannot access it.

For a catalog task:

> In the project I select, propose creating a collection named Research notes. Show its exact parent before creating it, and report the returned identifier afterward. Do not publish new knowledge content.

An assistant's prose is not a receipt. Confirm the source or changed catalog entry in koinon, and leave an uncertain result unresolved until the existing state has been inspected.

The reviewed documentation does not establish Grok support for the specific MCP Apps private-review extension used by koinon's content and file publication workflow. Without negotiated support, those operations remain unavailable. Ordinary reads and permitted catalog organization do not require that review extension.

For agents built on the remote-MCP API, Grok documents explicit server URL, authorization and allowed-tool settings. Its `require_approval` parameter is not supported; that API setting cannot be used as proof of a human approval. See [remote MCP tools](https://docs.x.ai/developers/tools/remote-mcp). Do not automatically repeat an uncertain write or treat a model response as publication approval.

Validate actual account linking, scope denial, read results, role revocation and each required interaction in the intended client before describing the integration as accepted. No Grok credential, connector or live session was created by the repository's local protocol tests.

## Disconnect or resolve an error

Revoke your OAuth grant under koinon's **Authorized applications**, then remove or disable the Grok connector. Removing it only from Grok does not guarantee revocation in koinon. For an API integration using a personal token, revoke that token under **API tokens** instead.

| What you see | What to check |
| --- | --- |
| The team connector is missing | Team provisioning and whether you selected the correct Grok account/team |
| The endpoint cannot be reached | The exact HTTPS URL and reachability from the hosted client |
| Account linking fails | The registered client, exact callback, PKCE and host compatibility |
| A tool returns `401` | Credential expiry or revocation; reconnect through the supported flow |
| A tool returns `403` | Current role, scopes and access to the selected space and resource |
| A proposal has no review component | Do not publish; the client must support the required MCP Apps review |
