# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""RLM metadata lineage remains authorized without becoming factual answer evidence."""

from dataclasses import replace
from datetime import timedelta
from hashlib import sha256
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pyfly.kernel import InvalidRequestException
from test_service import assistants as assistants
from test_service import configured

from koinon.assistants.execution import AssistantExecutor
from koinon.assistants.lifecycle import timestamp
from koinon.assistants.queue import AssistantQueue
from koinon.catalog.errors import AccessDenied
from koinon.catalog.service import ROLE_PERMISSIONS
from koinon.evidence.dtos import SourceReference
from koinon.knowledge.capture_dtos import CapturedEvidence, NativeReadFingerprint
from koinon.knowledge.evidence_capture import NativeKnowledgeEvidence
from koinon.tokens.authorization import TokenRestriction
from koinon.tokens.entities import PersonalToken
from koinon.tokens.repositories import PersonalTokenRepository


async def prepared(assistants, *, restricted=False):
    service, context = assistants
    parent = None
    for kind in ("workspace", "project", "collection", "source"):
        parent = await service.catalog.create(
            "issuer|admin", "north", kind=kind, name=kind, parent_id=parent.id if parent else None
        )
    documents = [
        await service.catalog.create(
            "issuer|admin", "north", kind="document", name="Document " + key, parent_id=parent.id
        )
        for key in ("A", "B")
    ]
    _, agent = await configured(service)
    allowed = [documents[0].id] if restricted else [value.id for value in documents]
    thread = await service.create_thread("issuer|admin", "north", {"scope": {"asset_ids": allowed}})
    await service.submit(
        "issuer|admin",
        "north",
        thread["id"],
        {
            "agent_id": agent["id"],
            "message": "Read A while observing B metadata",
            "client_request_id": "native-read-union",
        },
    )
    run = await context.get_bean(AssistantQueue).claim("rlm-worker")
    text = "A fixed recorded passage."
    source = SourceReference(
        id="body-A",
        asset_id=documents[0].id,
        source_id=parent.id,
        title="Document A",
        kind="document",
        chunk_id="chunk-A",
        quote=text,
        used_revision="chunk-sha256:" + sha256(text.encode()).hexdigest(),
    )
    reads = tuple(
        NativeReadFingerprint(
            "rlm.corpus",
            "documents",
            "north",
            value.workspace_id,
            value.id,
            "a" * 64,
            ("native-" + str(index),),
            (),
            read_kind="metadata",
        )
        for index, value in enumerate(documents)
    )
    data = {"hits": [{"id": "chunk-A", "asset_id": documents[0].id, "source_id": parent.id, "text": text}]}
    capture = CapturedEvidence(data, (source,), True, reads)
    return service, context, run, documents, capture


async def test_actual_executor_persists_metadata_assets_but_exposes_only_consumed_body_facts(assistants):
    service, context, run, documents, capture = await prepared(assistants)
    context.container.register_instance(
        NativeKnowledgeEvidence, SimpleNamespace(search=AsyncMock(return_value=capture))
    )
    tool = (await context.get_bean(AssistantExecutor).tools(run.id, "rlm-worker", ["search_knowledge"]))[0]
    result = await tool.execute(question="Read A")
    stored = await service.results.find_by_id(result["evidence_id"])
    assert set(stored.payload["asset_ids"]) == {value.id for value in documents}
    assert {row["entity_id"] for row in stored.payload["native_reads"]} == {value.id for value in documents}
    assert [row["asset_id"] for row in stored.payload["source_manifest"]["sources"]] == [documents[0].id]
    assert stored.payload["source_manifest"]["complete"] is True
    assert len(result["answer_facts"]) == 1 and result["answer_facts"][0]["text"] == capture.sources[0].quote


@pytest.mark.parametrize(
    "change",
    [
        "omitted_read",
        "extra_asset",
        "foreign_tenant",
        "wrong_workspace",
        "outside_scope",
        "revoked",
        "original_token",
    ],
)
async def test_observed_metadata_cannot_expand_or_forge_current_capture_authority(assistants, change):
    service, context, run, documents, capture = await prepared(
        assistants, restricted=change == "outside_scope"
    )
    assets = [value.id for value in documents]
    if change == "omitted_read":
        assets = assets[:1]
    if change == "extra_asset":
        assets.append("not-observed")
    if change == "foreign_tenant":
        capture = replace(
            capture,
            native_reads=(capture.native_reads[0], replace(capture.native_reads[1], tenant_id="south")),
        )
    if change == "wrong_workspace":
        capture = replace(
            capture,
            native_reads=(
                capture.native_reads[0],
                replace(capture.native_reads[1], workspace_id="another-workspace"),
            ),
        )
    if change == "revoked":
        member = await service.catalog.membership_repository.find_by_id("admin")
        member.active = False
        await service.catalog.membership_repository.save(member)
    if change == "original_token":
        from pyfly.container.scanner import scan_package

        scan_package("koinon.tokens", context.container)
        service.catalog.restriction = context.get_bean(TokenRestriction)
        await context.get_bean(PersonalTokenRepository).save(
            PersonalToken(
                id="capture-origin",
                subject="issuer|admin",
                tenant_id="north",
                name="Controlled original ceiling",
                token_hash="0" * 64,
                prefix="fixture",
                scopes=sorted(ROLE_PERMISSIONS["admin"]),
                asset_ids=[documents[0].id],
                expires_at=timestamp() + timedelta(hours=1),
            )
        )
        run.access_token_id = "capture-origin"
        await service.runs.save(run)
    before = {value.id for value in await service.results.find_all(run_id=run.id)}
    expected = (
        AccessDenied if change in {"outside_scope", "revoked", "original_token"} else InvalidRequestException
    )
    with pytest.raises(expected):
        await context.get_bean(AssistantQueue).evidence(
            run.id, "rlm-worker", "search", capture.data, assets, capture=capture
        )
    assert {value.id for value in await service.results.find_all(run_id=run.id)} == before
