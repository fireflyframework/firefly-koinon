# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Real PostgreSQL runtime admission, resume, and cleanup capabilities."""

import asyncio
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import psycopg
import pytest
from pyfly.data.transaction import current_unit_of_work
from pyfly.kernel import ConflictException, RateLimitException
from sqlalchemy import func, select, text
from test_connection_lifecycle import lifecycle as lifecycle
from test_mapping_review import review as review
from test_source_concurrency_postgres import source_sessions as source_sessions
from test_source_migration_postgres import load
from test_source_migration_postgres import source_database as source_database

from koinon.integrations.content_sources.errors import SourceError
from koinon.integrations.content_sources.mapping_validation_entities import (
    SourceMappingValidation as Validation,
)
from koinon.integrations.content_sources.mapping_validation_entities import (
    SourceMappingValidationEntry as Entry,
)
from koinon.integrations.content_sources.mapping_validation_repository import (
    SourceMappingValidationRepository,
)
from koinon.jobs.errors import JobConflict

pytestmark = pytest.mark.integration


@pytest.fixture
async def validations(source_sessions, source_database):
    sessions, uri = source_sessions
    _, role, _ = source_database
    with psycopg.connect(uri) as owner:
        for table in (Validation.__tablename__, Entry.__tablename__):
            load("deploy/provision_roles.py").grant_table(owner, table, role)
    return sessions


def header(**changes):
    now = datetime.now(UTC)
    return Validation(
        id=uuid4(),
        tenant_id="retained",
        owner="issuer|alice",
        operation_id=uuid4(),
        session_hash="a" * 64,
        request_sha256="b" * 64,
        request_ciphertext=b"encrypted-selection",
        connection_id="connection",
        connection_revision=1,
        authority_sha256="c" * 64,
        root_captured=False,
        root_kind=None,
        root_proof_sha256=None,
        root_proof_ciphertext=None,
        scan_max_items=100,
        reserved_bytes=100 * 16384 + 8388608,
        max_active_per_tenant=8,
        max_active_per_owner=2,
        max_records_per_tenant=1000,
        max_retained_bytes_per_tenant=17179869184,
        created_at=now,
        updated_at=now,
        expires_at=now + timedelta(hours=8),
        **changes,
    )


def entry(row, item="first", fingerprint="e" * 64, destination="f" * 64):
    return Entry(
        tenant_id=row.tenant_id,
        validation_id=row.id,
        item_id=item,
        fingerprint_sha256=fingerprint,
        candidate_ciphertext=b"encrypted-candidate",
        destination_key_sha256=destination,
        verified=False,
    )


async def add(sessions, row):
    async with sessions.begin() as session:
        return await SourceMappingValidationRepository(session=session).admit(row)


async def capture(sessions, row):
    async with sessions.begin() as session:
        stored = await SourceMappingValidationRepository(session=session).owned(
            row.tenant_id, row.owner, row.id, lock=True
        )
        stored.root_captured, stored.root_kind = True, "folder"
        stored.root_proof_sha256, stored.root_proof_ciphertext = "d" * 64, b"encrypted-proof"
        stored.checkpoint_ciphertext = b"encrypted-start-cursor"
        stored.revision += 1


async def test_admission_replay_does_not_renew_and_rejects_rebound_session(validations):
    original = header()
    stored = await add(validations, original)
    replay = header()
    replay.operation_id = original.operation_id
    result = await add(validations, replay)
    assert result.id == stored.id and result.expires_at == stored.expires_at
    replay.session_hash = "different"
    with pytest.raises(JobConflict) as conflict:
        await add(validations, replay)
    assert conflict.value.code == "IDEMPOTENCY_CONFLICT"
    async with validations() as session:
        assert await session.scalar(select(func.count()).select_from(Validation)) == 1


async def test_concurrent_owner_capacity_has_one_final_winner(validations):
    await add(validations, header())
    results = await asyncio.gather(
        add(validations, header()), add(validations, header()), return_exceptions=True
    )
    assert sum(isinstance(result, RateLimitException) for result in results) == 1
    async with validations() as session:
        rows = list((await session.scalars(select(Validation))).all())
        assert len(rows) == 2
        assert all(row.payload_released_at is None for row in rows)


async def test_owned_lookup_never_returns_foreign_preparation(validations):
    row = await add(validations, header())
    async with validations() as session:
        records = SourceMappingValidationRepository(session=session)
        assert await records.owned("retained", "issuer|other", row.id) is None
        assert await records.owned("other", "issuer|alice", row.id) is None
        assert await records.operation("retained", "issuer|other", row.operation_id) is None


async def test_duplicate_candidate_preserves_identity_and_changed_fingerprint_fails(validations):
    row = await add(validations, header())
    await capture(validations, row)
    async with validations.begin() as session:
        records = SourceMappingValidationRepository(session=session)
        stored = await records.owned(row.tenant_id, row.owner, row.id, lock=True)
        added = await records.append(stored, [entry(row), entry(row)])
        assert added == 1
        stored.eligible_count, stored.raw_observed_count = added, 2
        stored.revision += 1
    async with validations.begin() as session:
        records = SourceMappingValidationRepository(session=session)
        stored = await records.owned(row.tenant_id, row.owner, row.id, lock=True)
        with pytest.raises(JobConflict) as conflict:
            await records.append(stored, [entry(row, fingerprint="changed")])
        assert conflict.value.code == "SOURCE_CHANGED"
    async with validations() as session:
        assert await session.scalar(select(func.count()).select_from(Entry)) == 1
        stored = await session.get(Validation, row.id)
        assert stored.raw_observed_count == 2 and stored.eligible_count == 1


async def test_destination_collision_is_detected_across_pages(validations):
    row = await add(validations, header())
    await capture(validations, row)
    for identity in ("one", "two"):
        async with validations.begin() as session:
            records = SourceMappingValidationRepository(session=session)
            stored = await records.owned(row.tenant_id, row.owner, row.id, lock=True)
            count = await records.append(stored, [entry(row, identity)])
            stored.eligible_count += count
            stored.raw_observed_count += 1
            stored.revision += 1
    async with validations() as session:
        assert await SourceMappingValidationRepository(session=session).source_collision(row)


async def prepare_cleanup(validations):
    row = await add(validations, header())
    await capture(validations, row)
    async with validations.begin() as session:
        records = SourceMappingValidationRepository(session=session)
        stored = await records.owned(row.tenant_id, row.owner, row.id, lock=True)
        count = await records.append(stored, [entry(row, "one"), entry(row, "two")])
        stored.eligible_count, stored.raw_observed_count = count, count
        stored.revision += 1
    async with validations.begin() as session:
        records = SourceMappingValidationRepository(session=session)
        stored = await records.owned(row.tenant_id, row.owner, row.id, lock=True)
        records.start_cleanup(stored, datetime.now(UTC))
    async with validations.begin() as session:
        claim = await SourceMappingValidationRepository(session=session).claim_cleanup(
            row.tenant_id, row.id, datetime.now(UTC)
        )
    return row, claim


async def test_cleanup_requires_callers_exact_claim_not_merely_a_live_stored_claim(validations):
    row, claim = await prepare_cleanup(validations)
    async with validations.begin() as session:
        with pytest.raises(SourceError, match="access_denied"):
            await SourceMappingValidationRepository(session=session).cleanup_batch(
                replace(claim, token=uuid4()), datetime.now(UTC)
            )
    async with validations() as session:
        assert await session.scalar(select(func.count()).select_from(Entry)) == 2
        assert (await session.get(Validation, row.id)).payload_released_at is None


async def test_cleanup_rollback_and_partial_batch_keep_reservation_then_release_to_tombstone(validations):
    row, claim = await prepare_cleanup(validations)
    with pytest.raises(RuntimeError, match="crash"):
        async with validations.begin() as session:
            remaining = await SourceMappingValidationRepository(session=session).cleanup_batch(
                claim, datetime.now(UTC), limit=1
            )
            assert remaining
            raise RuntimeError("crash")
    async with validations() as session:
        assert await session.scalar(select(func.count()).select_from(Entry)) == 2
        assert (await session.get(Validation, row.id)).reserved_bytes == row.reserved_bytes
    async with validations.begin() as session:
        assert await SourceMappingValidationRepository(session=session).cleanup_batch(
            claim, datetime.now(UTC), limit=1
        )
    async with validations() as session:
        stored = await session.get(Validation, row.id)
        assert stored.payload_released_at is None and stored.reserved_bytes == row.reserved_bytes
    async with validations.begin() as session:
        newer = await SourceMappingValidationRepository(session=session).claim_cleanup(
            row.tenant_id, row.id, datetime.now(UTC)
        )
    async with validations.begin() as session:
        assert not await SourceMappingValidationRepository(session=session).cleanup_batch(
            newer, datetime.now(UTC)
        )
    async with validations() as session:
        stored = await session.get(Validation, row.id)
        assert stored.state == "abandoned" and stored.payload_released_at is not None
        assert stored.expires_at == row.expires_at and stored.reserved_bytes < 8192
        assert await session.scalar(select(func.count()).select_from(Entry)) == 0


@pytest.fixture
async def validation_service(review, monkeypatch):
    from koinon.integrations.content_sources.account_operations import SourceAccountOperations
    from koinon.integrations.content_sources.dtos import Change, ChangePage, Cursor, ItemPage, RemoteItem
    from koinon.integrations.content_sources.mapping_preview import SourceMappingPreview
    from koinon.integrations.content_sources.mapping_validation import SourceMappingValidations
    from koinon.integrations.content_sources.mapping_validation_dtos import SourceMappingValidationInput
    from koinon.integrations.content_sources.sessions import SourceBrowserSessions
    from koinon.integrations.content_sources.settings import ContentSourceSettings
    from koinon.workers.admission import WorkAdmission, WorkAdmissionSettings

    original = review.service.browser._source
    state = {
        "count": 101,
        "collision": False,
        "denied": set(),
        "children": 0,
        "changes": 0,
        "move_at_changes": False,
        "moved": False,
        "opens": 0,
        "root_capture_failure": False,
        "file_root": False,
        "duplicate_page": False,
        "events": [],
        "nested": False,
        "renamed_parent": False,
        "verification_failure": False,
        "provider_started": asyncio.Event(),
        "provider_pending": set(),
    }

    @asynccontextmanager
    async def source(scope, tokens):
        state["opens"] += 1
        async with original(scope, tokens) as adapter:
            get = adapter.get_item

            def item(index):
                return RemoteItem(
                    scope,
                    f"file-{index:04d}",
                    "file-0000.txt" if state["collision"] and index == 100 else f"file-{index:04d}.txt",
                    "file",
                    "v1",
                    7,
                    "text/plain",
                    ("other",)
                    if index == 0 and state["moved"]
                    else ("nested",)
                    if state["nested"]
                    else ("selected",),
                    True,
                )

            async def get_item(identifier):
                state["events"].append(identifier)
                unit = current_unit_of_work("primary")
                assert unit is None or unit.completed, "provider I/O occurred inside primary transaction"
                if identifier in state["denied"]:
                    raise SourceError("access_denied")
                if identifier == "selected" and state["file_root"]:
                    return RemoteItem(
                        scope, "selected", "chosen.txt", "file", "v1", 7, "text/plain", ("root",), True
                    )
                if identifier == "nested":
                    return RemoteItem(
                        scope,
                        "nested",
                        "New name" if state["renamed_parent"] else "Private folder",
                        "folder",
                        "v2" if state["renamed_parent"] else "v1",
                        None,
                        "",
                        ("selected",),
                    )
                if identifier.startswith("file-"):
                    return item(int(identifier[5:]))
                return await get(identifier)

            async def children(folder, cursor=None):
                unit = current_unit_of_work("primary")
                assert unit is None or unit.completed
                state["children"] += 1
                if folder == "selected" and state["nested"]:
                    return ItemPage((await get_item("nested"),), None)
                assert folder == ("nested" if state["nested"] else "selected")
                offset = int(cursor.token) if cursor else 0
                end = min(offset + 100, state["count"])
                return ItemPage(
                    tuple(
                        item(0 if state["duplicate_page"] and index < 100 else index)
                        for index in range(offset, end)
                    ),
                    Cursor(scope, "children:selected", str(end)) if end < state["count"] else None,
                )

            async def start_cursor():
                state["events"].append("bookmark")
                if state["root_capture_failure"]:
                    raise SourceError("unavailable")
                return Cursor(scope, "changes", "initial")

            async def changes(cursor):
                unit = current_unit_of_work("primary")
                assert unit is None or unit.completed
                state["changes"] += 1
                if state["move_at_changes"]:
                    state["moved"] = True
                    return ChangePage(
                        (Change("upsert", "file-0000", item(0)),), None, Cursor(scope, "changes", "terminal")
                    )
                return ChangePage((), None, Cursor(scope, "changes", "terminal"))

            async def check_access(identifier):
                if state["verification_failure"] and identifier == "file-0000":
                    await state["provider_started"].wait()
                    if state["verification_failure"] == "error":
                        raise SourceError("access_denied")
                    await asyncio.Event().wait()
                if state["verification_failure"] and identifier == "file-0001":
                    task = asyncio.current_task()
                    state["provider_pending"].add(task)
                    state["provider_started"].set()
                    try:
                        await asyncio.Event().wait()
                    finally:
                        state["provider_pending"].discard(task)
                return await get_item(identifier)

            adapter.get_item, adapter.check_access = get_item, check_access
            adapter.children, adapter.start_cursor, adapter.changes = children, start_cursor, changes
            yield adapter

    monkeypatch.setattr(review.service.browser, "_source", source)
    settings = review.context.get_bean(ContentSourceSettings)
    records = review.context.get_bean(SourceMappingValidationRepository)
    service = SourceMappingValidations(
        records,
        review.service,
        SourceMappingPreview(review.service.authority, review.service.connections, review.service.browser),
        review.context.get_bean(SourceBrowserSessions),
        settings,
        WorkAdmission(WorkAdmissionSettings()),
        review.context.get_bean(SourceAccountOperations),
    )
    body = SourceMappingValidationInput(**review.request.model_dump(), operation_id=uuid4())
    return service, body, state


async def finish_preparation(service, output):
    from koinon.integrations.content_sources.mapping_validation_dtos import (
        SourceMappingValidationContinueInput,
    )

    for _ in range(12):
        if output.continuation_token is None:
            return output
        output = await service.continue_validation(
            "issuer|alice",
            "tenant",
            "browser-a",
            output.validation_id,
            SourceMappingValidationContinueInput(
                expected_revision=output.revision, continuation_token=output.continuation_token
            ),
        )
    raise AssertionError("A 101-item validation did not reach a bounded terminal outcome")


@pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True)
@pytest.mark.parametrize("boundary", ["capture", "scan", "items", "seal"])
async def test_busy_account_preserves_validation_without_provider_io(validation_service, boundary):
    from koinon.integrations.content_sources.account_operation_dtos import AccountOperationRequest
    from koinon.integrations.content_sources.account_operations import (
        AccountOperationPermit,
        SourceAccountBusy,
        SourceAccountOperations,
    )
    from koinon.integrations.content_sources.mapping_validation_dtos import (
        SourceMappingValidationContinueInput,
    )
    from koinon.security.authority import primary_authority

    service, body, state = validation_service
    state["count"] = 2
    output = await service.begin_validation("issuer|alice", "tenant", "browser-a", body)
    if boundary == "scan":
        output = await service.continue_validation(
            "issuer|alice",
            "tenant",
            "browser-a",
            output.validation_id,
            SourceMappingValidationContinueInput(
                expected_revision=output.revision, continuation_token=output.continuation_token
            ),
        )
    elif boundary in {"items", "seal"}:
        output = await finish_preparation(service, output)
        assert output.state == "complete"
    async with primary_authority(fresh=True):
        row = await service.records._require_session().get(Validation, output.validation_id)
        connection_revision = row.connection_revision
        before = (
            row.revision,
            row.state,
            row.root_captured,
            row.raw_observed_count,
            row.eligible_count,
            row.last_continuation_sha256,
            row.checkpoint_ciphertext,
        )
    accounts = SourceAccountOperations(service.reviews.connections)
    holder = await accounts.acquire(
        "tenant",
        AccountOperationRequest(
            kind="validation",
            operation_id="another-validation",
            revision=1,
            connection_id=body.connection_id,
            connection_revision=connection_revision,
            owner="issuer|alice",
            process_instance_id="another-api-process",
        ),
    )
    assert isinstance(holder, AccountOperationPermit)
    provider_before = (state["opens"], state["children"], state["changes"], list(state["events"]))
    try:
        with pytest.raises(SourceAccountBusy) as failure:
            if boundary in {"capture", "scan"}:
                await service.continue_validation(
                    "issuer|alice",
                    "tenant",
                    "browser-a",
                    output.validation_id,
                    SourceMappingValidationContinueInput(
                        expected_revision=output.revision, continuation_token=output.continuation_token
                    ),
                )
            elif boundary == "items":
                await service.validation_items("issuer|alice", "tenant", "browser-a", output.validation_id)
            else:
                await service.seal_for_review(
                    "issuer|alice", "tenant", "browser-a", output.validation_id, body.selection()
                )
        assert 1 <= failure.value.retry_after_seconds <= 30
        assert (state["opens"], state["children"], state["changes"], state["events"]) == provider_before
        async with primary_authority(fresh=True):
            row = await service.records._require_session().get(Validation, output.validation_id)
            assert (
                row.revision,
                row.state,
                row.root_captured,
                row.raw_observed_count,
                row.eligible_count,
                row.last_continuation_sha256,
                row.checkpoint_ciphertext,
            ) == before
    finally:
        await accounts.abort(holder)


@pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True)
@pytest.mark.parametrize("code", ["access_denied", "resync_required"])
@pytest.mark.parametrize("expire_on_checkpoint", [False, True])
async def test_terminal_provider_error_keeps_account_settlement_atomic(
    validation_service, monkeypatch, code, expire_on_checkpoint
):
    from koinon.integrations.content_sources.account_operation_entities import SourceAccountOperation
    from koinon.integrations.content_sources.mapping_validation_dtos import (
        SourceMappingValidationContinueInput,
    )
    from koinon.security.authority import primary_authority

    service, body, _state = validation_service
    output = await service.begin_validation("issuer|alice", "tenant", "browser-a", body)
    original = service.reviews.browser._source

    @asynccontextmanager
    async def source(scope, tokens):
        async with original(scope, tokens) as adapter:

            async def fail_bookmark():
                raise SourceError(code)

            adapter.start_cursor = fail_bookmark
            yield adapter

    monkeypatch.setattr(service.reviews.browser, "_source", source)
    if expire_on_checkpoint:
        async with primary_authority(read_only=False):
            session = service.records._require_session()
            # A real database transition expires the holder after assert_current,
            # before finish. Both it and the validation write must roll back.
            await session.execute(
                text("""
                CREATE FUNCTION expire_validation_account() RETURNS trigger
                LANGUAGE plpgsql AS $$ BEGIN
                    UPDATE koinon_source_account_operations
                    SET started_at = statement_timestamp() - interval '151 seconds',
                        expires_at = statement_timestamp() - interval '1 second'
                    WHERE tenant_id = NEW.tenant_id AND operation_kind = 'validation'
                      AND operation_id = NEW.id::text AND token IS NOT NULL;
                    RETURN NEW;
                END $$
            """)
            )
            await session.execute(
                text("""
                CREATE TRIGGER expire_validation_account_after_checkpoint
                AFTER UPDATE ON koinon_content_mapping_validations
                FOR EACH ROW WHEN (NEW.revision <> OLD.revision)
                EXECUTE FUNCTION expire_validation_account()
            """)
            )
    command = SourceMappingValidationContinueInput(
        expected_revision=output.revision, continuation_token=output.continuation_token
    )
    if expire_on_checkpoint:
        with pytest.raises((ConflictException, JobConflict)) as failure:
            await service.continue_validation(
                "issuer|alice", "tenant", "browser-a", output.validation_id, command
            )
        assert failure.value.code == "SOURCE_ACCOUNT_LEASE_LOST"
    else:
        result = await service.continue_validation(
            "issuer|alice", "tenant", "browser-a", output.validation_id, command
        )
        assert result.state == "stale" and result.revision == output.revision + 1
    async with primary_authority(fresh=True):
        session = service.records._require_session()
        row = await session.get(Validation, output.validation_id)
        assert not row.root_captured and row.checkpoint_ciphertext is None and row.eligible_count == 0
        if expire_on_checkpoint:
            assert row.revision == output.revision and row.state == "scanning"
            assert row.last_continuation_sha256 is None and row.reason_code is None
        else:
            assert row.state == "stale" and row.last_continuation_result_revision == row.revision
        header = await session.scalar(select(SourceAccountOperation))
        assert header is not None and header.token is None
        assert (header.quarantine_until is not None) == (code == "resync_required")


@pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True)
async def test_complete_101_item_selection_seals_without_count_leak_or_extra_enumeration(validation_service):
    from koinon.security.authority import primary_authority

    service, body, state = validation_service
    begin = await service.begin_validation("issuer|alice", "tenant", "browser-a", body)
    result = await finish_preparation(service, begin)
    assert result.state == "complete" and result.manifest_sha256 is not None
    assert result.total is result.observed_count is None
    assert state["children"] == 2
    sealed = await service.seal_for_review(
        "issuer|alice", "tenant", "browser-a", result.validation_id, body.selection()
    )
    assert sealed.manifest_sha256 == result.manifest_sha256 and state["children"] == 2
    async with primary_authority(read_only=False):
        row = await service.locked_assert_eligible("issuer|alice", "tenant", "browser-a", sealed)
        assert row.eligible_count == 101 and row.verification_position == 101
    page = await service.validation_items("issuer|alice", "tenant", "browser-a", result.validation_id)
    assert page.visible_count == 25 and page.total is None and page.next_cursor is not None
    assert len({item.item_id for item in page.items}) == 25


@pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True)
async def test_collision_on_item_101_prevents_complete_manifest(validation_service):
    service, body, state = validation_service
    state["collision"] = True
    result = await finish_preparation(
        service, await service.begin_validation("issuer|alice", "tenant", "browser-a", body)
    )
    assert result.state == "blocked" and result.reason_code == "SOURCE_NAME_COLLISION"
    assert result.manifest_sha256 is None and result.continuation_token is None
    page = await service.validation_items("issuer|alice", "tenant", "browser-a", result.validation_id)
    assert page.items[0].collision == "source_name"
    assert page.total is None and page.visible_count == 25


@pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True)
@pytest.mark.parametrize("observation_kind", ["ordinary", "excluded", "duplicates"])
async def test_scan_maximum_plus_one_stays_incomplete_across_continuations(
    validation_service, observation_kind
):
    service, body, state = validation_service
    service.settings.sync_max_scan_items = 100
    state["duplicate_page"] = observation_kind == "duplicates"
    if observation_kind == "excluded":
        body = body.model_copy(update={"excluded_ids": [f"file-{index:04d}" for index in range(100)]})
    result = await finish_preparation(
        service, await service.begin_validation("issuer|alice", "tenant", "browser-a", body)
    )
    assert result.state == "blocked" and result.reason_code == "SOURCE_SCAN_LIMIT_EXCEEDED"
    assert not result.enumeration_complete and result.manifest_sha256 is None


@pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True)
async def test_revoked_candidate_is_omitted_and_invalidates_sealed_preparation(validation_service):
    service, body, state = validation_service
    result = await finish_preparation(
        service, await service.begin_validation("issuer|alice", "tenant", "browser-a", body)
    )
    state["denied"].add("file-0000")
    page = await service.validation_items("issuer|alice", "tenant", "browser-a", result.validation_id)
    assert page.visible_count == 24 and all(item.item_id != "file-0000" for item in page.items)
    assert "file-0000" not in page.model_dump_json() and page.total is None
    status = await service.validation_status("issuer|alice", "tenant", "browser-a", result.validation_id)
    assert status.state == "stale" and status.manifest_sha256 is None


@pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True)
async def test_selected_item_moved_outside_root_is_stale_not_an_unrelated_change(validation_service):
    service, body, state = validation_service
    state["move_at_changes"] = True
    result = await finish_preparation(
        service, await service.begin_validation("issuer|alice", "tenant", "browser-a", body)
    )
    assert result.state == "stale" and result.reason_code == "SOURCE_CHANGED"
    assert result.manifest_sha256 is None


@pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True)
async def test_real_begin_reserves_final_slot_before_any_provider_call_and_replays_at_capacity(
    validation_service,
):
    from koinon.integrations.content_sources.mapping_validation import SourceMappingValidations
    from koinon.workers.admission import WorkAdmission, WorkAdmissionSettings

    service, body, state = validation_service
    first = await service.begin_validation("issuer|alice", "tenant", "browser-a", body)
    second, third = (
        body.model_copy(update={"operation_id": uuid4()}),
        body.model_copy(update={"operation_id": uuid4()}),
    )
    other_process = SourceMappingValidations(
        service.records,
        service.reviews,
        service.preview,
        service.sessions,
        service.settings,
        WorkAdmission(WorkAdmissionSettings()),
        service.accounts,
    )
    results = await asyncio.gather(
        service.begin_validation("issuer|alice", "tenant", "browser-a", second),
        other_process.begin_validation("issuer|alice", "tenant", "browser-a", third),
        return_exceptions=True,
    )
    assert sum(isinstance(result, RateLimitException) for result in results) == 1
    assert state["opens"] == state["children"] == state["changes"] == 0
    replay = await service.begin_validation("issuer|alice", "tenant", "browser-a", body)
    assert replay.validation_id == first.validation_id and replay.expires_at == first.expires_at


@pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True)
async def test_capture_response_loss_replays_same_revision_without_enumeration(validation_service):
    from koinon.integrations.content_sources.account_operation_dtos import AccountOperationRequest
    from koinon.integrations.content_sources.account_operations import AccountOperationPermit
    from koinon.integrations.content_sources.mapping_validation_dtos import (
        SourceMappingValidationContinueInput,
    )
    from koinon.security.authority import primary_authority

    service, body, state = validation_service
    result = await service.begin_validation("issuer|alice", "tenant", "browser-a", body)
    command = SourceMappingValidationContinueInput(
        expected_revision=result.revision, continuation_token=result.continuation_token
    )
    captured = await service.continue_validation(
        "issuer|alice", "tenant", "browser-a", result.validation_id, command
    )
    async with primary_authority(fresh=True):
        row = await service.records._require_session().get(Validation, result.validation_id)
        revision = row.connection_revision
    holder = await service.accounts.acquire(
        "tenant",
        AccountOperationRequest(
            kind="validation",
            operation_id="other-preparation",
            revision=1,
            connection_id=body.connection_id,
            connection_revision=revision,
            owner="issuer|alice",
            process_instance_id="other-api-process",
        ),
    )
    assert isinstance(holder, AccountOperationPermit)
    before = state["opens"]
    try:
        replay = await service.continue_validation(
            "issuer|alice", "tenant", "browser-a", result.validation_id, command
        )
    finally:
        await service.accounts.abort(holder)
    assert captured.revision == replay.revision == 2
    assert state["opens"] == before and state["children"] == 0
    assert state["events"][0] == "bookmark"
    async with primary_authority():
        row = await service.records._require_session().get(Validation, result.validation_id)
        assert row.root_captured and row.eligible_count == row.raw_observed_count == 0
        assert row.checkpoint_ciphertext is not None


@pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True)
async def test_identity_recovery_is_read_only_and_expiry_cannot_resume_preparation(
    validation_service, monkeypatch
):
    from koinon.integrations.content_sources.mapping_validation_dtos import (
        SourceMappingValidationContinueInput,
    )

    service, body, state = validation_service
    created = await service.begin_validation("issuer|alice", "tenant", "browser-a", body)
    recovered = await service.creation_receipt("issuer|alice", "tenant", "browser-a", body.operation_id)
    status = await service.validation_status("issuer|alice", "tenant", "browser-a", created.validation_id)
    expected = created.model_dump(exclude={"continuation_token"})
    assert recovered.model_dump(exclude={"continuation_token"}) == expected
    assert status.model_dump(exclude={"continuation_token"}) == expected
    assert state["opens"] == 0
    monkeypatch.setattr(service, "_now", lambda: created.expires_at)
    expired = await service.validation_status("issuer|alice", "tenant", "browser-a", created.validation_id)
    assert expired.state == "expired" and expired.revision == created.revision
    assert expired.expires_at == created.expires_at and expired.continuation_token is None
    with pytest.raises(JobConflict) as error:
        await service.continue_validation(
            "issuer|alice",
            "tenant",
            "browser-a",
            created.validation_id,
            SourceMappingValidationContinueInput(
                expected_revision=created.revision, continuation_token=created.continuation_token
            ),
        )
    assert error.value.code == "SOURCE_VALIDATION_EXPIRED"
    assert state["opens"] == 0


@pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True)
async def test_transient_capture_failure_keeps_original_uncaptured_reservation(validation_service):
    from koinon.integrations.content_sources.mapping_validation_dtos import (
        SourceMappingValidationContinueInput,
    )
    from koinon.security.authority import primary_authority

    service, body, state = validation_service
    result = await service.begin_validation("issuer|alice", "tenant", "browser-a", body)
    state["root_capture_failure"] = True
    with pytest.raises(SourceError, match="unavailable"):
        await service.continue_validation(
            "issuer|alice",
            "tenant",
            "browser-a",
            result.validation_id,
            SourceMappingValidationContinueInput(
                expected_revision=result.revision, continuation_token=result.continuation_token
            ),
        )
    async with primary_authority():
        row = await service.records._require_session().get(Validation, result.validation_id)
        assert not row.root_captured and row.revision == 1 and row.expires_at == result.expires_at
        assert row.reserved_bytes == row.scan_max_items * 16384 + 8388608


@pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True)
async def test_single_file_captures_and_seals_without_children_or_rewriting_creation_policy(
    validation_service,
):
    from koinon.integrations.content_sources.mapping_validation import digest, effective_selection
    from koinon.security.authority import primary_authority

    service, body, state = validation_service
    state["file_root"] = True
    result = await finish_preparation(
        service, await service.begin_validation("issuer|alice", "tenant", "browser-a", body)
    )
    assert result.state == "complete" and state["children"] == 0
    selected = effective_selection(body.selection(), "file")
    sealed = await service.seal_for_review(
        "issuer|alice", "tenant", "browser-a", result.validation_id, selected
    )
    assert '"recursive":false' in sealed.selection_json and '"hierarchy":"preserve"' in sealed.selection_json
    async with primary_authority():
        row = await service.records._require_session().get(Validation, result.validation_id)
        assert row.request_sha256 == digest(body.selection().model_dump(mode="json"))
        assert row.eligible_count == 1
        entry = await service.records.entry(row, "selected")
        presentation = await service._presentation(row, entry, selected, {})
        assert presentation["ancestry"] == []
        assert presentation["destination_relative_path"] == ["chosen.txt"]


@pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True)
async def test_file_exclusions_block_uncaptured_preparation_without_child_read(validation_service):
    service, body, state = validation_service
    state["file_root"] = True
    body = body.model_copy(update={"excluded_ids": ["other"]})
    result = await finish_preparation(
        service, await service.begin_validation("issuer|alice", "tenant", "browser-a", body)
    )
    assert result.state == "blocked" and result.reason_code == "SOURCE_INVALID_SELECTION"
    assert state["children"] == 0 and result.manifest_sha256 is None


@pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True)
async def test_changed_ancestor_cannot_hydrate_old_protected_names(validation_service):
    service, body, state = validation_service
    state["nested"], state["count"] = True, 1
    result = await finish_preparation(
        service, await service.begin_validation("issuer|alice", "tenant", "browser-a", body)
    )
    assert result.state == "complete"
    state["renamed_parent"] = True
    page = await service.validation_items("issuer|alice", "tenant", "browser-a", result.validation_id)
    assert page.visible_count == 0 and page.items == []
    assert "Private folder" not in page.model_dump_json() and page.total is None


@pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True)
@pytest.mark.parametrize("failure", ["error", "cancel"])
async def test_failed_verification_cancels_provider_siblings_before_returning(validation_service, failure):
    from koinon.integrations.content_sources.mapping_validation_dtos import (
        SourceMappingValidationContinueInput,
    )

    service, body, state = validation_service
    state["count"] = 2
    result = await service.begin_validation("issuer|alice", "tenant", "browser-a", body)
    for _ in range(2):
        result = await service.continue_validation(
            "issuer|alice",
            "tenant",
            "browser-a",
            result.validation_id,
            SourceMappingValidationContinueInput(
                expected_revision=result.revision, continuation_token=result.continuation_token
            ),
        )
    assert result.state == "verifying"
    state["verification_failure"] = failure
    try:
        task = asyncio.create_task(
            service.continue_validation(
                "issuer|alice",
                "tenant",
                "browser-a",
                result.validation_id,
                SourceMappingValidationContinueInput(
                    expected_revision=result.revision, continuation_token=result.continuation_token
                ),
            )
        )
        if failure == "cancel":
            await state["provider_started"].wait()
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            current = await service.validation_status(
                "issuer|alice", "tenant", "browser-a", result.validation_id
            )
            assert current.state == "verifying" and current.revision == result.revision
        else:
            stale = await task
            assert stale.state == "stale" and stale.reason_code == "SOURCE_AUTHORITY_CHANGED"
        assert not state["provider_pending"], "failed request left a provider task running"
    finally:
        pending = tuple(state["provider_pending"])
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
