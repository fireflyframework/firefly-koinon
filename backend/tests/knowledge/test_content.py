# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from hashlib import sha256
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from test_facade import context as context
from test_facade import upload


def updates(context):
    from koinon.knowledge.content import ContentUpdates

    facade, _, domains, _, _ = context
    domains.replace_document = AsyncMock(
        return_value={
            "previous_chunk_count": 2,
            "invalidated_chunk_ids": ["old-1", "old-2"],
            "chunk_ids_complete": True,
            "n_chunks": 1,
            "unchanged": False,
        }
    )
    domains.document_revision = AsyncMock(return_value=None)
    domains.reupload_table = AsyncMock(
        return_value={
            "file_id": "new-file",
            "previous_snapshot_id": "snapshot-old",
            "snapshot_id": "snapshot-new",
            "n_columns": 2,
            "n_rows_actual": 3,
        }
    )
    return ContentUpdates(facade)


async def test_extra_source_alias_requires_its_own_review_even_when_the_editor_can_write_it(context):
    from pyfly.kernel import ConflictException

    service = updates(context)
    facade, catalog, domains, tree, _ = context
    uploaded = await upload(context)
    document = uploaded["assets"][0]["id"]
    alias = await catalog.create(
        "issuer|admin",
        "north",
        kind="source",
        name="Other source",
        parent_id=tree["collection"].id,
        metadata={"sha256": "b" * 64},
    )
    binding = await facade.binding("north", document, "canon")
    await facade._bind(
        "issuer|admin", "north", alias, "canon", binding.native_id, binding.native_workspace_id, {}
    )
    with pytest.raises(ConflictException) as failure:
        await service.document(
            "issuer|admin",
            "north",
            document,
            filename="new.txt",
            content=b"new",
            expected_sha256="a" * 64,
            acknowledge_chunk_invalidation=True,
        )
    assert failure.value.code == "DOCUMENT_ALIASED_CHANGE_REVIEW_REQUIRED"
    domains.replace_document.assert_not_awaited()
    assert (await catalog.get("issuer|admin", "north", alias.id)).metadata_json["sha256"] == "b" * 64


async def test_content_updates_deny_role_archive_and_alias_pat_write_before_native_mutation(context):
    from koinon.catalog.errors import AccessDenied

    service = updates(context)
    facade, catalog, domains, tree, _ = context
    result = await upload(context)
    document = result["assets"][0]["id"]
    arguments = {
        "filename": "new.txt",
        "content": b"new",
        "expected_sha256": "a" * 64,
        "acknowledge_chunk_invalidation": True,
    }
    with pytest.raises(AccessDenied):
        await service.document("issuer|reader", "north", document, **arguments)
    with pytest.raises(AccessDenied):
        await service.document("issuer|outsider", "north", document, **arguments)

    async def restrict(subject, entry, *, write=False):
        if write and entry.kind == "source":
            raise AccessDenied("The selected token cannot write this alias", code="TOKEN_SCOPE_DENIED")

    catalog.restriction = SimpleNamespace(grant=AsyncMock(return_value=None), resource=restrict)
    with pytest.raises(AccessDenied):
        await service.document("issuer|admin", "north", document, **arguments)
    catalog.restriction = None
    await catalog.archive("issuer|admin", "north", tree["collection"].id)
    with pytest.raises(AccessDenied):
        await service.document("issuer|admin", "north", document, **arguments)
    domains.replace_document.assert_not_awaited()
    assert not await catalog.list("issuer|admin", "north", kind="index_version")


async def test_document_replacement_preserves_bindings_and_records_actual_invalidation(context):
    service = updates(context)
    facade, catalog, domains, _, _ = context
    result = await upload(context)
    identifier = result["assets"][0]["id"]
    binding = await facade.binding("north", identifier, "canon")
    response = await service.document(
        "issuer|admin",
        "north",
        identifier,
        filename="v2.md",
        content=b"new facts",
        expected_sha256="a" * 64,
        acknowledge_chunk_invalidation=True,
    )
    assert response["asset"]["id"] == identifier
    assert response["effects"]["invalidated_chunk_ids"] == ["old-1", "old-2"]
    assert response["effects"]["citation_rows_preserved"] is True
    assert response["version"]["status"] == "ready"
    assert response["version"]["kind"] == "index_version"
    assert (await facade.binding("north", identifier, "canon")).id == binding.id
    assert domains.replace_document.await_args.kwargs["source_id"] == "native-source"
    assert domains.replace_document.await_args.kwargs["actor"] == "issuer|admin"
    assert (await catalog.get("issuer|admin", "north", identifier)).metadata_json["sha256"] == sha256(
        b"new facts"
    ).hexdigest()


async def test_document_replacement_requires_explicit_effect_and_version_precondition(context):
    from pyfly.kernel import InvalidRequestException

    service = updates(context)
    _, _, domains, _, _ = context
    document = (await upload(context))["assets"][0]["id"]
    for changes in (
        {"expected_sha256": None, "acknowledge_chunk_invalidation": True},
        {"expected_sha256": "a" * 64, "acknowledge_chunk_invalidation": False},
    ):
        with pytest.raises(InvalidRequestException):
            await service.document(
                "issuer|admin", "north", document, filename="new.txt", content=b"new", **changes
            )
    domains.replace_document.assert_not_awaited()


async def test_writable_legacy_aliases_are_not_explicit_consent_to_change_two_documents(context):
    from pyfly.kernel import ConflictException

    service = updates(context)
    _, catalog, domains, _, _ = context
    first = (await upload(context))["assets"][0]["id"]
    second = (await upload(context))["assets"][0]["id"]
    assert first != second
    with pytest.raises(ConflictException) as rejected:
        await service.document(
            "issuer|admin",
            "north",
            first,
            filename="one.txt",
            content=b"new",
            expected_sha256="a" * 64,
            acknowledge_chunk_invalidation=True,
        )
    assert rejected.value.code == "DOCUMENT_ALIASED_CHANGE_REVIEW_REQUIRED"
    domains.replace_document.assert_not_awaited()
    assert not await catalog.list("issuer|admin", "north", kind="index_version")


async def test_recorded_document_requires_exact_paired_revision_before_creating_an_attempt(context):
    from pyfly.kernel import ConflictException

    service = updates(context)
    _, catalog, domains, _, _ = context
    document = (await upload(context))["assets"][0]["id"]
    version, extraction = str(uuid4()), str(uuid4())
    domains.document_revision.return_value = {"source_version_id": version, "extraction_id": extraction}
    kwargs = dict(
        filename="next.txt", content=b"new", expected_sha256="a" * 64, acknowledge_chunk_invalidation=True
    )
    with pytest.raises(ConflictException):
        await service.document("issuer|admin", "north", document, **kwargs)
    with pytest.raises(ConflictException):
        await service.document(
            "issuer|admin",
            "north",
            document,
            **kwargs,
            expected_source_version_id=version,
            expected_extraction_id=str(uuid4()),
        )
    domains.replace_document.assert_not_awaited()
    assert not await catalog.list("issuer|admin", "north", kind="index_version")


async def test_content_failure_records_error_and_stale_precondition_keeps_old_asset_ready(context):
    from pyfly.kernel import ConflictException

    service = updates(context)
    _, catalog, domains, _, _ = context
    document = (await upload(context))["assets"][0]["id"]
    arguments = {
        "filename": "v2.txt",
        "content": b"new",
        "expected_sha256": "a" * 64,
        "acknowledge_chunk_invalidation": True,
    }
    domains.replace_document.side_effect = ConflictException("Stale content", code="CONTENT_VERSION_CONFLICT")
    with pytest.raises(ConflictException):
        await service.document("issuer|admin", "north", document, **arguments)
    assert (await catalog.get("issuer|admin", "north", document)).status == "ready"
    domains.replace_document.side_effect = RuntimeError("Provider failed")
    with pytest.raises(RuntimeError):
        await service.document("issuer|admin", "north", document, **arguments)
    assert (await catalog.get("issuer|admin", "north", document)).status == "ready"
    versions = await catalog.list("issuer|admin", "north", kind="index_version")
    assert len(versions) == 2 and all(version.status == "error" for version in versions)


async def test_table_reupload_checks_exact_parent_and_preserves_snapshot_provenance(context):
    from koinon.catalog.errors import InvalidHierarchy

    service = updates(context)
    facade, catalog, domains, _, _ = context
    domains.ingest_dataset.return_value["tables"] = [
        {"table_id": "native-table", "name": "orders", "snapshot_id": "snapshot-old"}
    ]
    dataset = (await upload(context, "dataset"))["assets"][0]["id"]
    table = (await catalog.list("issuer|admin", "north", kind="table", parent_id=dataset))[0]
    with pytest.raises(InvalidHierarchy):
        await service.table(
            "issuer|admin",
            "north",
            "wrong-dataset",
            table.id,
            filename="orders.csv",
            content=b"new",
            expected_snapshot_id="snapshot-old",
        )
    domains.reupload_table.assert_not_awaited()
    binding = await facade.binding("north", table.id, "structured")
    response = await service.table(
        "issuer|admin",
        "north",
        dataset,
        table.id,
        filename="orders.csv",
        content=b"new",
        expected_snapshot_id="snapshot-old",
    )
    assert response["effects"]["previous_snapshot_id"] == "snapshot-old"
    assert response["effects"]["snapshot_id"] == "snapshot-new"
    assert response["effects"]["historical_snapshots_preserved"] is True
    assert response["table"]["metadata"]["snapshot_id"] == "snapshot-new"
    assert (await facade.binding("north", table.id, "structured")).id == binding.id
    assert domains.reupload_table.await_args.kwargs["dataset_id"] == "native-dataset"
    assert domains.reupload_table.await_args.kwargs["table_id"] == "native-table"


async def test_reupload_checks_every_deduplicated_table_alias_before_native_access(context):
    from koinon.catalog.errors import AccessDenied

    service = updates(context)
    facade, catalog, domains, _, _ = context
    domains.ingest_dataset.return_value["tables"] = [
        {"table_id": "native-table", "name": "orders", "snapshot_id": "snapshot-old"}
    ]
    dataset = (await upload(context, "dataset"))["assets"][0]["id"]
    table = (await catalog.list("issuer|admin", "north", kind="table", parent_id=dataset))[0]
    alias = await catalog.create("issuer|admin", "north", kind="table", name="alias", parent_id=dataset)
    await facade._bind("issuer|admin", "north", alias, "structured", "native-table", "native-workspace")
    await catalog.archive("issuer|admin", "north", alias.id)
    with pytest.raises(AccessDenied, match="archived"):
        await service.table(
            "issuer|admin",
            "north",
            dataset,
            table.id,
            filename="orders.csv",
            content=b"new",
            expected_snapshot_id="snapshot-old",
        )
    domains.reupload_table.assert_not_awaited()
