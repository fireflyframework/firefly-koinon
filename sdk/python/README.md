<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
# koinon Python SDK

A typed asynchronous client for the koinon API, independent of Angular, the backend and pyfly. Python 3.12 or later is required; runtime dependencies are HTTPX and Pydantic. Your application owns authentication, token renewal and the event loop.

## Install and read

Install an operator-supplied verified wheel with `python -m pip install "$KOINON_SDK_WHEEL"`. For source development from the repository root, use `python -m pip install ./sdk/python`. Local wheel qualification does not imply publication to PyPI or acceptance against a live deployment.

Set the API URL ending in `/api/v1`, an authorized tenant ID and a scoped API token in your environment. This example reads only:

```python
import asyncio
import os
from koinon_sdk import KoinonClient

def required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Set {name}")
    return value

async def main() -> None:
    tenant = required("KOINON_TENANT_ID")
    async with KoinonClient(required("KOINON_API_URL"),
                           token_provider=lambda: required("KOINON_TOKEN")) as client:
        context = await client.context()
        if not any(item.id == tenant for item in context.tenants):
            raise RuntimeError("The selected organization is unavailable")
        documents = await client.catalog(tenant, kind="document", page=1, page_size=25)
        for document in documents.items:
            print(document.id, document.name)

if __name__ == "__main__":
    asyncio.run(main())
```

The callback can be synchronous or asynchronous and is evaluated per request. Supply a personal token or an OIDC access token for the API audience; an ID token or model-provider key is not suitable. Replace the environment lookup with host-owned renewal for expiring tokens. Never copy browser cookies to a service or use the cookie-only BFF prefix. `async with` closes the HTTP client; a DI host can close it during its own shutdown.

## Follow a workflow

These links target the guides in the source repository:

- [Python setup, authentication and first read](../../docs/guides/headless-python.md)
- [Knowledge creation, intake, search/SQL, immutable history and curated confirmation](../../docs/guides/python-knowledge.md)
- [Conversations, SSE, cancellation, audit, exports and proposals](../../docs/guides/python-conversations.md)
- [Administration, organization directory, paging, revisions, errors and private downloads](../../docs/guides/python-administration.md)
- [Agentic, embedding, RAG and RLM responsibilities](../../docs/concepts/knowledge-runtime.md)
- [Generated API reference](../../docs/reference/sdk-api.md)

| Capability | Representative helpers |
| --- | --- |
| Catalog and ingestion | `catalog`, `get`, `create`, `update`, `archive`, `restore`, `delete`, `upload`, `append_dataset_file` |
| Search and structured data | `search`, `query`, `schema`, table snapshots/provenance/coordinate methods, retained glossary helpers |
| Immutable document history | `document_versions`, `document_version`, `document_extractions`, `document_parts`, `document_part`, `document_version_original` |
| Content changes | `replace_document`, `reingest_document`, `replace_table`, `reingest_table` with current digest/snapshot preconditions |
| Curated knowledge | `preview_knowledge`, `knowledge_intent`, `confirm_knowledge`, `cancel_knowledge`, `knowledge_items`/item/version reads |
| Conversations | threads, folders, messages, `submit_run`, `events`, `cancel_run`, `retry_run`, results, activities and `run_audit` |
| Private attachments | capabilities, upload/retry/read/cancel/remove and explicit reviewed promotion |
| Model/knowledge operations | configuration, providers, agents, source connections/roles, index lifecycle and jobs |
| Organization and account | `organization_people` and related position/unit/settings/mapping helpers, members, invitations, audit, profile, tokens and organization defaults |
| Reviewed distribution | conversation evidence, exports, authenticated shares and explicit catalog proposals |
| Connected applications | authorized applications, MCP descriptors, OAuth registration management and reviewed external text/file changes |

Use `sdk/contract/operations.json` and `schemas.json` for the current checked operation index and schemas instead of a duplicated count. Qualified retained glossary routes are listed separately; operator probes and browser-only authentication routes are not headless API operations.

## Keep authority and outcomes explicit

- Effective access intersects token scopes, the owner's current roles and saved resource bounds. Position metadata never grants a role. Corporate profile mapping, token administration and OAuth registration management retain ordinary verified-identity gates; a PAT cannot bypass them.
- Input serialization preserves omission versus explicit `None`, false and zero. Read current revisions before writes. Releasing a provider source uses `manage_locally=True`, not a null provider ID.
- Writes, stream reconnection and unknown commit outcomes are never automatically retried. Preserve stable request/idempotency identities and reconcile `pending`/unresolved results. A conflict requires a new reviewed decision.
- `offset_pages` and `cursor_pages` use actual endpoint pagination without prefetch or synthetic pages. Close partially consumed generators/streams; canceling their HTTP task does not cancel a durable run or job.
- `ApiError.status`, `.code` and `.transaction_id` preserve safe operator correlation. Do not log bearer credentials or credential-bearing request objects.
- Binary helpers retain private bytes and nullable metadata; they do not choose a local filename. Preserve exact decimals/unsafe integers as strings and use the explicit exact-value helpers when constructing opaque payloads.
- Audit presence and provenance completeness are separate. Preserve unknown identities, null `rlm_tools`, exact historical versions and actual observed coverage. Current availability is not historical evidence.
- Curated/catalog/external proposals need an explicit reviewed confirmation. Public clients cannot obtain component-only approval nonces or invent curated sharing/export/derive/delete capabilities.

Use the source package's configured tests, Ruff and Pyright for development. Source checks, built-wheel consumers, publication, managed-database/provider integration and live application acceptance remain separate evidence.

Copyright 2026 Firefly Software Foundation. Licensed under Apache-2.0.
