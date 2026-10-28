# Integration data flow and privacy

The firefly koinon desktop extension runs a local MCP bridge. Its configured remote destination is the full MCP endpoint selected by the user. The bridge sends a personal access token in an Authorization bearer header to that endpoint, forwards the host's requested tool arguments and resource or prompt requests, and returns server results to the host.

The current bridge implementation has no telemetry destination or persistence layer. This is a statement about the bridge code, not a retention promise for the desktop host, model provider, server, reverse proxy, operating system, or deployment operator. Those components have their own policies and logging behavior.

The desktop host receives knowledge returned by the server. It may process those results through its configured model provider. Review the host's data-use policy and the operator's retention, access-control, and privacy policies before enabling the integration. Select an endpoint that you trust and a token whose scope matches the knowledge you intend to expose.

The bridge rejects redirects and refuses URLs containing credentials, query parameters, or fragments. It passes the token through its process environment rather than command arguments. The MCPB configuration marks the token as sensitive; the host controls how that configuration is stored. A local process environment is not a guarantee against privileged system access.

Revoke a compromised token in koinon and update or remove the extension configuration in your host. Contact the deployment operator for requests concerning the knowledge held by the server. The extension cannot independently delete server records or change the host's retention settings.

The distributed reusable skill contains instructions only. Installing it does not send data, configure a server, or grant permissions. Running tools under the skill follows the configured MCP connection and host policies.
