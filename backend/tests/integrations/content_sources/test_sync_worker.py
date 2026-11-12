# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Bounded source execution against actual primary transactions and provider pages."""

from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pyfly.kernel import ConflictException
from test_connection_lifecycle import lifecycle as lifecycle
from test_mapping_policy_service import empty_listing as empty_listing
from test_mapping_review import review as review
from test_source_migration_postgres import source_database as source_database
from test_sync_publication_service import claimed_source_file as claimed_source_file
from test_sync_publication_service import producer as producer
from test_sync_publication_service import source_files as source_files

from koinon.integrations.content_sources.account_operations import SourceAccountOperations
from koinon.integrations.content_sources.credentials import SourceCredentialVault
from koinon.integrations.content_sources.dtos import Cursor, ItemPage, RemoteItem, SourceScope
from koinon.integrations.content_sources.mapping_policies import SourcePolicies
from koinon.integrations.content_sources.mapping_service import SourceMappings
from koinon.integrations.content_sources.settings import ContentSourceSettings
from koinon.integrations.content_sources.source_publication import SourcePublicationWriter
from koinon.integrations.content_sources.sync_dtos import (
    SourceControlInput,
    SourcePolicyApplyInput,
    SourcePolicyReviewInput,
)
from koinon.integrations.content_sources.sync_entities import SourceSyncRun, SourceSyncState
from koinon.integrations.content_sources.sync_files import SourceFiles
from koinon.integrations.content_sources.sync_folders import SourceFolders
from koinon.integrations.content_sources.sync_heartbeat import SourceSyncHeartbeat
from koinon.integrations.content_sources.sync_replacement import SourceReplacements
from koinon.integrations.content_sources.sync_runs import SourceRunLease, SourceRunRepository
from koinon.integrations.content_sources.sync_worker import SourceSyncWorker
from koinon.jobs.entities import Job
from koinon.knowledge.bulk.ports import SourceIntakeAdmission, SourceIntakeItem
from koinon.security.authority import primary_authority
from koinon.workers.admission import WorkAdmission, WorkAdmissionSettings

pytestmark = pytest.mark.integration


@pytest.fixture
async def worker(empty_listing, monkeypatch, request):
    value = empty_listing
    mappings = value.context.get_bean(SourceMappings)
    if getattr(request, "param", None) == "file":
        value.request = value.request.model_copy(update={"recursive": False})
        folder_source = mappings.browser._source

        @asynccontextmanager
        async def selected_file(scope, tokens):
            async with folder_source(scope, tokens) as adapter:
                original_get = adapter.get_item

                async def get_item(identifier):
                    if identifier == "selected":
                        return RemoteItem(
                            scope,
                            "selected",
                            "selected.bin",
                            "file",
                            "v1",
                            7,
                            "application/octet-stream",
                            ("root",),
                        )
                    return await original_get(identifier)

                adapter.get_item = get_item
                yield adapter

        monkeypatch.setattr(mappings.browser, "_source", selected_file)
    policies = value.context.get_bean(SourcePolicies)
    accepted = await policies.review(
        "issuer|alice",
        "tenant",
        "browser-a",
        SourcePolicyReviewInput(**value.request.model_dump(), operation_id=str(uuid4())),
    )
    await policies.apply(
        "issuer|alice",
        "tenant",
        "browser-a",
        accepted.mapping_id,
        SourcePolicyApplyInput(
            operation_id=str(uuid4()),
            expected_revision=1,
            review_id=accepted.policy_id,
            review_digest=accepted.review_digest,
        ),
    )
    queued = await mappings.execute(
        "issuer|alice",
        "tenant",
        accepted.mapping_id,
        "sync",
        SourceControlInput(
            operation_id=str(uuid4()),
            expected_revision=1,
        ),
    )
    settings = value.context.get_bean(ContentSourceSettings)
    settings.enabled = settings.synchronization_enabled = True
    writer = value.context.get_bean(SourcePublicationWriter)
    capacity = WorkAdmission(WorkAdmissionSettings())
    scope = SourceScope(value.connection.account, "drive")
    original = mappings.browser._source
    pages, calls = [], []

    @asynccontextmanager
    async def source(scope, tokens):
        async with original(scope, tokens) as adapter:

            async def children(identifier, cursor=None):
                if identifier != "selected":
                    return ItemPage((), None)
                calls.append((identifier, cursor.token if cursor else None))
                return pages[len(calls) - 1]

            adapter.children = children
            yield adapter

    monkeypatch.setattr(mappings.browser, "_source", source)

    def service():
        return SourceSyncWorker(
            mappings,
            SourceFolders(writer),
            SourceFiles(writer, mappings),
            SourceReplacements(writer, mappings, None, None),
            capacity,
            settings,
            value.context.get_bean(SourceCredentialVault),
            SourceAccountOperations(mappings.connections),
            SourceSyncHeartbeat(SourceRunRepository(), settings),
        )

    def page(start, count, *, more=False):
        items = tuple(
            RemoteItem(
                scope, str(index), f"{index}.bin", "file", "v1", 1, "application/octet-stream", ("selected",)
            )
            for index in range(start, start + count)
        )
        return ItemPage(items, Cursor(scope, "children:selected", "next") if more else None)

    yield SimpleNamespace(
        review=value,
        service=service,
        worker=service(),
        mappings=mappings,
        settings=settings,
        pages=pages,
        calls=calls,
        page=page,
        run_id=queued.run_id,
        mapping_id=accepted.mapping_id,
    )
    capacity.close_workers()


@pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True)
async def test_worker_captures_configured_bound_and_continues_without_attempt_inflation(worker):
    worker.pages.extend([worker.page(0, 100, more=True), worker.page(100, 1)])
    assert await worker.worker.run_once("tenant", "issuer|alice", worker.run_id) == "running"
    async with primary_authority():
        session = worker.mappings.controls._require_session()
        state = await session.get(SourceSyncState, worker.mapping_id)
        assert (state.scan_max_items, state.scan_observed_count) == (100000, 100)
        run = await session.get(SourceSyncRun, worker.run_id)
        assert (await session.get(Job, run.job_id)).attempts == 1
    assert await worker.worker.run_once("tenant", "issuer|alice", worker.run_id) == "succeeded"
    async with primary_authority():
        session = worker.mappings.controls._require_session()
        state = await session.get(SourceSyncState, worker.mapping_id)
        run = await session.get(SourceSyncRun, worker.run_id)
        assert state.scan_observed_count == 101 and state.last_complete_scan_generation == run.scan_generation
        assert (await session.get(Job, run.job_id)).attempts == 1
    assert worker.calls == [("selected", None), ("selected", "next")]


@pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True)
async def test_worker_restart_preserves_raw_count_and_blocks_cap_plus_one(worker):
    worker.settings.sync_max_scan_items = 100
    worker.pages.extend([worker.page(0, 100, more=True), worker.page(100, 1)])
    assert await worker.worker.run_once("tenant", "issuer|alice", worker.run_id) == "running"
    async with primary_authority(read_only=False):
        session = worker.mappings.controls._require_session()
        run = await session.get(SourceSyncRun, worker.run_id)
        (await session.get(Job, run.job_id)).lease_until = datetime.now(UTC) - timedelta(seconds=1)
    restarted = worker.service()
    assert await restarted.run_once("tenant", "issuer|alice", worker.run_id) == "failed"
    async with primary_authority():
        session = worker.mappings.controls._require_session()
        state = await session.get(SourceSyncState, worker.mapping_id)
        run = await session.get(SourceSyncRun, worker.run_id)
        assert (state.scan_max_items, state.scan_observed_count, state.last_complete_scan_generation) == (
            100,
            101,
            0,
        )
        assert not run.enumeration_complete and run.page_sequence == 1
        assert (await session.get(Job, run.job_id)).attempts == 2
        assert run.counters_json["error_code"] == "SOURCE_SCAN_LIMIT_EXCEEDED"
    assert await worker.worker.run_once("tenant", "issuer|alice", worker.run_id) == "unavailable"
    assert worker.calls == [("selected", None), ("selected", "next")]


@pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True)
async def test_cancelled_worker_never_enumerates_another_page(worker):
    worker.pages.append(worker.page(0, 1, more=True))
    assert await worker.worker.run_once("tenant", "issuer|alice", worker.run_id) == "running"
    async with primary_authority():
        revision = (
            await worker.mappings.controls._require_session().get(SourceSyncState, worker.mapping_id)
        ).revision
    await worker.mappings.execute(
        "issuer|alice",
        "tenant",
        worker.mapping_id,
        "cancel",
        SourceControlInput(
            expected_revision=revision,
            operation_id=str(uuid4()),
        ),
        target_run_id=worker.run_id,
    )
    assert await worker.worker.run_once("tenant", "issuer|alice", worker.run_id) == "cancelled"
    assert worker.calls == [("selected", None)]


@pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True)
@pytest.mark.parametrize("worker", ["file"], indirect=True)
async def test_single_file_worker_retains_one_actual_root_observation_without_listing_children(worker):
    from sqlalchemy import select

    from koinon.integrations.content_sources.mapping_entities import SourceObject

    assert await worker.worker.run_once("tenant", "issuer|alice", worker.run_id) == "succeeded"
    assert worker.calls == []
    async with primary_authority():
        session = worker.mappings.controls._require_session()
        state = await session.get(SourceSyncState, worker.mapping_id)
        origin = await session.scalar(
            select(SourceObject).where(SourceObject.mapping_id == worker.mapping_id)
        )
        assert state.scan_observed_count == 1
        assert (origin.item_id, origin.remote_parent_id, origin.remote_name, origin.remote_ancestry_json) == (
            "selected",
            "root",
            "selected.bin",
            [],
        )


@pytest.mark.parametrize(
    "field", ["tenant_id", "owner", "mapping_id", "run_id", "mapping_revision", "connection_revision"]
)
async def test_dispatch_rejects_foreign_execution_before_resolving_dependencies(field):
    pin = SourceIntakeItem("object", 1, "v1", "observation", "work", 1, 0, "a" * 64)
    admission = SourceIntakeAdmission(
        "tenant", "issuer|alice", "mapping", 1, 1, "run", ("workspace", "project", "folder"), (pin,)
    )
    execution = SourceRunLease(
        "tenant",
        "issuer|alice",
        "mapping",
        "run",
        "job",
        "worker",
        1,
        1,
        1,
        "policy",
        datetime.now(UTC) + timedelta(minutes=1),
        False,
    )
    execution = replace(execution, **{field: 2 if field.endswith("revision") else "foreign"})
    service = SourceSyncWorker(None, None, None, None, None, ContentSourceSettings(), None, None, None)
    with pytest.raises(ConflictException) as failure:
        await service.dispatch(admission, execution)
    assert failure.value.code == "SOURCE_LEASE_LOST"


@pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True)
async def test_retained_initial_native_work_is_not_downloaded_or_dispatched_again(
    claimed_source_file, monkeypatch
):
    from sqlalchemy import select

    from koinon.integrations.content_sources.import_entities import SourceImportAttempt
    from koinon.integrations.content_sources.sync_entities import SourceSyncWork

    value = claimed_source_file.producer
    catalog = value.writer.authority.catalog
    monkeypatch.setattr(catalog, "get", type(catalog).get.__get__(catalog, type(catalog)))
    mappings = value.review.context.get_bean(SourceMappings)
    settings = value.review.context.get_bean(ContentSourceSettings)
    settings.enabled = settings.synchronization_enabled = True
    capacity = WorkAdmission(WorkAdmissionSettings())
    service = SourceSyncWorker(
        mappings,
        SourceFolders(value.writer),
        SourceFiles(value.writer, mappings),
        SourceReplacements(value.writer, mappings, None, None),
        capacity,
        settings,
        value.review.context.get_bean(SourceCredentialVault),
        SourceAccountOperations(mappings.connections),
        SourceSyncHeartbeat(SourceRunRepository(), value.review.context.get_bean(ContentSourceSettings)),
    )
    service._lease = value.execution
    service.worker_id = value.execution.worker_id

    @asynccontextmanager
    async def forbidden_provider(*args):
        raise AssertionError("Retained initial work must not enumerate or download again")
        yield

    monkeypatch.setattr(mappings.browser, "_source", forbidden_provider)
    try:
        assert await service.run_once("tenant", "issuer|alice", value.execution.run_id) == "reconciling"
        async with primary_authority():
            session = value.guard._require_session()
            work = await session.get(SourceSyncWork, value.admission.items[0].work_id)
            attempts = list((await session.scalars(select(SourceImportAttempt))).all())
            assert work.status == "processing" and len(attempts) == 1
            assert work.attempt_id == attempts[0].id and attempts[0].receipt_json is None
    finally:
        capacity.close_workers()


@pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True)
async def test_failed_slice_defers_its_job_and_allows_a_healthy_successor(worker, monkeypatch):
    import asyncio

    from koinon.integrations.content_sources.errors import SourceError

    policies = worker.review.context.get_bean(SourcePolicies)
    request = worker.review.request.model_copy(update={"root_id": "other"})
    approved = await policies.review(
        "issuer|alice",
        "tenant",
        "browser-a",
        SourcePolicyReviewInput(**request.model_dump(), operation_id=str(uuid4())),
    )
    await policies.apply(
        "issuer|alice",
        "tenant",
        "browser-a",
        approved.mapping_id,
        SourcePolicyApplyInput(
            operation_id=str(uuid4()),
            expected_revision=1,
            review_id=approved.policy_id,
            review_digest=approved.review_digest,
        ),
    )
    queued = await worker.mappings.execute(
        "issuer|alice",
        "tenant",
        approved.mapping_id,
        "sync",
        SourceControlInput(operation_id=str(uuid4()), expected_revision=1),
    )
    original = worker.mappings.browser._source

    @asynccontextmanager
    async def failed_source(scope, tokens):
        async with original(scope, tokens) as adapter:

            async def children(identifier, cursor=None):
                if identifier == "selected":
                    raise SourceError("access_denied")
                return ItemPage((), None)

            adapter.children = children
            yield adapter

    monkeypatch.setattr(worker.mappings.browser, "_source", failed_source)
    await worker.worker.tick()
    async with primary_authority():
        session = worker.mappings.controls._require_session()
        run = await session.get(SourceSyncRun, worker.run_id)
        job = await session.get(Job, run.job_id)
        assert job.available_at > datetime.now(UTC) and job.attempts == 1
        assert run.status == "running" and not run.enumeration_complete
    async with asyncio.timeout(1), worker.worker.admission.hold("maintenance"), primary_authority():
        assert (
            await worker.mappings.controls._require_session().get(SourceSyncRun, queued.run_id)
        ).status == "queued"
    await worker.worker.tick()
    async with primary_authority():
        assert (
            await worker.mappings.controls._require_session().get(SourceSyncRun, queued.run_id)
        ).status == "succeeded"
    assert await worker.worker.run_once("tenant", "issuer|alice", worker.run_id) == "unavailable"


@pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True)
async def test_worker_slices_do_not_starve_other_runs_while_native_receipt_is_unknown(
    claimed_source_file, monkeypatch
):
    current = claimed_source_file
    value = current.producer
    catalog = value.writer.authority.catalog
    monkeypatch.setattr(catalog, "get", type(catalog).get.__get__(catalog, type(catalog)))
    mappings = value.review.context.get_bean(SourceMappings)
    settings = value.review.context.get_bean(ContentSourceSettings)
    settings.enabled = settings.synchronization_enabled = True
    policies = value.review.context.get_bean(SourcePolicies)
    request = value.review.request.model_copy(update={"root_id": "other"})
    approved = await policies.review(
        "issuer|alice",
        "tenant",
        "browser-a",
        SourcePolicyReviewInput(**request.model_dump(), operation_id=str(uuid4())),
    )
    await policies.apply(
        "issuer|alice",
        "tenant",
        "browser-a",
        approved.mapping_id,
        SourcePolicyApplyInput(
            operation_id=str(uuid4()),
            expected_revision=1,
            review_id=approved.policy_id,
            review_digest=approved.review_digest,
        ),
    )
    queued = await mappings.execute(
        "issuer|alice",
        "tenant",
        approved.mapping_id,
        "sync",
        SourceControlInput(operation_id=str(uuid4()), expected_revision=1),
    )
    capacity = WorkAdmission(WorkAdmissionSettings())
    service = SourceSyncWorker(
        mappings,
        SourceFolders(value.writer),
        SourceFiles(value.writer, mappings),
        SourceReplacements(value.writer, mappings, None, None),
        capacity,
        settings,
        value.review.context.get_bean(SourceCredentialVault),
        SourceAccountOperations(mappings.connections),
        SourceSyncHeartbeat(SourceRunRepository(), value.review.context.get_bean(ContentSourceSettings)),
    )
    service.worker_id = value.execution.worker_id
    service._lease = value.execution
    try:
        await service.tick()
        await service.tick()
        async with primary_authority():
            session = value.guard._require_session()
            first = await session.get(SourceSyncRun, value.execution.run_id)
            second = await session.get(SourceSyncRun, queued.run_id)
            assert first.status == "reconciling" and second.status == "succeeded"
            assert (await session.get(Job, first.job_id)).attempts == 1
            assert (await session.get(Job, second.job_id)).attempts == 1
    finally:
        capacity.close_workers()


@pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True)
@pytest.mark.parametrize("producer", ["folder"], indirect=True)
async def test_nested_observations_route_to_the_published_remote_parent(producer):
    from sqlalchemy import select

    from koinon.catalog.entities import CatalogEntry
    from koinon.integrations.content_sources.sync_checkpoints import SourceCheckpoints
    from koinon.integrations.content_sources.sync_walk import WalkItem, WalkPage

    value = producer
    mappings = value.review.context.get_bean(SourceMappings)
    folders = SourceFolders(value.writer)
    parent = await folders.publish(value.admission, value.execution)
    child = RemoteItem(
        value.remote_item.scope, "nested", "Nested", "folder", "v1", None, "", (value.remote_item.item_id,)
    )
    value.changed["items"][child.item_id] = child
    async with primary_authority(read_only=False):
        await value.writer.authority.destination(
            "issuer|alice", "tenant", value.review.request.destination, write=True
        )
        await SourceCheckpoints(session=value.guard._require_session()).append(
            value.execution,
            1,
            WalkPage((WalkItem(child, ("selected", value.remote_item.item_id)),), None, True, 1),
            cursor_ciphertext=None,
        )
    capacity = WorkAdmission(WorkAdmissionSettings())
    service = SourceSyncWorker(
        mappings,
        folders,
        SourceFiles(value.writer, mappings),
        SourceReplacements(value.writer, mappings, None, None),
        capacity,
        value.review.context.get_bean(ContentSourceSettings),
        value.review.context.get_bean(SourceCredentialVault),
        SourceAccountOperations(mappings.connections),
        SourceSyncHeartbeat(SourceRunRepository(), value.review.context.get_bean(ContentSourceSettings)),
    )
    try:
        pending = await service._pending(value.execution)
        assert len(pending) == 1 and pending[0].destination[2] == parent
        assert await service.dispatch(pending[0], value.execution) == "acknowledged"
        async with primary_authority():
            nested = await value.guard._require_session().scalar(
                select(CatalogEntry).where(CatalogEntry.name == "Nested")
            )
            assert nested is not None and nested.parent_id == parent
    finally:
        capacity.close_workers()


@pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True)
@pytest.mark.parametrize("change", ["takeover", "cancel", "foreign_tenant"])
async def test_error_deferral_cannot_change_a_foreign_or_cancelled_lease(worker, change):
    second = worker.page(1, 1, more=True)
    second = replace(second, next_cursor=replace(second.next_cursor, token="later"))
    worker.pages.extend([worker.page(0, 1, more=True), second])
    await worker.worker.run_once("tenant", "issuer|alice", worker.run_id)
    execution = worker.worker._lease
    if change == "takeover":
        async with primary_authority(read_only=False):
            session = worker.mappings.controls._require_session()
            run = await session.get(SourceSyncRun, worker.run_id)
            (await session.get(Job, run.job_id)).lease_until = datetime.now(UTC) - timedelta(seconds=1)
        assert await worker.service().run_once("tenant", "issuer|alice", worker.run_id) == "reconciling"
    elif change == "cancel":
        async with primary_authority():
            revision = (
                await worker.mappings.controls._require_session().get(SourceSyncState, worker.mapping_id)
            ).revision
        await worker.mappings.execute(
            "issuer|alice",
            "tenant",
            worker.mapping_id,
            "cancel",
            SourceControlInput(expected_revision=revision, operation_id=str(uuid4())),
            target_run_id=worker.run_id,
        )
    async with primary_authority():
        session = worker.mappings.controls._require_session()
        run = await session.get(SourceSyncRun, worker.run_id)
        job = await session.get(Job, run.job_id)
        before = (job.available_at, job.updated_at, job.worker_id, job.attempts)
    assert not await worker.worker._defer(
        "foreign" if change == "foreign_tenant" else "tenant", "issuer|alice", worker.run_id, execution
    )
    async with primary_authority():
        job = await worker.mappings.controls._require_session().get(Job, execution.job_id)
        assert (job.available_at, job.updated_at, job.worker_id, job.attempts) == before


@pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True)
async def test_initial_file_dispatch_queues_once_without_claiming_publication(
    producer, source_files, monkeypatch
):
    from hashlib import sha256

    from sqlalchemy import select

    from koinon.integrations.content_sources.dtos import DownloadReceipt
    from koinon.integrations.content_sources.import_entities import SourceImportAttempt
    from koinon.integrations.content_sources.sync_entities import SourceSyncWork
    from koinon.knowledge.bulk.entities import BulkItem

    value = producer
    mappings = value.review.context.get_bean(SourceMappings)
    catalog = value.writer.authority.catalog
    monkeypatch.setattr(catalog, "get", type(catalog).get.__get__(catalog, type(catalog)))
    original = mappings.browser._source
    downloads = []

    @asynccontextmanager
    async def source(scope, tokens):
        async with original(scope, tokens) as adapter:

            async def download(item, sink, *, max_bytes, export_mime):
                downloads.append(item.item_id)
                await sink.write(b"source!")
                return DownloadReceipt(
                    scope, item.item_id, item.version, 7, sha256(b"source!").hexdigest(), "text/plain"
                )

            adapter.download = download
            yield adapter

    monkeypatch.setattr(mappings.browser, "_source", source)
    settings = value.review.context.get_bean(ContentSourceSettings)
    files = SourceFiles(value.writer, mappings, SimpleNamespace(get=lambda: source_files), settings)
    capacity = WorkAdmission(WorkAdmissionSettings())
    service = SourceSyncWorker(
        mappings,
        SourceFolders(value.writer),
        files,
        SourceReplacements(value.writer, mappings, None, None),
        capacity,
        settings,
        value.review.context.get_bean(SourceCredentialVault),
        SourceAccountOperations(mappings.connections),
        SourceSyncHeartbeat(SourceRunRepository(), value.review.context.get_bean(ContentSourceSettings)),
    )
    try:
        assert await service.dispatch(value.admission, value.execution) == "unresolved"
        assert await service.dispatch(value.admission, value.execution) == "unresolved"
        assert downloads == [value.remote_item.item_id]
        async with primary_authority():
            session = value.guard._require_session()
            work = await session.get(SourceSyncWork, value.admission.items[0].work_id)
            attempts = list((await session.scalars(select(SourceImportAttempt))).all())
            assert work.status == "processing" and len(attempts) == 1
            item = await session.get(BulkItem, attempts[0].intake_item_id)
            assert item.status == "queued" and item.receipt_json is None
            assert attempts[0].receipt_json is None and work.attempt_id == attempts[0].id
    finally:
        capacity.close_workers()


@pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True)
async def test_cancellation_commit_fences_concurrent_error_deferral(worker, source_database):
    import asyncio
    from contextvars import Context

    from sqlalchemy import text
    from test_source_concurrency_postgres import wait_for_blocked_connection

    worker.pages.append(worker.page(0, 1, more=True))
    await worker.worker.run_once("tenant", "issuer|alice", worker.run_id)
    execution = worker.worker._lease
    target, _, _ = source_database
    uri = target.set(drivername="postgresql").render_as_string(hide_password=False)

    async def deferred():
        async with primary_authority(read_only=False, fresh=True):
            session = worker.mappings.controls._require_session()
            await session.execute(text("SET LOCAL application_name='koinon_source_deferral_test'"))
            return await worker.worker._defer("tenant", "issuer|alice", worker.run_id, execution)

    task = observer = None
    try:
        async with primary_authority(read_only=False):
            _, state, _ = await worker.mappings._scope(
                "issuer|alice", "tenant", worker.mapping_id, write=True
            )
            await worker.mappings.controls.apply(
                "tenant",
                "issuer|alice",
                worker.mapping_id,
                "cancel",
                SourceControlInput(expected_revision=state.revision, operation_id=str(uuid4())),
                target_run_id=worker.run_id,
            )
            task = asyncio.create_task(deferred(), context=Context())
            observer = asyncio.create_task(
                wait_for_blocked_connection(uri, "koinon_source_deferral_test"), context=Context()
            )
            await asyncio.wait((task, observer), return_when=asyncio.FIRST_COMPLETED)
            if task.done():
                task.result()
            assert not task.done(), "Deferral must wait for the run cancellation transaction"
            await observer
        assert await task is False
    finally:
        if observer is not None:
            observer.cancel()
            await asyncio.gather(observer, return_exceptions=True)
        if task is not None:
            async with asyncio.timeout(5):
                await asyncio.gather(task, return_exceptions=True)
