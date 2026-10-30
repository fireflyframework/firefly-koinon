# Python: scoped knowledge operations

Python 3.12 or later can use the built `firefly-koinon-sdk` wheel without Angular or the backend package. Build from a trusted repository checkout with `python -m pip install ./sdk/python`, or install a verified wheel supplied by your operator. This does not imply publication to PyPI.

Set `KOINON_API_URL` to the API root ending in `/api/v1`, `KOINON_TOKEN` to a scoped personal or API-audience OIDC access token, and `KOINON_TENANT_ID` and `KOINON_WORKSPACE_ID` to authorized identifiers. Keep these values in your process environment or secret manager. Do not commit them. The token callback is called for each request; replace the environment lookup with your identity provider's renewal callback when using expiring OIDC tokens.

Save the example as `headless.py`. Running it only reads and lists authorized documents. File ingestion and model execution occur only when your application explicitly calls those helpers. Their destination identifiers must come from your authorized catalog.

```python
import asyncio
import os
from pathlib import Path
from typing import Literal
from uuid import uuid4

from koinon_sdk import KoinonClient, KnowledgeScope, RunInput, offset_pages

def required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Set {name} before running this example")
    return value

async def browse(client: KoinonClient, tenant: str, workspace: str):
    async def fetch(page: int):
        return await client.catalog(tenant, workspace_id=workspace, kind="document",
                                    page=page, page_size=25, sort="name", order="asc")
    async for page in offset_pages(fetch):
        for document in page.items:
            print(document.id, document.name)

async def upload_files(client: KoinonClient, tenant: str, workspace: str,
                       project: str, collection: str, files: list[Path],
                       mode: Literal["document", "dataset"] = "document"):
    if not 1 <= len(files) <= 16:
        raise ValueError("Choose from 1 to 16 files")
    for path in files:
        if not path.is_file() or path.stat().st_size > 32 * 1024 * 1024:
            raise ValueError(f"Choose a regular file up to 32 MiB: {path.name}")
    for path in files:
        content = await asyncio.to_thread(path.read_bytes)
        if len(content) > 32 * 1024 * 1024:
            raise ValueError("The file changed after size validation")
        receipt = await client.upload(tenant, filename=path.name, content=content,
            parent_id=collection, workspace_id=workspace, project_id=project, mode=mode)
        yield path.name, receipt

async def ask(client: KoinonClient, tenant: str, scope: KnowledgeScope, question: str):
    settings = await client.organization_chat_settings(tenant,
        workspace_id=scope.workspace_id, project_id=scope.project_id)
    if not settings.can_run or settings.default_agent_id is None:
        raise RuntimeError("An operator must configure the organization's chat agent")
    thread = await client.create_thread(tenant, title="Knowledge question", scope=scope)
    run = await client.submit_run(tenant, thread.id, RunInput(
        agent_id=settings.default_agent_id, message=question, scope=scope,
        client_request_id=str(uuid4()), attachment_ids=[],
    ))
    completed = False
    async with client.events(tenant, run.run_id) as stream:
        async for event in stream:
            print(event.id, event.type)
            if event.type in {"failed", "cancelled"}:
                raise RuntimeError(f"Run ended: {event.type}")
            if event.type == "completed":
                completed = True
                break
    if not completed:
        raise RuntimeError("The stream ended without a completed event")
    audit = await client.run_audit(tenant, run.run_id)
    return thread, run, audit

async def main():
    async with KoinonClient(required("KOINON_API_URL"),
            token_provider=lambda: required("KOINON_TOKEN")) as client:
        await client.context()
        await browse(client, required("KOINON_TENANT_ID"), required("KOINON_WORKSPACE_ID"))

if __name__ == "__main__":
    asyncio.run(main())
```

Run `python headless.py`. To ingest a batch, explicitly iterate `upload_files(...)` and persist every yielded receipt before requesting the next item. This is a bounded client loop, not a durable server batch. Stop and reconcile an ambiguous upload outcome; do not retry the whole list automatically.

Call `ask` with a `KnowledgeScope` containing the intended workspace and optional project, collection or asset IDs. The saved organization default supplies the actual agent ID; choosing a scope never grants additional access. Read saved messages through `await client.messages(tenant, thread.id)` and tool result payloads through `await client.result(tenant, run.run_id, result_id)` using IDs returned by that run.

The async context managers close HTTP responses and the client. They do not cancel a durable run: use `await client.cancel_run(tenant, run.run_id)` when the user requests cancellation. For intentional stream resumption, pass the last fully processed event ID as `last_event_id`; handle `message_reset` by replacing the partial message in your own presentation state. Never log token values or model credentials.

Preserve `audit.sources`, `native_reads`, `sql_attempts` and nullable `rlm_tools` as recorded. A completed event does not prove complete source history. See [audit semantics](agents.md#read-the-audit-without-the-frontend), [reviewed export and sharing](exports-sharing.md) and the [full SDK reference](../reference/sdk-api.md).
