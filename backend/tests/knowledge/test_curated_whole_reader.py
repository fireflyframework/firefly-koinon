# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Whole-version reads recheck authority and exact serving identity after I/O."""

from importlib import import_module, util
from types import MethodType, SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from test_curated_whole_views import _inputs

from koinon.catalog.errors import AccessDenied
from koinon.knowledge.capture_dtos import NativeDatabaseContext
from koinon.knowledge.curated.release_dtos import CuratedReleaseStamp


def _reader():
    assert util.find_spec("koinon.knowledge.curated.whole") is not None, (
        "A framework-managed whole-version reader is required before enabling curated RLM"
    )
    mapper, dtos, value, selection, meta, parts = _inputs()
    entry = SimpleNamespace(
        id="item", kind="knowledge_item", workspace_id="canonical-workspace", status="active"
    )
    state = SimpleNamespace(
        tenant_id="north",
        workspace_id="canonical-workspace",
        item_id="item",
        native_item_id="native-item",
        native_workspace_id="native-workspace",
        serving_version_id="version-one",
        serving_version=1,
        serving_operation_id="approved-operation",
    )
    reads = SimpleNamespace(
        scope=AsyncMock(return_value=(entry, state)),
        version=AsyncMock(return_value=value),
        authority=SimpleNamespace(catalog=SimpleNamespace(authorize=AsyncMock())),
    )
    projection = dtos.CuratedProjection(parts, NativeDatabaseContext("sqlite", None, None, None))
    repository = SimpleNamespace(assert_serving=AsyncMock(), read=AsyncMock(return_value=projection))
    cls = import_module("koinon.knowledge.curated.whole").CuratedWholeVersionReader
    stamp = CuratedReleaseStamp("0" * 64, "0" * 64, 0)
    reader = cls(
        reads,
        repository,
        reads.authority,
        SimpleNamespace(
            observe=AsyncMock(return_value=stamp),
            observe_bound=AsyncMock(return_value=stamp),
            require_unchanged=AsyncMock(),
        ),
    )
    # Native transaction boundaries are exercised separately by test_curated_whole_native.
    reader._authorize_current = MethodType(cls._authorize_current.__wrapped__, reader)
    return reader, reads, repository, value, selection, meta, state, projection


async def test_reader_returns_only_the_exact_published_pin_and_observed_native_context():
    reader, reads, repository, value, selection, meta, _, _ = _reader()
    assert await reader.pin("issuer|reader", "north", "native-workspace", selection) == meta
    result = await reader.read("issuer|reader", "north", meta)
    assert result.text == value.selected_version.content.body
    assert result.meta == meta
    assert result.database.engine == "sqlite"
    assert reads.scope.await_count >= 4
    assert reads.version.await_count >= 3
    assert repository.assert_serving.await_count >= 2
    reads.authority.catalog.authorize.assert_awaited_with(
        "issuer|reader", "north", "knowledge:search", "canonical-workspace"
    )


async def test_permission_revocation_while_parts_are_pending_prevents_text_release():
    reader, reads, repository, _, _, meta, _, projection = _reader()

    async def parts(*args, **kwargs):
        reads.authority.catalog.authorize.side_effect = AccessDenied("Removed membership")
        return projection

    repository.read.side_effect = parts
    with pytest.raises(AccessDenied):
        await reader.read("issuer|reader", "north", meta)


@pytest.mark.parametrize(
    "change",
    [
        "serving_version_id",
        "serving_version",
        "serving_operation_id",
        "native_item_id",
        "native_workspace_id",
        "workspace_id",
    ],
)
async def test_primary_ack_or_binding_change_during_read_does_not_silently_repin(change):
    reader, reads, repository, _, _, meta, state, projection = _reader()

    async def parts(*args, **kwargs):
        setattr(state, change, 2 if change == "serving_version" else "replaced")
        return projection

    repository.read.side_effect = parts
    with pytest.raises(Exception) as caught:
        await reader.read("issuer|reader", "north", meta)
    assert getattr(caught.value, "code", None) == "KNOWLEDGE_VERSION_CONFLICT"


@pytest.mark.parametrize("field", ["author_subject", "operation_id", "committed_at"])
async def test_immutable_metadata_change_after_body_query_rejects_the_original_pin(field):
    from datetime import UTC, datetime

    reader, reads, repository, value, _, meta, _, projection = _reader()

    async def parts(*args, **kwargs):
        changed = datetime(2026, 10, 31, tzinfo=UTC) if field == "committed_at" else "changed"
        reads.version.return_value = value.model_copy(
            update={"selected_version": value.selected_version.model_copy(update={field: changed})}
        )
        return projection

    repository.read.side_effect = parts
    with pytest.raises(Exception) as caught:
        await reader.read("issuer|reader", "north", meta)
    assert getattr(caught.value, "code", None) == "KNOWLEDGE_VERSION_CONFLICT"


async def test_native_retirement_or_head_mismatch_blocks_even_metadata_admission():
    from pyfly.kernel import ConflictException

    reader, _, repository, _, selection, _, _, _ = _reader()
    repository.assert_serving.side_effect = ConflictException(
        "Native head changed", code="KNOWLEDGE_VERSION_CONFLICT"
    )
    with pytest.raises(ConflictException):
        await reader.pin("issuer|reader", "north", "native-workspace", selection)
    repository.read.assert_not_awaited()
