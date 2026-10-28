# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import json
from pathlib import Path

import httpx

from koinon_sdk import (
    ConversationExportInput,
    ExportCreate,
    KoinonClient,
    MessageSelection,
    QueryResultExportInput,
    ShareCreate,
    ShareReviewInput,
)


async def test_review_create_paging_evidence_and_download_keep_wire_contracts():
    values = json.loads((Path(__file__).resolve().parents[2] / "contract/fixtures.json").read_text())[
        "fixtures"
    ]
    expected = [
        "ExportReview",
        "ExportReview",
        "Export",
        "ExportPage",
        "Export",
        None,
        None,
        "ShareReview",
        "Share",
        "SharePage",
        "SharedConversation",
        None,
        "EvidenceManifest",
    ]
    requests = []

    def handle(request):
        requests.append(request)
        schema = expected[len(requests) - 1]
        if request.url.path.endswith("/download"):
            return httpx.Response(
                200,
                content=b"9007199254740993,47\n",
                headers={
                    "Content-Type": "text/csv",
                    "Content-Disposition": 'attachment; filename="result.csv"',
                    "ETag": '"immutable"',
                },
            )
        return httpx.Response(200, json=values[schema]) if schema else httpx.Response(204)

    calls = 0

    def fresh():
        nonlocal calls
        calls += 1
        return f"fresh-{calls}"

    async with KoinonClient(
        "https://koinon.test/api/v1", token_provider=fresh, transport=httpx.MockTransport(handle)
    ) as client:
        await client.review_export(
            "north",
            ConversationExportInput(
                kind="conversation",
                format="markdown",
                thread_id="thread",
                message_ids=["message"],
                include_evidence=False,
            ),
        )
        await client.review_export(
            "north",
            QueryResultExportInput(
                kind="query_result", dataset_id="dataset", query_id="query", format="csv", csv_mode="exact"
            ),
        )
        await client.create_export("north", ExportCreate(review_id="review", expected_revision="a" * 64))
        await client.exports("north", page=2, page_size=10, q="renewal", status="ready")
        await client.export("north", "export/one")
        download = await client.export_download("north", "export/one")
        await client.cancel_export("north", "export/one")
        await client.review_share("north", ShareReviewInput(thread_id="thread", message_ids=["message"]))
        await client.create_share(
            "north", ShareCreate(review_id="review", expected_revision="b" * 64, expires_in_hours=1)
        )
        await client.shares("north", page=2, status="active")
        await client.share("north", "share/one")
        await client.revoke_share("north", "share/one")
        await client.conversation_evidence(
            "north", MessageSelection(thread_id="thread", message_ids=["message"])
        )
    assert len(requests) == calls == 13
    assert json.loads(requests[0].content)["include_evidence"] is False
    assert json.loads(requests[0].content)["kind"] == "conversation" and "root" not in json.loads(
        requests[0].content
    )
    assert json.loads(requests[1].content)["csv_mode"] == "exact"
    assert requests[3].url.params["page"] == "2"
    assert requests[4].url.raw_path.endswith(b"/exports/export%2Fone")
    assert requests[10].url.raw_path.endswith(b"/shares/share%2Fone")
    assert download.content == b"9007199254740993,47\n" and download.filename == "result.csv"
    assert download.etag == '"immutable"'
    assert [request.headers["Authorization"] for request in requests] == [
        f"Bearer fresh-{index}" for index in range(1, 14)
    ]
