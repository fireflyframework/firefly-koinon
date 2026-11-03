<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
# Plugin marketplaces and connection profiles

Use a plugin to distribute koinon skills and reviewed connection metadata. The external agent still connects to your installation's MCP endpoint as the user, within current roles, scopes and space grants. Installing or syncing a plugin does not grant permissions or approve a knowledge change.

The GitHub marketplace at `fireflyframework/firefly-koinon` provides a skills-only plugin with koinon's canonical icons and instructions. It has no universal server URL or credential. Configure your installation's hosted OAuth connection separately. An operator can also build deployment-specific profiles containing the exact HTTPS URL and registered public client identifier, without packaging secrets.

| Client surface | Available package path | Remaining setup |
| --- | --- | --- |
| Claude Code | Repository marketplace or generated Claude-compatible profile | Exact registered client/callback and user OAuth sign-in |
| Claude remote/account connector | Shared skills plus a separately configured connector | Host redirect registration, account linking and supported review capability |
| ChatGPT workspace | GitHub marketplace import or generated portable package | Workspace policy and account linking; imported MCP profiles may be Desktop only |
| Desktop host supporting MCPB | Versioned desktop extension | HTTPS endpoint, operator-registered OAuth client and browser sign-in; explicit PAT compatibility |

For Grok, follow the [custom connector guide](../guides/connect-grok.md). The reviewed Grok documentation does not define an importer for these skill/plugin archives. The remote MCP connection remains the supported documented path.

## Install in Claude Code

The install source is the [koinon GitHub marketplace repository](https://github.com/fireflyframework/firefly-koinon). You do not download the desktop MCPB for this route. If you need the independent instruction files, download the [26.11.11 skills archive](https://github.com/fireflyframework/firefly-koinon/releases/download/v26.11.11/firefly-koinon-skills-26.11.11.zip) and its [checksums](https://github.com/fireflyframework/firefly-koinon/releases/download/v26.11.11/SHA256SUMS) once that release’s assets are published. Use an archive only with a host's documented skill installer.

1. Open Claude Code in the intended account and choose whether the plugin belongs to you or to the project, according to your team's policy.
2. Add the koinon marketplace and install its instruction plugin:

    ```text
    /plugin marketplace add fireflyframework/firefly-koinon
    /plugin install koinon@firefly-koinon
    ```

3. Review the installed plugin in the client's plugin controls. It should include the `koinon-evidence` skill. It does not include a shared server URL or token.
4. Configure the installation's MCP connection separately, or use the operator-generated profile described below. Complete your own OAuth sign-in.
5. Ask the assistant to call `koinon_context` and verify the returned space before asking it to retrieve a known source.

These commands follow the [Claude plugin installation guide](https://code.claude.com/docs/en/discover-plugins). Installing the skill and successfully authenticating to the server are separate checks.

## Install in a ChatGPT workspace

1. Have an authorized workspace administrator open **Admin**, then **Plugins**, and choose the GitHub import option.
2. Supply `https://github.com/fireflyframework/firefly-koinon`. Leave **Path** empty because the marketplace manifest is at the repository root.
3. Choose the source revision. A branch supports reviewed future syncs; a tag or commit pins the imported source.
4. Review and import the koinon plugin under your workspace's access policy. Each intended user then installs or enables it as permitted by that policy.
5. Follow [Connect ChatGPT](../guides/connect-chatgpt.md) to add the deployment's MCP connection and link the user's account. The GitHub instructions package does not establish that connection.
6. Retrieve a known source and inspect the returned evidence. Check that the same user can open that source in koinon.

OpenAI documents [GitHub import and synchronization](https://learn.chatgpt.com/docs/enterprise/plugin-management). Availability depends on the workspace's plugin controls. If those controls are unavailable, follow the custom MCP connection guide for the capabilities available to your account; importing an MCPB into ChatGPT is not a substitute.

## Update or remove an installation

Review the repository revision before syncing a marketplace or replacing a generated profile. After an update, check that the intended skill remains enabled and that `koinon_context` still reports the expected account scope. Updating a plugin does not renew an expired authorization.

To end access, revoke the OAuth connection under **Authorized applications**, or revoke the desktop bridge's token under **API tokens**, then disable or remove the corresponding client connection. Keep other users' connections separate. Removing local instructions alone does not invalidate a credential.

## Generate a profile for your deployment

A generated registered-app reference requires an existing app identifier supplied by the operator. It does not create a host registration or guarantee web availability. The portable OAuth profile uses the documented host extension and records its separate validation boundary because the published base schema does not include that extension.

Follow the [package builder and marketplace instructions](https://github.com/fireflyframework/firefly-koinon/blob/main/integrations/plugins/README.md) for installation, syncing, exact profile fields, checksums and current validator limits. For tool behavior, read [external-agent management](../guides/external-agent-management.md). Content/file publication still requires supported explicit human review; a plugin or OAuth consent is not that review. Actual external-client import, account linking and tool execution require separate acceptance testing.
