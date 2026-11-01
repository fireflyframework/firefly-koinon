# Desktop MCP extension

The firefly koinon 26.11.3 desktop extension connects a compatible MCP desktop host to an operator-managed koinon MCP endpoint. The bridge uses the official TypeScript MCP SDK and forwards remote tools, resources, and prompts. The server remains responsible for schemas, permissions, and knowledge access.

## Install in Claude Desktop

Obtain the MCPB archive and its `SHA256SUMS` from a trusted distribution and verify the checksum. Open the archive in a Claude Desktop version that supports desktop extensions. Review the extension details, enter your operator's full HTTPS MCP URL, including `/mcp`, and enter a scoped personal access token. The token is marked as sensitive and passed to the bridge through its environment.

Enable the extension and ask the assistant to inspect the current koinon context. Review tool requests before allowing access. The package supports Node.js 22 or later supplied by the host. The server's remote MCP endpoint must be enabled by your operator. No tenant or workspace credentials are embedded in the extension; the token and remote tools determine the available scope.

The branded installation preview shipped in the archive illustrates these settings. It is explanatory artwork, not a screenshot of Claude Desktop or proof of a completed installation.

## Reusable skill

The portable skills archive includes `koinon-evidence`, which guides document retrieval, schema inspection, bounded dataset queries, answer audit interpretation, provenance, and citation. Install the folder through your assistant's supported skill mechanism. MCPB installation does not automatically install skills. A skill provides instructions and does not establish a connection or grant access.

## ChatGPT and other MCP hosts

MCPB is a local desktop extension format. It does not provide a local archive installer or connector for ChatGPT. A ChatGPT remote MCP integration requires a reachable HTTPS endpoint and a host-supported authentication flow, typically OAuth. The current personal-access-token bridge does not implement OAuth.

Other compatible MCP hosts can launch the extracted `server/index.cjs` with Node.js, setting `KOINON_MCP_URL` and `KOINON_TOKEN` through secure environment configuration. Keep tokens out of arguments, URLs, source control, and logs. Use the host's own policy and setup documentation to determine supported transports and authentication.

## Connection behavior

The bridge initializes locally and contacts the configured endpoint only when the host requests tools, resources, or prompts. It rejects redirects and URLs containing credentials, query parameters, or fragments. Requests use a 30-second timeout. HTTPS is required; an explicit environment-only loopback HTTP override exists for development and is absent from desktop configuration.

Read the [integration data flow and privacy notes](privacy.md) before connecting sensitive knowledge. For build instructions, packaging checks, and dependency provenance, see `integrations/mcp-desktop/README.md` in the repository.

## Reviewed knowledge management

A compatible host can render the remote server's embedded review for text creation/updates and file uploads. The bridge forwards tool results and resources; the host must preserve MCP Apps private metadata and app-only visibility. Installation alone does not establish that capability. A PAT needs the exact write and supporting-evidence scopes, intersected with the current user's role and resource bounds. See [managing knowledge inside an MCP conversation](../guides/mcp-knowledge-management.md) and the dedicated [Claude](../guides/connect-claude.md) and [ChatGPT](../guides/connect-chatgpt.md) connection guides.

The [plugin marketplace and profile guide](plugins.md) explains GitHub distribution, canonical skills and deployment-specific OAuth metadata. Packages do not replace account authorization or supported human review.
