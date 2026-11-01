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
| Desktop host supporting MCPB | Existing desktop extension | Explicit HTTPS endpoint and separately issued scoped PAT |

A generated registered-app reference requires an existing app identifier supplied by the operator. It does not create a host registration or guarantee web availability. The portable OAuth profile uses the documented host extension and records its separate validation boundary because the published base schema does not include that extension.

Follow the [package builder and marketplace instructions](https://github.com/fireflyframework/firefly-koinon/blob/main/integrations/plugins/README.md) for installation, syncing, exact profile fields, checksums and current validator limits. For tool behavior, read [external-agent management](../guides/external-agent-management.md). Content/file publication still requires supported explicit human review; a plugin or OAuth consent is not that review. Actual external-client import, account linking and tool execution require separate acceptance testing.
