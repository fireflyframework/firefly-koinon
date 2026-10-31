# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0

import asyncio
import os

from koinon_sdk import CatalogEntry, KoinonClient, Page, offset_pages


def required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Set {name} before running this example")
    return value


async def browse(client: KoinonClient, tenant: str, workspace: str) -> None:
    async def fetch(page: int) -> Page[CatalogEntry]:
        return await client.catalog(
            tenant,
            workspace_id=workspace,
            kind="document",
            page=page,
            page_size=25,
            sort="name",
            order="asc",
        )

    async for page in offset_pages(fetch):
        for document in page.items:
            print(document.id, document.name)


async def main() -> None:
    tenant, workspace = required("KOINON_TENANT_ID"), required("KOINON_WORKSPACE_ID")
    async with KoinonClient(
        required("KOINON_API_URL"), token_provider=lambda: required("KOINON_TOKEN")
    ) as client:
        context = await client.context()
        if not any(item.id == tenant for item in context.tenants):
            raise RuntimeError("The selected organization is unavailable")
        await browse(client, tenant, workspace)


if __name__ == "__main__":
    asyncio.run(main())
