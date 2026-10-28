# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from hashlib import sha256
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from koinon.catalog.errors import AccessDenied
from koinon.knowledge.capture_receipt import NativeEvidenceReceipt
from koinon.knowledge.evidence_capture import NativeKnowledgeEvidence


def prepared():
    asset = SimpleNamespace(id="asset", kind="document", name="Owned source", workspace_id="space")
    source = SimpleNamespace(id="source")
    binding = SimpleNamespace(native_id="native-source", native_workspace_id="native-space")
    knowledge = SimpleNamespace(
        _chain=AsyncMock(return_value=[asset, source]), binding=AsyncMock(return_value=binding)
    )
    native = {
        "chunk_id": "chunk",
        "source_id": "native-source",
        "content": "Exact native text 😀",
        "page": 3,
        "section_path": "Scope",
    }
    data = {
        "hits": [
            {
                "id": "chunk",
                "asset_id": "asset",
                "source_id": "source",
                "title": "Owned source",
                "text": native["content"],
            }
        ]
    }

    async def search(subject, tenant, **kwargs):
        kwargs["_capture"].search(tenant, "native-space", subject, [native])
        return data

    knowledge.search = AsyncMock(side_effect=search)
    return NativeKnowledgeEvidence(knowledge, SimpleNamespace()), knowledge, native, data


async def test_new_read_captures_exact_native_chunk_content_without_current_source_hash_backfill():
    service, knowledge, native, data = prepared()
    captured = await service.search("owner", "tenant", question="Scope", answer=False)
    assert captured.data == data and captured.complete
    assert len(captured.sources) == 1
    source = captured.sources[0]
    assert source.used_revision == "chunk-sha256:" + sha256(native["content"].encode()).hexdigest()
    assert (source.asset_id, source.source_id, source.chunk_id, source.page, source.section) == (
        "asset",
        "source",
        "chunk",
        3,
        "Scope",
    )
    assert source.current_revision is None and source.quote == native["content"]
    knowledge._chain.assert_awaited()


async def test_forged_data_manifest_or_missing_native_observer_never_becomes_complete():
    service, knowledge, _, data = prepared()
    data["source_manifest"] = {"version": 1, "complete": True, "sources": []}
    knowledge.search = AsyncMock(return_value=data)
    captured = await service.search("owner", "tenant", question="Scope")
    assert not captured.complete and captured.sources == ()


async def test_alias_or_scope_mismatch_and_postread_revocation_are_denied_before_manifest_return():
    service, knowledge, _, _ = prepared()
    knowledge.binding.return_value.native_id = "foreign-source"
    with pytest.raises(AccessDenied):
        await service.search("owner", "tenant", question="Scope")
    service, knowledge, _, _ = prepared()
    knowledge._chain.side_effect = AccessDenied("Revoked")
    with pytest.raises(AccessDenied):
        await service.search("owner", "tenant", question="Scope")


async def test_schema_observes_object_snapshot_at_read_and_does_not_infer_a_current_pin():
    receipt = NativeEvidenceReceipt("owner", "tenant")
    receipt.schema(
        "tenant",
        "native-space",
        "owner",
        "dataset",
        {"id": "table", "name": "orders", "current_snapshot_id": "old"},
        [{"snapshot_id": "new"}],
    )
    assert not receipt.complete and receipt.snapshots == []
    receipt = NativeEvidenceReceipt("owner", "tenant")
    receipt.query(
        "tenant",
        "native-space",
        "owner",
        "dataset",
        {"query_id": "query", "execution_status": "OK", "snapshot_pins": {}},
    )
    assert not receipt.complete and receipt.snapshots == []


async def test_capture_receipt_rejects_wrong_actor_or_reuse_after_close():
    receipt = NativeEvidenceReceipt("owner", "tenant")
    with pytest.raises(AccessDenied):
        receipt.search("tenant", "native-space", "other", [])
    receipt.closed = True
    with pytest.raises(AccessDenied):
        receipt.search("tenant", "native-space", "owner", [])


async def test_actual_native_search_adapter_observes_native_dto_before_canonical_projection():
    from flycanon.interfaces.dtos.query import Hit, SearchResponse

    from koinon.knowledge.adapters import NativeDomains

    bus = SimpleNamespace(
        query=AsyncMock(
            return_value=SearchResponse(
                hits=[
                    Hit(
                        chunk_id="chunk",
                        source_id="native-source",
                        content="Native read",
                        score=1,
                        page=4,
                        section_path="Actual",
                    )
                ],
                elapsed_ms=0,
            )
        )
    )
    domains = NativeDomains(SimpleNamespace(contains_type=lambda kind: True, resolve=lambda kind: bus))
    receipt = NativeEvidenceReceipt("owner", "tenant")
    result = await NativeDomains.search.__wrapped__(
        domains,
        tenant_id="tenant",
        workspace_id="native-space",
        source_ids=["native-source"],
        question="Read",
        limit=1,
        answer=False,
        actor="owner",
        _capture=receipt,
    )
    assert result["hits"][0]["content"] == "Native read"
    assert receipt.documents["chunk"].digest == sha256(b"Native read").hexdigest()
    assert receipt.documents["chunk"].page == 4


async def test_actual_native_schema_adapter_observes_raw_snapshot_ids_before_returning_columns():
    from uuid import uuid4

    from koinon.knowledge.adapters import NativeDomains

    dataset, table, snapshot, workspace = uuid4(), uuid4(), uuid4(), uuid4()
    service = SimpleNamespace(
        list_for_dataset=AsyncMock(
            return_value=[{"id": table, "name": "orders", "current_snapshot_id": snapshot}]
        ),
        list_objects=AsyncMock(
            return_value=[
                {
                    "id": uuid4(),
                    "snapshot_id": snapshot,
                    "kind": "COLUMN",
                    "qualified_name": "orders.total",
                    "data_type": "BIGINT",
                }
            ]
        ),
    )
    domains = NativeDomains(SimpleNamespace(contains_type=lambda kind: True, resolve=lambda kind: service))
    receipt = NativeEvidenceReceipt("owner", "tenant")
    result = await domains.schema(
        tenant_id="tenant",
        workspace_id=str(workspace),
        dataset_id=str(dataset),
        actor="owner",
        _capture=receipt,
    )
    assert result["tables"][0]["snapshot_id"] == str(snapshot)
    assert receipt.complete and len(receipt.snapshots) == 1
    assert receipt.snapshots[0].snapshot_id == str(snapshot)


async def test_inherited_task_cannot_reuse_another_read_receipt():
    import asyncio

    receipt = NativeEvidenceReceipt("owner", "tenant")

    async def child():
        receipt.search("tenant", "space", "owner", [])

    with pytest.raises(AccessDenied):
        await asyncio.create_task(child())


async def test_verified_reranker_read_superset_is_retained_with_canonical_receipt_identities():
    from flycanon.core.services.query.provenance import before_model, observe

    capture, knowledge, native, data = prepared()
    first = SimpleNamespace(id="asset", kind="document", name="First", workspace_id="canonical-space")
    second = SimpleNamespace(id="other-asset", kind="document", name="Second", workspace_id="canonical-space")
    parents = {"asset": SimpleNamespace(id="source"), "other-asset": SimpleNamespace(id="other-source")}
    assets = {"asset": first, "other-asset": second}
    knowledge._chain = AsyncMock(side_effect=lambda subject, tenant, asset: [assets[asset], parents[asset]])
    knowledge.binding = AsyncMock(
        side_effect=lambda tenant, asset, domain, entry: SimpleNamespace(
            native_workspace_id="native-space",
            native_id="native-source" if asset == "asset" else "other-native-source",
        )
    )

    async def search(subject, tenant, **kwargs):
        receipt = kwargs["_capture"]
        receipt.authorize_model = AsyncMock()
        receipt.admit_documents(
            tenant,
            "native-space",
            subject,
            {
                "native-source": (first, parents["asset"]),
                "other-native-source": (second, parents["other-asset"]),
            },
        )
        hits = [
            SimpleNamespace(
                chunk_id="chunk", source_id="native-source", content=native["content"], metadata={}
            ),
            SimpleNamespace(
                chunk_id="other-chunk", source_id="other-native-source", content="Inspected only", metadata={}
            ),
        ]
        with observe(
            receipt,
            tenant_id=tenant,
            workspace_id="native-space",
            actor=subject,
            source_ids=["native-source", "other-native-source"],
        ):
            await before_model(
                "rerank", "Exact widened native input", hits, tenant_id=tenant, workspace_id="native-space"
            )
        return data

    knowledge.search = AsyncMock(side_effect=search)
    result = await capture.search("owner", "tenant", question="First")
    assert result.complete and len(result.data["hits"]) == 1
    assert {row.asset_id for row in result.sources} == {"asset", "other-asset"}
    assert {row.entity_id for row in result.native_reads} == {"asset", "other-asset"}
    assert all(
        row.domain == "documents" and row.workspace_id == "canonical-space" for row in result.native_reads
    )
    assert {source for row in result.native_reads for source in row.source_ids} == {
        "native-source",
        "other-native-source",
    }


async def test_failed_native_work_keeps_safe_canonical_audit_receipt_and_denial_semantics():
    from koinon.knowledge.capture_dtos import NativeReadFingerprint
    from koinon.knowledge.evidence_capture import NativeEvidenceFailure

    asset = SimpleNamespace(id="dataset", kind="dataset", name="Owned", workspace_id="canonical-space")
    source = SimpleNamespace(id="source")
    binding = SimpleNamespace(native_id="native-dataset", native_workspace_id="native-space")

    async def query(subject, tenant, **arguments):
        receipt = arguments["_capture"]
        receipt.native_reads.append(
            NativeReadFingerprint(
                "grounding",
                "structured",
                tenant,
                "native-space",
                "native-dataset",
                "f" * 64,
                ("native-column",),
                ("pin",),
            )
        )
        attempt = receipt.sql_begin("candidate", "SELECT sum(total) FROM orders")
        receipt.sql_candidate(attempt, "scope", "SELECT")
        raise AccessDenied("Unsafe internal diagnostic must not escape")

    knowledge = SimpleNamespace(
        _chain=AsyncMock(return_value=[asset, source]), binding=AsyncMock(return_value=binding), query=query
    )
    capture = NativeKnowledgeEvidence(knowledge, SimpleNamespace())
    with pytest.raises(NativeEvidenceFailure) as caught:
        await capture.query("owner", "tenant", dataset_id="dataset", question="Count")
    failure = caught.value
    assert isinstance(failure, AccessDenied) and failure.denied
    assert failure.capture.data == {} and not failure.capture.complete
    assert failure.capture.native_reads[0].entity_id == "dataset"
    assert failure.capture.native_reads[0].workspace_id == "canonical-space"
    assert failure.capture.sql_attempts[0].outcome == "blocked"
    assert failure.capture.sources[0].used_revision is None
    assert "Unsafe internal" not in str(failure)


async def test_cancelled_capture_preserves_cancellation_and_safe_attempt_observation():
    import asyncio

    from koinon.knowledge.evidence_capture import failure_capture

    asset = SimpleNamespace(id="dataset", kind="dataset", name="Owned", workspace_id="canonical-space")
    binding = SimpleNamespace(native_id="native-dataset", native_workspace_id="native-space")

    async def query(subject, tenant, **arguments):
        receipt = arguments["_capture"]
        attempt = receipt.sql_begin("candidate", "SELECT total FROM orders")
        receipt.sql_started(attempt)
        receipt.sql_failed(attempt, True)
        raise asyncio.CancelledError()

    knowledge = SimpleNamespace(
        _chain=AsyncMock(return_value=[asset, SimpleNamespace(id="source")]),
        binding=AsyncMock(return_value=binding),
        query=query,
    )
    capture = NativeKnowledgeEvidence(knowledge, SimpleNamespace())
    with pytest.raises(asyncio.CancelledError) as caught:
        await capture.query("owner", "tenant", dataset_id="dataset", question="Count")
    observed = failure_capture(caught.value)
    assert observed is not None and not observed.complete and observed.data == {}
    assert observed.sources[0].asset_id == "dataset"
    assert observed.sql_attempts[0].outcome == "cancelled"
