# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import importlib.util
import json
from pathlib import Path

import pytest
from pyfly.kernel import ConflictException

from koinon.catalog.errors import AccessDenied
from koinon.exports.dtos import ConversationExportInput, ExportCreate
from koinon.exports.service import KnowledgeExports

fixture_spec = importlib.util.spec_from_file_location(
    "export_review_fixture", Path(__file__).resolve().parents[1] / "evidence/test_evidence_reviews.py"
)
assert fixture_spec and fixture_spec.loader
fixture_module = importlib.util.module_from_spec(fixture_spec)
fixture_spec.loader.exec_module(fixture_module)
reviews = fixture_module.reviews


async def test_review_shows_actual_selection_and_download_is_immutable(reviews):
    _, snapshot, context = reviews
    service = context.get_bean(KnowledgeExports)
    preview = await service.preview(
        "owner",
        "north",
        ConversationExportInput(kind="conversation", thread_id="t", message_ids=["m"], format="json"),
    )
    assert preview.messages[0].text == "Reviewed answer"
    assert preview.completeness == "selected_messages"
    body = ExportCreate(review_id=preview.id, expected_revision=preview.revision)
    created = await service.create("owner", "north", body)
    snapshot.revision = "b" * 64
    first = await service.download("owner", "north", created.id)
    second = await service.download("owner", "north", created.id)
    assert first.content == second.content
    payload = json.loads(first.content)
    assert payload["revision"] == "a" * 64
    assert payload["exported_at"] == created.created_at.isoformat()
    assert "owner_subject" not in payload and "originating_token_ids" not in payload
    with pytest.raises(ConflictException):
        await service.create("owner", "north", body)
    with pytest.raises(AccessDenied):
        await service.download("other", "north", created.id)


async def test_cancel_retains_metadata_and_prevents_download(reviews):
    _, _, context = reviews
    service = context.get_bean(KnowledgeExports)
    preview = await service.preview(
        "owner",
        "north",
        ConversationExportInput(kind="conversation", thread_id="t", message_ids=["m"], format="markdown"),
    )
    created = await service.create(
        "owner", "north", ExportCreate(review_id=preview.id, expected_revision=preview.revision)
    )
    assert (await service.page("owner", "north", q="Review", page_size=1)).total == 1
    assert (await service.page("owner", "north", q="missing")).total == 0
    await service.cancel("owner", "north", created.id)
    await service.cancel("owner", "north", created.id)
    assert (await service.get("owner", "north", created.id)).status == "cancelled"
    with pytest.raises(AccessDenied):
        await service.download("owner", "north", created.id)


async def test_stored_result_export_preserves_unknown_completeness_and_rejects_changed_bytes(reviews):
    from datetime import UTC, datetime
    from hashlib import sha256
    from io import BytesIO

    import pyarrow as pa
    import pyarrow.parquet as pq

    from koinon.catalog.repositories import MembershipRepository
    from koinon.catalog.service import CatalogService
    from koinon.evidence.dtos import ResultColumn, StoredResult
    from koinon.evidence.ports import StoredResultPort
    from koinon.exports.dtos import QueryResultExportInput

    _, _, context = reviews
    members = context.get_bean(MembershipRepository)
    owner = await members.find_by_id("owner")
    owner.role = "admin"
    await members.save(owner)
    catalog = context.get_bean(CatalogService)
    parent = None
    for kind in ("workspace", "project", "collection", "source", "dataset"):
        parent = await catalog.create(
            "owner", "north", kind=kind, name=kind, parent_id=parent.id if parent else None
        )
    dataset_id = parent.id
    buffer = BytesIO()
    pq.write_table(pa.table({"exact_id": [9007199254740993], "name": ["=unsafe"]}), buffer)
    original = buffer.getvalue()

    class StoredFixture:
        changed = False

        async def describe(self, subject, tenant_id, dataset_id, query_id):
            return StoredResult(
                asset_id=dataset_id,
                query_id=query_id,
                revision=sha256(original).hexdigest(),
                row_count=1,
                row_cap=None,
                truncated=None,
                byte_size=len(original),
                columns=(
                    ResultColumn(name="exact_id", data_type="int64"),
                    ResultColumn(name="name", data_type="string"),
                ),
                expires_at=datetime(2099, 1, 1, tzinfo=UTC),
            )

        async def read(self, subject, tenant_id, result):
            yield b"changed" if self.changed else original

    port = StoredFixture()
    context.container.register_instance(StoredResultPort, port)
    service = context.get_bean(KnowledgeExports)
    preview = await service.preview(
        "owner",
        "north",
        QueryResultExportInput(kind="query_result", dataset_id=dataset_id, query_id="query", format="jsonl"),
    )
    assert preview.completeness == "unknown" and preview.truncated is None and preview.row_cap is None
    assert preview.result.revision == sha256(original).hexdigest()
    assert preview.result.snapshot_manifest_complete is False and preview.omissions
    created = await service.create(
        "owner", "north", ExportCreate(review_id=preview.id, expected_revision=preview.revision)
    )
    downloaded = await service.download("owner", "north", created.id)
    assert json.loads(downloaded.content) == {"exact_id": "9007199254740993", "name": "=unsafe"}
    assert downloaded.filename.endswith("-stored-result.jsonl")
    assert dict(downloaded.headers)["X-Koinon-Truncated"] == "unknown"
    assert dict(downloaded.headers)["X-Koinon-Stored-Rows"] == "1"
    port.changed = True
    with pytest.raises(ConflictException):
        await service.download("owner", "north", created.id)


async def test_failed_export_creation_rolls_back_review_consumption_for_a_safe_retry(reviews, monkeypatch):
    from unittest.mock import AsyncMock

    from koinon.evidence.repositories import EvidenceReviewRepository

    _, _, context = reviews
    service = context.get_bean(KnowledgeExports)
    preview = await service.preview(
        "owner",
        "north",
        ConversationExportInput(kind="conversation", thread_id="t", message_ids=["m"], format="json"),
    )
    body = ExportCreate(review_id=preview.id, expected_revision=preview.revision)
    original = service.reviews.catalog._audit
    monkeypatch.setattr(
        service.reviews.catalog, "_audit", AsyncMock(side_effect=RuntimeError("audit write failed"))
    )
    with pytest.raises(RuntimeError, match="audit write failed"):
        await service.create("owner", "north", body)
    row = await context.get_bean(EvidenceReviewRepository).find_by_id(preview.id)
    assert row.consumed_at is None
    assert (await service.page("owner", "north")).total == 0
    monkeypatch.setattr(service.reviews.catalog, "_audit", original)
    assert (await service.create("owner", "north", body)).status == "ready"


async def test_export_download_admission_is_bounded_and_released_after_failure(reviews, monkeypatch):
    from unittest.mock import Mock

    from pyfly.kernel import PayloadTooLargeException

    _, _, context = reviews
    service = context.get_bean(KnowledgeExports)
    preview = await service.preview(
        "owner",
        "north",
        ConversationExportInput(kind="conversation", thread_id="t", message_ids=["m"], format="json"),
    )
    created = await service.create(
        "owner", "north", ExportCreate(review_id=preview.id, expected_revision=preview.revision)
    )
    service._downloads = service.reviews.settings.max_concurrent_downloads
    with pytest.raises(ConflictException, match="download"):
        await service.download("owner", "north", created.id)
    service._downloads = 0
    monkeypatch.setattr(
        "koinon.exports.service.render_transcript",
        Mock(side_effect=PayloadTooLargeException("download limit")),
    )
    with pytest.raises(PayloadTooLargeException, match="download limit"):
        await service.download("owner", "north", created.id)
    assert service._downloads == 0


async def test_export_expiry_does_not_outlive_its_originating_authority(reviews):
    from datetime import UTC, datetime, timedelta

    from koinon.tokens.entities import PersonalToken
    from koinon.tokens.repositories import PersonalTokenRepository

    _, snapshot, context = reviews
    expiry = datetime.now(UTC) + timedelta(minutes=5)
    await context.get_bean(PersonalTokenRepository).save(
        PersonalToken(
            id="origin-token",
            subject="owner",
            tenant_id="north",
            name="Bounded origin",
            token_hash="a" * 64,
            prefix="fixture",
            scopes=["chat:use", "catalog:read"],
            expires_at=expiry,
        )
    )
    snapshot.origin_tokens = ("origin-token",)
    service = context.get_bean(KnowledgeExports)
    preview = await service.preview(
        "owner",
        "north",
        ConversationExportInput(kind="conversation", thread_id="t", message_ids=["m"], format="json"),
    )
    created = await service.create(
        "owner", "north", ExportCreate(review_id=preview.id, expected_revision=preview.revision)
    )
    assert created.expires_at == expiry
