# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import json

import httpx
import pytest
from pydantic import ValidationError

from koinon_sdk import GlossaryTermCreate, GlossaryTermUpdate, KoinonClient


async def test_glossary_both_families_preserve_exact_timestamp_headers_and_sparse_null():
    revision = "2026-10-27T12:34:56.123456+00:00"
    calls = []
    row = dict(
        id="term",
        tenant_id="north",
        workspace_id="workspace",
        term="Renewal",
        definition="Original",
        synonyms_json=[],
        tags_json=[],
        related_columns_json=[],
        related_metrics_json=[],
        created_at=revision,
        updated_at=revision,
    )

    def handle(request):
        calls.append(request)
        return httpx.Response(204) if request.method == "DELETE" else httpx.Response(200, json=row)

    async with KoinonClient(
        "https://koinon.test/api/v1", token_provider=lambda: "fresh", transport=httpx.MockTransport(handle)
    ) as client:
        for agent in (False, True):
            read = await client.create_glossary_term(
                "north",
                "workspace",
                GlossaryTermCreate(term="Renewal", definition="Original", synonyms=["Renew"]),
                agent=agent,
            )
            assert read.updated_at == revision
            await client.update_glossary_term(
                "north",
                "workspace",
                "term/one",
                GlossaryTermUpdate(definition=None, tags=[]),
                expected_updated_at=read.updated_at,
                agent=agent,
            )
            await client.delete_glossary_term(
                "north", "workspace", "term/one", expected_updated_at=read.updated_at, agent=agent
            )
    assert len(calls) == 6
    for index, request in enumerate(calls):
        assert request.headers["X-Tenant-ID"] == "north" and request.headers["X-Workspace-ID"] == "workspace"
        if request.method != "POST":
            assert request.headers["If-Match"] == '"' + revision + '"'
            assert request.url.raw_path.endswith(b"/term%2Fone")
        assert ("/agent/glossary" in request.url.path) == (index >= 3)
    assert json.loads(calls[1].content) == {"definition": None, "tags_json": []}
    assert json.loads(calls[0].content)["synonyms_json"] == ["Renew"]
    with pytest.raises(ValidationError):
        GlossaryTermCreate(term="Renewal", definition="Original", synonyms=[], synonyms_json=[])
