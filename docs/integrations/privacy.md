# Integration data flow and privacy

The firefly koinon desktop extension runs a local MCP bridge. Its configured remote destination is the full MCP endpoint selected by the user. The 26.11.11 bridge sends its OAuth access token or explicitly configured personal access token in an Authorization bearer header to that endpoint, forwards the host's requested tool arguments and resource or prompt requests, and returns server results to the host.

The [desktop OAuth flow](desktop-oauth.md) supports explicit browser sign-in. It reads only the configured installation's exact OAuth metadata and token endpoints; the browser uses the installation's existing login and identity provider. OAuth access tokens and temporary code-verifier/state values remain in bridge memory only. The host receives the authorization link and connection status, but not the access token. Disconnecting locally forgets that token; server revocation remains a separate action in **Authorized applications**. The bridge has no persistent OAuth credential cache or refresh-token support.

The current bridge implementation has no telemetry destination or persistence layer. This is a statement about the bridge code, not a retention promise for the desktop host, model provider, server, reverse proxy, operating system, or deployment operator. Those components have their own policies and logging behavior.

The desktop host receives knowledge returned by the server. It may process those results through its configured model provider. Review the host's data-use policy and the operator's retention, access-control, and privacy policies before enabling the integration. Select an endpoint that you trust and a token whose scope matches the knowledge you intend to expose.

The bridge rejects redirects and refuses URLs containing credentials, query parameters, or fragments. In PAT mode, the host passes the configured token through the process environment rather than command arguments. The MCPB configuration marks that token as sensitive; the host controls how that configuration is stored. A local process environment is not a guarantee against privileged system access.

Revoke a compromised token in koinon and update or remove the extension configuration in your host. Contact the deployment operator for requests concerning the knowledge held by the server. The extension cannot independently delete server records or change the host's retention settings.

The distributed reusable skill contains instructions only. Installing it does not send data, configure a server, or grant permissions. Running tools under the skill follows the configured MCP connection and host policies.
