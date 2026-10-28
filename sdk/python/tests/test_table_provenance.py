# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import httpx

from koinon_sdk import KoinonClient


async def test_exact_snapshot_and_server_paging_are_preserved_without_current_fallback():
    calls = []
    unknown = {
        "dataset_id": "dataset",
        "table_id": "table",
        "native_dataset_id": "native-data",
        "native_table_id": "native-table",
        "snapshot_id": "old/snapshot",
        "status": "not_recorded",
        "snapshot_status": "READY",
        "level": "file_section",
    }

    def handle(request):
        calls.append(request)
        value = (
            unknown
            if request.url.path.endswith("/provenance")
            else {
                "items": [unknown],
                "total": 3,
                "page": 2,
                "page_size": 1,
                "pages": 3,
                "has_next": True,
                "has_previous": True,
                "current_snapshot_id": "new-snapshot",
            }
        )
        return httpx.Response(200, json=value)

    async with KoinonClient(
        "https://koinon.test/api/v1", token_provider=lambda: "fresh", transport=httpx.MockTransport(handle)
    ) as client:
        provenance = await client.table_provenance(
            "north", "data/set", "table/one", snapshot_id="old/snapshot"
        )
        page = await client.table_snapshots("north", "data/set", "table/one", page=2, page_size=1)
    assert provenance.snapshot_id == "old/snapshot" and provenance.artifact is None
    assert provenance.status == "not_recorded" and provenance.steps == ()
    assert page.current_snapshot_id == "new-snapshot" and page.pages == 3 and page.total == 3
    assert calls[0].url.params["snapshot_id"] == "old/snapshot"
    assert b"data%2Fset/tables/table%2Fone" in calls[0].url.raw_path
    assert dict(calls[1].url.params) == {"page": "2", "page_size": "1"}
    assert all(request.headers["authorization"] == "Bearer fresh" for request in calls)
