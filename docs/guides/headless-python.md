<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
# Python: use koinon without the interface

The asynchronous `firefly-koinon-sdk` supports Python 3.12 or later. Its runtime dependencies are HTTPX and Pydantic; it does not import Angular, the backend or pyfly, or start an application context. Your host owns its event loop, authentication and client lifecycle.

## Install a qualified package

Install the verified wheel supplied by your operator into your application's environment:

```bash
python -m pip install "$KOINON_SDK_WHEEL"
```

`KOINON_SDK_WHEEL` is a local verified wheel path. For source development from the repository root, use `python -m pip install ./sdk/python`. A source build, wheel-consumer check, publication and live API acceptance are separate results; this guide does not imply a package is published to PyPI.

## Authenticate and read one authorized scope

Set `KOINON_API_URL` to your API root ending in `/api/v1`, `KOINON_TOKEN` to a scoped personal token or API-audience OIDC access token, and the tenant/workspace variables to authorized IDs. Use a secret manager or process environment, never committed credentials. An ID token or a model-provider key is not an API access token.

Save this as `headless.py`. Its entry point only reads context and documents:

```python
import asyncio
import os
from koinon_sdk import KoinonClient, offset_pages

def required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Set {name} before running this example")
    return value

async def browse(client: KoinonClient, tenant: str, workspace: str) -> None:
    async def fetch(page: int):
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

## Continue by workflow

| Workflow | Guide |
| --- | --- |
| Catalog creation, bounded uploads, search/SQL, immutable history and reviewed curated writes | [Knowledge lifecycle](python-knowledge.md) |
| Saved threads, organization-default agent, SSE, cancellation and answer evidence | [Conversations and evidence](python-conversations.md) |
| Provider/agent/index/job operations, organization directory, revisions and error handling | [Administration](python-administration.md) |
| Native agentic, embedding, RAG and RLM responsibilities | [Knowledge runtime](../concepts/knowledge-runtime.md) |
| Exact signatures and all operation groups | [Generated API and SDK reference](../reference/sdk-api.md) |

Examples show existing public helpers. A successful type check or fake-transport test establishes the example's local contract, not a configured provider, finished import or live model execution.
