<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
# Python: use koinon without the interface

The asynchronous `firefly-koinon-sdk` supports Python 3.12 or later. Its runtime dependencies are HTTPX and Pydantic; it does not import Angular, the backend or pyfly, or start an application context. Your host owns its event loop, authentication and client lifecycle.

## Work through the tutorial

Start here when you have an API address and an account but have not written an integration yet. The first program establishes authentication, checks the available organization context, and pages through documents. It makes no changes. After it works, keep the same client configuration for [knowledge](python-knowledge.md), [conversations](python-conversations.md), and [administration](python-administration.md).

Use the resource IDs from your first catalog read in the remaining chapters. Each chapter introduces the permissions, inputs and response fields needed for its operations.

[Download the complete Python tutorial source and build instructions](../examples/python/README.md). The files include imports and entry points. Each chapter's default entry point reads existing state; write helpers are separate functions that your application calls after its own explicit decision. Keep all files for the selected language together.

## Prepare the deployment and credential

Ask your operator for an authorized API root, an organization, and a workspace you can read. Start with a credential whose scope includes `catalog:read` and whose resource bounds admit that workspace. Do not request every management scope merely to make the first request succeed.

| Value | Where it comes from | How the program uses it |
| --- | --- | --- |
| `KOINON_API_URL` | Your deployment operator | API root ending in `/api/v1`, without a token in the URL. |
| `KOINON_TOKEN` | A current API-audience OIDC access token or a scoped personal API token | The callback supplies it afresh for each request. |
| `KOINON_TENANT_ID` | The organization's canonical ID in the current context | Every tenant operation uses this exact organization. |
| `KOINON_WORKSPACE_ID` | An authorized workspace returned by the API | Catalog and knowledge filters stay inside this destination. |

An OIDC access token comes from your host's approved identity flow. This tutorial does not implement that flow or ask for a refresh token. For a personal token, sign in through the ordinary account flow, review its permitted scopes and resource bounds, and save its one-time secret privately. An existing PAT cannot create another PAT. Never substitute a model-provider key, an ID token, or an MCP resource token.

Set the variables through your shell's secure environment mechanism or secret manager. Avoid pasting live credentials into an example file, a terminal transcript, a URL, or a support ticket. A long-running host should renew its access token before returning it from the callback; replacing an expired token is the host's responsibility.

## Install the SDK

Install the verified wheel supplied by your operator into your application's environment:

```bash
python -m pip install "$KOINON_SDK_WHEEL"
```

Download the wheel and `SHA256SUMS` from [GitHub Releases](https://github.com/fireflyframework/firefly-koinon/releases), verify its checksum, and set `KOINON_SDK_WHEEL` to the local wheel path. For source development from the repository root, use `python -m pip install ./sdk/python`.

## Authenticate and read one authorized scope

Set `KOINON_API_URL` to your API root ending in `/api/v1`, `KOINON_TOKEN` to a scoped personal token or API-audience OIDC access token, and the tenant/workspace variables to authorized IDs. Use a secret manager or process environment, never committed credentials. An ID token or a model-provider key is not an API access token.

Save this as `headless.py`. Its entry point only reads context and documents:

```python
import asyncio
import os
from koinon_sdk import KoinonClient, offset_pages, Page, CatalogEntry

def required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Set {name} before running this example")
    return value

async def browse(client: KoinonClient, tenant: str, workspace: str) -> None:
    async def fetch(page: int) -> Page[CatalogEntry]:
        return await client.catalog(
            tenant, workspace_id=workspace, kind="document", page=page,
            page_size=25, sort="name", order="asc",
        )
    async for page in offset_pages(fetch):
        for document in page.items:
            print(document.id, document.name)

async def main() -> None:
    tenant, workspace = required("KOINON_TENANT_ID"), required("KOINON_WORKSPACE_ID")
    async with KoinonClient(required("KOINON_API_URL"),
                           token_provider=lambda: required("KOINON_TOKEN")) as client:
        context = await client.context()
        if not any(item.id == tenant for item in context.tenants):
            raise RuntimeError("The selected organization is unavailable")
        await browse(client, tenant, workspace)

if __name__ == "__main__":
    asyncio.run(main())
```

Run `python headless.py` only against your authorized deployment. The token callback is evaluated on each request and can be asynchronous. Replace the environment lookup with your host's token-renewal callback for expiring OIDC tokens. The SDK does not store a refresh token, renew credentials, follow redirects or automatically retry writes.

Current authority is the intersection of token scopes, the owner's current roles and token resource bounds. Choosing a tenant or workspace is not a grant. Reads use `catalog:read`; search, SQL, chat and writes have separate permissions. Management capabilities remain organization-scoped where required, and ordinary-identity-only operations cannot be enabled with a PAT scope. See [API permissions and current roles](api-permissions.md).

Use the bearer `/api/v1` API for Python services. Do not copy browser session cookies or point the service at `/bff/api/v1`. Close the client with `async with`; a DI-managed host can instead close it during its own shutdown. See [administration and safe operations](python-administration.md) for paging, cancellation, errors and private binary data.

## Understand the first response

Run the startup program only after choosing the deployment and credential above. The context response identifies the current subject, available organizations, memberships, workspaces, and applicable permissions. Select IDs from that response rather than displaying a guessed organization or treating a URL parameter as a grant. In an application, keep that context with the authenticated session and discard it when the identity changes.

The catalog request returns a typed page. `items` contains the current authorized rows; `page`, `page_size` or `size`, `pages`, and `total` describe pagination when the endpoint supplies them. The helper asks for another server page lazily. It does not fetch a large list and slice it locally. An empty list can be a legitimate empty scope; it is not an invitation to remove the workspace filter.

The printed IDs and names are the program's expected output. They are resource identities for later calls, not sample fixture IDs you should hardcode. Retain a selected document or dataset ID when moving to the next chapter. Keep names as labels, since renaming an asset does not change its identity.

If the first call returns `401`, repair the host's token acquisition or expiry handling before continuing. If it returns `403`, compare the current role, requested scopes, resource bounds, and credential type. A wider token cannot repair a missing role. For a timeout or protocol error, retain only safe status and request-reference metadata; never print the token or a whole private response body.

The SDK does not renew credentials, create a sign-in session, or reconnect a stream automatically. Keeping those responsibilities in the host lets a web application, command-line tool, and scheduled service use the same API without sharing browser cookies or credentials accidentally.

## Continue by workflow

| Workflow | Guide |
| --- | --- |
| Catalog creation, bounded uploads, search/SQL, immutable history and reviewed curated writes | [Knowledge lifecycle](python-knowledge.md) |
| Saved threads, organization-default agent, SSE, cancellation and answer evidence | [Conversations and evidence](python-conversations.md) |
| Provider/agent/index/job operations, organization directory, revisions and error handling | [Administration](python-administration.md) |
| Native agentic, embedding, RAG and RLM responsibilities | [Knowledge runtime](../concepts/knowledge-runtime.md) |
| Exact signatures and all operation groups | [Generated API and SDK reference](../reference/sdk-api.md) |
