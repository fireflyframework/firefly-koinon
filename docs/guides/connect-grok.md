<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
# Connect Grok to koinon

Use your installation's remote HTTPS `/mcp` endpoint to let Grok discover koinon tools. The connection must use the actual user's identity and permissions. It does not turn Grok into an organization administrator or bypass a selected knowledge space.

Grok's official documentation supports adding a custom MCP connector under its connector settings. Business and Enterprise teams require administrator provisioning before members connect their accounts. The endpoint must be publicly reachable. These are documented host capabilities; they are not evidence that a particular koinon deployment and Grok account completed linking. See [Grok connectors](https://docs.x.ai/grok/connectors) and [connector management](https://docs.x.ai/grok/connector-management).

## Prepare authentication

Obtain the exact MCP URL and an operator-approved, pre-registered OAuth client from koinon's connection panel. Follow the host's actual authentication flow and register its exact displayed callback with the koinon administrator. koinon supports authorization code with PKCE and pre-registered clients; it does not implement automatic client registration. The reviewed Grok setup documentation does not establish every field needed for this pre-registered-client path. If the host cannot accept that setup, stop and report the compatibility gap instead of inventing a client ID, callback or credential.

Each user still signs in through the organization's identity provider and consents to the exact requested scopes and space. Never substitute a koinon PAT for an OAuth client secret, expose a token in the chat, or put credentials in the MCP URL. Scope and role changes constrain the next governed operation; revocation does not require restarting koinon.

## Start with a bounded task

After an actual connection succeeds, ask Grok to call `koinon_context`, browse authorized objects and inspect evidence before answering. For a user-requested folder operation, use the dedicated organization tools with the current IDs and timestamp preconditions. See [external-agent management](external-agent-management.md) for the exact read/write boundary.

The reviewed documentation does not establish Grok support for the specific MCP Apps private-review extension used by koinon's content and file publication workflow. Without negotiated support, those operations remain unavailable. Ordinary reads and permitted catalog organization do not require that review extension.

For agents built on the remote-MCP API, Grok documents explicit server URL, authorization and allowed-tool settings. Its `require_approval` parameter is not supported; that API setting cannot be used as proof of a human approval. See [remote MCP tools](https://docs.x.ai/developers/tools/remote-mcp). Do not automatically repeat an uncertain write or treat a model response as publication approval.

Validate actual account linking, scope denial, read results, role revocation and each required interaction in the intended client before describing the integration as accepted. No Grok credential, connector or live session was created by the repository's local protocol tests.
