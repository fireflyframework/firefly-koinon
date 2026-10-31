<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
# Connect ChatGPT to koinon

Use koinon's remote MCP endpoint to retrieve organization knowledge from ChatGPT, inspect datasets and retain source references. Each user connects with their own identity and an explicitly scoped authorization. The remote connector is separate from the branded Claude Desktop MCPB; ChatGPT does not install that archive.

## Prepare the connection

Open your koinon avatar menu, select **Authorized applications**, then **Connect an app**. The connection panel provides:

- The installation's exact MCP URL. A hosted ChatGPT connection requires a reachable HTTPS address, such as `https://knowledge.example.org/mcp`.
- The enabled OAuth client registrations for your current organization and their client IDs.

An organization administrator [registers the application](register-applications.md) under **Settings**, in **Applications**, and supplies any confidential client secret through a protected channel. Confirm the intended organization, space and operations before connecting. Client registration does not grant membership or additional permissions.

The domain above is an example, not a supplied hosted service. The product can also display a listener-derived local endpoint marked `local_only`; that address is for the local computer and cannot serve ChatGPT cloud connections. Use a reachable HTTPS deployment URL for this connection. The server uses Streamable HTTP. Compatible legacy clients negotiate MCP Apps during initialization; modern clients can declare capabilities per request. Its public URL and OAuth resource must match exactly. Deployment, identity-provider login and client availability must be verified in your environment.

koinon currently supports OAuth authorization-code exchange with PKCE S256 and pre-registered clients. It does not advertise automatic dynamic registration, Client ID Metadata Documents, refresh tokens or machine-to-machine grants. Select the client's static OAuth configuration. OpenAI documents predefined clients and exact callback registration in its [authentication guide](https://developers.openai.com/plugins/build/auth). If your workspace exposes no compatible configuration, request operator support rather than selecting unauthenticated access.


<figure class="doc-guide-shot">
  <a href="../../assets/screenshots/mcp-connection.png"><img src="../../assets/screenshots/mcp-connection.png" alt="koinon Authorized applications connection panel with an MCP URL, registered application and OAuth client ID" width="1440" height="1100" loading="lazy"></a>
  <figcaption>Controlled koinon connection panel, with ChatGPT selected as an example. Choose your intended chat application and use your own installation's values. This image does not show a completed external connection.</figcaption>
</figure>

## Add the custom MCP server

<figure class="connection-illustration">
  <figcaption><strong>Illustrative setup</strong><span>Field reference for ChatGPT. This is an editable illustration, not a vendor screenshot or a completed connection.</span></figcaption>
  <div class="connection-example">
    <h3>Add custom MCP server</h3>
    <p>Start in <strong>ChatGPT Plugins</strong>.</p>
    <dl class="connection-fields">
      <div><dt>Name</dt><dd>koinon</dd></div>
      <div><dt>Server URL</dt><dd><code>https://knowledge.example.org/mcp</code><small>Example only. Use your operator's reachable HTTPS URL.</small></dd></div>
      <div><dt>Authentication</dt><dd>OAuth<small>Use your pre-registered client's static credentials in the host's protected settings.</small></dd></div>
      <div><dt>Callback</dt><dd>Register the exact callback ChatGPT displays<small>Have your operator allow that exact value before account linking.</small></dd></div>
    </dl>
    <p class="connection-next">Choose <strong>Create as a plugin</strong>, install it, then select <code>@koinon</code> in the conversation.</p>
  </div>
</figure>


The current official web flow starts from **ChatGPT Plugins**: add a custom MCP server, enter its name and URL, configure OAuth, review the requested setup and create the plugin. Install the resulting plugin before invoking it with `@` in a conversation. Workspace controls may restrict this capability. See [OpenAI's current custom MCP setup](https://developers.openai.com/api/docs/guides/custom-mcp-server).

Name the integration **koinon** and use the supplied `/mcp` URL. Enter its pre-registered OAuth client credentials in protected settings. Copy the exact callback shown by ChatGPT to your operator for registration; do not copy a callback from an unrelated example. koinon does not claim the newer stable-callback issuer-identification extension, so let ChatGPT choose the callback for the actual server configuration. OpenAI explains these [callback requirements](https://developers.openai.com/plugins/build/auth).

A personal API token cannot be substituted for an OAuth client secret. This ChatGPT flow uses OAuth; koinon's PAT option is for an MCP host that explicitly supports a bearer header. Never send a secret as a tool argument or include one in the server URL.


<details class="connection-reference">
  <summary>Administrator reference: registration is separate from user consent</summary>
  <figure class="doc-guide-shot doc-guide-shot--mobile">
    <a href="../../assets/screenshots/oauth-application-review-mobile.png"><img src="../../assets/screenshots/oauth-application-review-mobile.png" alt="Controlled mobile application-registration review showing callback URLs, allowed access and an unchecked administrator confirmation" width="390" height="1100" loading="lazy"></a>
    <figcaption>Controlled administrator registration review. This defines the application and its allowed access; it is not the user's OAuth consent screen.</figcaption>
  </figure>
  <p><a href="../register-applications/">Read application registration</a> for the operator workflow. Each user still signs in and reviews their own access.</p>
</details>

## Sign in and review access

When linking the account or invoking a tool that requires it, follow the sign-in flow to koinon. The existing organization identity provider authenticates you. Verify the account name/avatar, requesting application, readable permissions and selected organization and space before choosing **Connect**. Choose **Cancel** to deny the request.

The initial authorization can be limited to `catalog:read`. Search requires `knowledge:search`, queries require `query:execute`, and an existing-answer audit requires `chat:use`, in addition to catalog access. Reviewed text and file changes additionally require `catalog:write` and `ingest:write`. The tool metadata declares these requirements. A verified scope-only denial can ask the host to relink with the relevant scopes. Current role, organization, workspace and asset restrictions still apply; a scope upgrade cannot override them.

The tool schemas may appear in discovery even when a particular operation is unavailable to your grant. Permission checks run at invocation. See [MCP authentication](../operations/mcp-authentication.md) for operator registration and [Authorized applications](authorized-applications.md) for owner controls.

## Retrieve and verify knowledge

Select `@koinon` in the conversation and start with:

> Use only koinon for this knowledge request. Call `koinon_context` to identify my authorized organization and space. Then browse with `koinon_list` if needed; do not infer IDs from names.

For document evidence:

> Find the service-renewal policy with `koinon_search`. Read the matching document passages with `koinon_fetch` before answering. Cite the source IDs and versions that actually support the answer, and describe any gaps.

For structured data:

> Inspect `koinon_dataset_schema` for the selected dataset, then call `koinon_query` for the requested calculation. Include the recorded SQL, underlying source identity, snapshot information and any row limits. Do not change the dataset.

The complete [MCP tool catalog](../architecture/mcp.md) distinguishes catalog entries, document IDs, curated versions, datasets and table snapshots. Pass IDs returned by authorized operations. `koinon_fetch` with `kind="document"` reads the current canonical extraction; `kind="knowledge_item"` can request an exact curated version. `koinon_provenance` reads lineage or the exact dataset/table/snapshot relationship. Never substitute a dataset's native ID for its canonical catalog ID.

Search returns evidence without generating a koinon answer. ChatGPT generates its response from those results; this does not create a koinon chat run. `koinon_answer_audit` can inspect an existing run owned by the authenticated user, not an arbitrary ChatGPT conversation. Retain missing provenance as unknown; a tool result or audit record is not a guarantee that the model interpreted it correctly.

## Approve knowledge changes inside the conversation

Ask ChatGPT for the exact proposed change:

> Propose a draft using the source passages we just retrieved. Include the koinon read receipt IDs, preserve the source references and show the destination and exact text for my review. Do not approve it for me.

`koinon_stage_knowledge` returns an embedded review. Inspect its destination, action, before/after content and evidence, select the explicit approval checkbox, then choose **Approve** or **Cancel**. `koinon_prepare_file_upload` opens a file picker in the conversation; the component computes the actual file's size and SHA-256, transfers bounded chunks and presents a verified review before ingestion. It does not ask the model to invent a file digest or fetch an arbitrary download URL.

<figure class="doc-guide-shot">
  <a href="../../assets/screenshots/mcp-file-review.png"><img src="../../assets/screenshots/mcp-file-review.png" alt="koinon file review in a controlled MCP Apps host, showing selected file bytes, SHA-256, destination and explicit import approval" width="900" height="1100" loading="lazy"></a>
  <figcaption>koinon's file review in a controlled MCP Apps host, before importing. The verified file details are example data; this is not a ChatGPT screenshot or an accepted external upload.</figcaption>
</figure>

The implementation uses [MCP Apps](https://developers.openai.com/plugins/build/app-quickstart). A private nonce is delivered only to the component, outside model-visible content, and approval/cancellation actions are app-only. Account-linking consent is separate from the decision to save a particular proposal. The external assistant's prose remains an unverified external proposal, including when exact repository-source ancestry is available.

Read [the complete workflow and limits](mcp-knowledge-management.md), including unchanged-source checks, retries and incomplete ingestion. If the host cannot show the review, leave the repository unchanged and explain the limitation in the conversation. No automatic browser approval redirect or autonomous confirmation tool is provided. Actual ChatGPT rendering and deployed account-linking must be tested separately from local SDK/protocol checks.

## Disconnect and expiry

In koinon, open the avatar menu and select **Authorized applications**. Review the ChatGPT application's selected space, permissions and expiration, then choose **Revoke access** when appropriate. Revocation disables the associated credential; current membership changes also constrain the next governed operation. Removing the plugin in ChatGPT alone does not notify koinon.

Reconnecting the same application to the same space replaces its active grant with the newly approved access. It does not merge permissions or alter another space. This release does not issue refresh tokens; reconnect after expiry. Keep manually issued tokens under the separate **API tokens** page.

## Troubleshooting and acceptance

| Symptom | Action |
| --- | --- |
| Custom MCP setup is unavailable | Ask the ChatGPT workspace administrator about current plugin permissions and availability |
| The URL fails discovery | Check HTTPS reachability, exact `/mcp` URL and operator configuration; a laptop-local address is not a reachable remote deployment |
| OAuth fails registration or callback checks | Use the static client provided by the operator and ChatGPT's exact displayed callback; koinon has no DCR or CIMD endpoint |
| Linking repeatedly asks for permissions | Check the registered client's allowed scopes and current user role; do not repeatedly widen access |
| Tools return `401` or `403` | Check expiry, revocation, current role and selected space; API JWTs and browser cookies are not direct MCP credentials |
| Results are too large | Narrow the query, source range or page; oversized evidence is rejected rather than silently truncated |
| An upload or update tool is absent | Check the deployed server version, permitted write scopes and MCP Apps support; leave the repository unchanged when in-chat review is unavailable |

Local tests cover official MCP protocol initialization/discovery, native scope enforcement, PKCE, owner-only consent, token isolation, expiry and revocation. They do not prove that an actual ChatGPT account completed OAuth or accepted a deployed server. Retain the real client connection result separately from package and protocol tests.

The official setup pages were checked on October 30, 2026. This guide describes their current web flow without assuming a particular subscription or workspace policy. The local MCPB and portable evidence skill remain separate artifacts; neither installs a ChatGPT OAuth connection.
