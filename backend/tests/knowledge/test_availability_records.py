# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from unittest.mock import AsyncMock

import pytest
from test_facade import context as context
from test_facade import upload

from koinon.catalog.errors import InvalidHierarchy
from koinon.catalog.mappers import entry_dto
from koinon.knowledge.availability.repository import ATTEMPT_KEY, AvailabilityRepository
from koinon.knowledge.availability.service import KnowledgeAvailabilityService
from koinon.knowledge.content import ContentUpdates
from koinon.security.authority import primary_authority


async def projection(facade, document):
    async with primary_authority(fresh=True):
        entry = await facade.catalog.get("issuer|admin", "north", document)
        return (await AvailabilityRepository().load("north", [entry]))[document]


async def test_public_create_cannot_forge_marker_and_patch_cannot_forge_or_clear(context):
    facade, catalog, _, tree, _ = context
    for kind, parent in (
        ("project", tree["workspace"].id),
        ("collection", tree["collection"].id),
        ("source", tree["collection"].id),
    ):
        with pytest.raises(InvalidHierarchy, match="Reserved"):
            await catalog.create(
                "issuer|admin",
                "north",
                kind=kind,
                name="forged",
                parent_id=parent,
                metadata={ATTEMPT_KEY: {"operation": "document.replace"}},
            )
    document = (await upload(context))["assets"][0]["id"]
    updates = ContentUpdates(facade)
    source = (await facade._chain("issuer|admin", "north", document))[1]
    version = await updates._version("issuer|admin", "north", source.id, "document.replace", "new", b"new")
    with pytest.raises(InvalidHierarchy, match="Reserved"):
        await catalog.update("issuer|admin", "north", version.id, {"metadata": {ATTEMPT_KEY: None}})
    await catalog.update("issuer|admin", "north", version.id, {"metadata": {"description": "safe"}})
    current = await catalog.get("issuer|admin", "north", version.id)
    assert current.metadata_json[ATTEMPT_KEY] == {"operation": "document.replace", "state": "unknown"}
    assert ATTEMPT_KEY not in entry_dto(current)["metadata"]


async def test_forged_old_history_is_unknown_but_server_marked_failure_is_latest_attempt(context):
    facade, catalog, domains, _, _ = context
    document = (await upload(context))["assets"][0]["id"]
    source = (await facade._chain("issuer|admin", "north", document))[1]
    fake = await catalog.create(
        "issuer|admin",
        "north",
        kind="index_version",
        name="fake",
        parent_id=source.id,
        metadata={"operation": "document.replace"},
    )
    await catalog.update("issuer|admin", "north", fake.id, {"status": "error"})
    assert (await projection(facade, document))["latest_attempt"] is None
    # Model a pre-upgrade row, before this marker name was reserved by the public API.
    fake.metadata_json[ATTEMPT_KEY] = {"operation": "document.replace", "state": "failed"}
    await catalog.catalog_repository.save(fake)
    assert (await projection(facade, document))["latest_attempt"] is None
    domains.document_revision = AsyncMock(return_value=None)
    domains.replace_document = AsyncMock(side_effect=RuntimeError("provider fixture"))
    with pytest.raises(RuntimeError):
        await ContentUpdates(facade).document(
            "issuer|admin",
            "north",
            document,
            filename="v2.txt",
            content=b"new",
            expected_sha256="a" * 64,
            acknowledge_chunk_invalidation=True,
        )
    selected = await projection(facade, document)
    assert selected["latest_attempt"]["state"] == "failed"
    assert selected["latest_attempt"]["id"] != fake.id
    assert (await catalog.get("issuer|admin", "north", document)).status == "ready"


async def test_reader_foreign_asset_and_live_revocation_are_enforced_before_observation(context):
    from koinon.catalog.errors import AccessDenied
    from koinon.catalog.repositories import MembershipRepository
    from koinon.knowledge.availability.dtos import AvailabilityRequest

    facade, _, _, _, app = context
    document = (await upload(context))["assets"][0]["id"]
    native = type("Native", (), {"observe": AsyncMock(return_value={})})()
    service = KnowledgeAvailabilityService(facade, AvailabilityRepository(), native)
    request = AvailabilityRequest(asset_ids=[document])
    await service.observe("issuer|reader", "north", request)
    with pytest.raises(AccessDenied):
        await service.observe("issuer|outsider", "north", request)
    members = app.get_bean(MembershipRepository)
    member = await members.find_by_id("reader")
    member.active = False
    await members.save(member)
    native.observe.reset_mock()
    with pytest.raises(AccessDenied):
        await service.observe("issuer|reader", "north", request)
    native.observe.assert_not_awaited()


async def test_processing_page_is_admin_only_bounded_and_excludes_unmarked_history(context):
    from koinon.catalog.errors import AccessDenied
    from koinon.knowledge.availability.dtos import ProcessingRequest

    facade, catalog, _, _, _ = context
    document = (await upload(context))["assets"][0]["id"]
    source = (await facade._chain("issuer|admin", "north", document))[1]
    await catalog.create(
        "issuer|admin",
        "north",
        kind="index_version",
        name="old",
        parent_id=source.id,
        metadata={"operation": "document.replace"},
    )
    updates = ContentUpdates(facade)
    for name in ("one", "two"):
        version = await updates._version("issuer|admin", "north", source.id, "document.replace", name, b"new")
        await updates._finish_version("issuer|admin", "north", version, {"status": "error"}, "failed")
    native = type("Native", (), {"observe": AsyncMock(return_value={})})()
    service = KnowledgeAvailabilityService(facade, AvailabilityRepository(), native)
    with pytest.raises(AccessDenied):
        await service.processing("issuer|reader", "north", ProcessingRequest())
    first = await service.processing("issuer|admin", "north", ProcessingRequest(page_size=1))
    second = await service.processing("issuer|admin", "north", ProcessingRequest(page=2, page_size=1))
    assert len(first.items) == len(second.items) == 1 and first.next_page == 2
    assert first.items[0].id != second.items[0].id and second.next_page is None
    assert first.items[0].state == "failed" and first.items[0].resource_id == source.id


async def test_native_workspace_must_match_the_admitted_workspace_binding(context):
    facade, _, _, _, _ = context
    document = (await upload(context))["assets"][0]["id"]
    async with primary_authority(fresh=True):
        binding = await facade.binding("north", document, "canon")
    binding.native_workspace_id = "unrelated-native-workspace"
    await facade.bindings.save(binding)
    selected = await projection(facade, document)
    assert selected["native_id"] is None and selected["native_workspace_id"] is None


async def test_processing_requires_exact_durable_job_and_current_live_lease(context):
    from datetime import UTC, datetime, timedelta

    from pyfly.data.transaction import TransactionTemplate

    from koinon.jobs.entities import Job
    from koinon.knowledge.bulk.entities import BulkBatch, BulkItem

    facade, _, _, _, _ = context
    document = (await upload(context))["assets"][0]["id"]
    chain = await facade._chain("issuer|admin", "north", document)
    asset, source = chain[:2]
    async with TransactionTemplate("primary").transaction() as unit:
        session = unit.resource
        session.add(
            BulkBatch(
                id="batch",
                tenant_id="north",
                subject="issuer|admin",
                workspace_id=asset.workspace_id,
                project_id=asset.project_id,
                parent_id=source.parent_id,
                key_hash="a" * 64,
                request_hash="b" * 64,
                request_json={},
                total_bytes=1,
                expires_at=datetime.now(UTC) + timedelta(hours=1),
            )
        )
        session.add(
            Job(
                id="job",
                tenant_id="north",
                resource_id=asset.id,
                kind="knowledge.bulk.intake",
                idempotency_key="queued-proof",
                payload_hash="c" * 64,
                status="queued",
            )
        )
        await session.flush()
        session.add(
            BulkItem(
                id="item",
                batch_id="batch",
                ordinal=0,
                client_item_id="one",
                filename="fixture.txt",
                mode="document",
                size_bytes=1,
                sha256="d" * 64,
                source_id=source.id,
                asset_id=asset.id,
                job_id="job",
                status="queued",
            )
        )
    assert (await projection(facade, document))["phase"] == "queued"
    async with TransactionTemplate("primary").transaction() as unit:
        job = await unit.resource.get(Job, "job")
        item = await unit.resource.get(BulkItem, "item")
        job.status = item.status = "running"
        job.lease_until = datetime.now(UTC) + timedelta(hours=1)
    assert (await projection(facade, document))["phase"] == "processing"
    async with TransactionTemplate("primary").transaction() as unit:
        job = await unit.resource.get(Job, "job")
        job.lease_until = datetime.now(UTC) - timedelta(hours=1)
    assert (await projection(facade, document))["phase"] == "unknown"


async def test_public_status_edits_cannot_forge_a_recorded_attempt_outcome(context):
    facade, catalog, _, _, _ = context
    document = (await upload(context))["assets"][0]["id"]
    source = (await facade._chain("issuer|admin", "north", document))[1]
    updates = ContentUpdates(facade)
    version = await updates._version("issuer|admin", "north", source.id, "document.replace", "new", b"new")
    await catalog.update("issuer|admin", "north", version.id, {"status": "error"})
    assert (await projection(facade, document))["latest_attempt"]["state"] == "unknown"
    await updates._finish_version("issuer|admin", "north", version, {"status": "error"}, "failed")
    await catalog.update("issuer|admin", "north", version.id, {"status": "ready"})
    assert (await projection(facade, document))["latest_attempt"]["state"] == "failed"
