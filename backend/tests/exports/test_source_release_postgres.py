# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Export preflight and release never retain a primary transaction across provider I/O."""

import importlib.util
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from pyfly.core import Config
from pyfly.data.relational.datasource_registry import DataSourceRegistry
from pyfly.data.transaction import current_unit_of_work
from sqlalchemy.engine import make_url

import koinon.knowledge.bulk.entities  # noqa: F401
from koinon.exports.dtos import ConversationExportInput, ExportCreate
from koinon.exports.service import KnowledgeExports

spec = importlib.util.spec_from_file_location(
    "source_export_fixture", Path(__file__).parents[1] / "evidence/test_evidence_reviews.py"
)
assert spec and spec.loader
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)
reviews = fixtures.reviews
pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def postgres_reviews(monkeypatch):
    uri = os.environ.get("KOINON_MEMORY_AUTHORITY_TEST_PG_URL")
    if not uri:
        pytest.skip("Requires an explicitly owned PostgreSQL fixture")
    url = make_url(uri)
    assert url.host == "127.0.0.1" and url.port not in (None, 18783)
    database = "source_export_" + uuid4().hex[:12]
    with psycopg.connect(uri, autocommit=True) as owner:
        owner.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    original = fixtures.ApplicationContext

    def configured(config):
        values = config.to_dict()
        values["pyfly"]["data"]["relational"]["url"] = url.set(
            drivername="postgresql+asyncpg", database=database
        ).render_as_string(hide_password=False)
        context = original(Config(values))
        from koinon.integrations.content_sources.read_repository import SourceReadRepository
        from koinon.integrations.content_sources.reader_selection_repository import (
            SourceReaderSelectionRepository,
        )

        context.register_bean(SourceReadRepository)
        context.register_bean(SourceReaderSelectionRepository)
        return context

    monkeypatch.setattr(fixtures, "ApplicationContext", configured)
    try:
        yield
    finally:
        with psycopg.connect(uri, autocommit=True) as owner:
            owner.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(database)))


async def created_export(context):
    service = context.get_bean(KnowledgeExports)
    preview = await service.preview(
        "owner",
        "north",
        ConversationExportInput(kind="conversation", thread_id="t", message_ids=["m"], format="json"),
    )
    created = await service.create(
        "owner", "north", ExportCreate(review_id=preview.id, expected_revision=preview.revision)
    )
    return service, created


async def test_output_authority_runs_outside_primary_transaction(reviews, monkeypatch):
    _, snapshot, context = reviews
    service, created = await created_export(context)
    original = snapshot.authorize_output

    async def remote_output(*args, **kwargs):
        unit = current_unit_of_work("primary")
        assert unit is None or unit.completed, "provider I/O inside export transaction"
        await original(*args, **kwargs)

    monkeypatch.setattr(snapshot, "authorize_output", remote_output)
    assert b"Reviewed answer" in (await service.download("owner", "north", created.id)).content


async def imported_graph(context):
    from koinon.catalog.entities import CatalogEntry
    from koinon.integrations.content_sources.entities import PersonalSourceConnection
    from koinon.integrations.content_sources.import_entities import SourceImportAttempt
    from koinon.integrations.content_sources.mapping_entities import SourceMapping, SourceObject
    from koinon.integrations.content_sources.sync_entities import SourceImportedAsset
    from koinon.knowledge.bulk.entities import BulkBatch, BulkItem

    now = datetime.now(UTC)
    sessions = context.get_bean(DataSourceRegistry).primary.sessionmaker
    async with sessions.begin() as session:
        parent = None
        for identifier, kind in (
            ("workspace", "workspace"),
            ("project", "project"),
            ("folder", "folder"),
            ("source", "source"),
            ("asset", "document"),
        ):
            session.add(
                CatalogEntry(
                    id=identifier,
                    tenant_id="north",
                    kind=kind,
                    name=identifier,
                    workspace_id="workspace",
                    project_id="project",
                    parent_id=parent,
                    created_by="owner",
                )
            )
            await session.flush()
            parent = identifier
        session.add(
            PersonalSourceConnection(
                id="connection",
                tenant_id="north",
                owner="owner",
                provider="google_drive",
                status="connected",
                external_subject="remote-owner",
            )
        )
        await session.flush()
        session.add(
            SourceMapping(
                id="mapping",
                tenant_id="north",
                owner="owner",
                connection_id="connection",
                provider="google_drive",
                external_subject="remote-owner",
                issuer="https://accounts.google.com",
                drive_id="drive",
                root_id="root",
                workspace_id="workspace",
                project_id="project",
                parent_id="folder",
                request_json={},
                request_sha256="a" * 64,
                status="active",
                reviewed_at=now,
            )
        )
        await session.flush()
        session.add(
            SourceObject(
                id="object",
                tenant_id="north",
                mapping_id="mapping",
                item_id="file",
                mapping_revision=1,
                remote_version="v1",
            )
        )
        session.add(
            BulkBatch(
                id="batch",
                tenant_id="north",
                subject="owner",
                workspace_id="workspace",
                project_id="project",
                parent_id="folder",
                key_hash="b" * 64,
                request_hash="c" * 64,
                request_json={},
                total_bytes=1,
                expires_at=now + timedelta(days=1),
            )
        )
        await session.flush()
        session.add(
            BulkItem(
                id="item",
                batch_id="batch",
                ordinal=0,
                client_item_id="file",
                filename="file.txt",
                mode="document",
                size_bytes=1,
                sha256="d" * 64,
                source_id="source",
                asset_id="asset",
            )
        )
        await session.flush()
        session.add(
            SourceImportAttempt(
                id="attempt",
                tenant_id="north",
                mapping_id="mapping",
                mapping_revision=1,
                object_id="object",
                generation=1,
                intake_item_id="item",
                provider="google_drive",
                external_subject="remote-owner",
                drive_id="drive",
                remote_item_id="file",
                remote_version="v1",
                source_id="source",
                asset_id="asset",
                sha256="d" * 64,
                size_bytes=1,
            )
        )
        await session.flush()
        session.add(
            SourceImportedAsset(
                asset_id="asset", tenant_id="north", source_id="source", initial_attempt_id="attempt"
            )
        )
    return sessions


async def test_numbered_page_excludes_imported_titles_before_filter_and_total(reviews):
    from koinon.evidence.entities import EvidenceReview
    from koinon.exports.entities import ExportRecord
    from koinon.exports.repositories import KnowledgeExportRepository

    _, _, context = reviews
    sessions = await imported_graph(context)
    now = datetime.now(UTC)
    async with sessions.begin() as session:
        for identifier, title, manifest in (
            ("local", "Ordinary notes", []),
            ("imported", "Confidential acquisition", [{"asset_id": "asset"}]),
        ):
            session.add(
                EvidenceReview(
                    id=identifier,
                    tenant_id="north",
                    owner_subject="owner",
                    kind="export",
                    title=title,
                    revision="a" * 64,
                    request_json={},
                    snapshot_json={},
                    manifest_json=manifest,
                    created_at=now,
                    expires_at=now + timedelta(days=1),
                )
            )
            await session.flush()
            session.add(
                ExportRecord(
                    id=identifier,
                    tenant_id="north",
                    owner_subject="owner",
                    review_id=identifier,
                    created_at=now,
                    expires_at=now + timedelta(days=1),
                )
            )
    async with sessions() as session:
        repository = KnowledgeExportRepository(session=session)
        page = await repository.page("owner", "north")
        assert page["total"] == 1 and [row.id for row in page["items"]] == ["local"]
        assert await repository.active_count("owner", "north") == 2
        probe = await repository.page("owner", "north", q="Confidential")
        assert probe["items"] == [] and probe["total"] == probe["pages"] == 0


async def reader_export(reviews, monkeypatch):
    from types import SimpleNamespace

    from sqlalchemy import update

    from koinon.catalog.service import CatalogService
    from koinon.evidence.dtos import SourceReference
    from koinon.evidence.reviews import digest
    from koinon.integrations.content_sources.entities import PersonalSourceConnection
    from koinon.integrations.content_sources.import_entities import SourceImportAttempt
    from koinon.integrations.content_sources.mapping_entities import SourceMapping, SourceObject
    from koinon.integrations.content_sources.read_authority import SourceReadAuthority, source_authority
    from koinon.integrations.content_sources.read_dtos import ReaderSelectionInput
    from koinon.integrations.content_sources.read_repository import SourceReadRepository
    from koinon.integrations.content_sources.read_service import SourceReader
    from koinon.integrations.content_sources.reader_access import RemoteReadObservation
    from koinon.integrations.content_sources.reader_selection_repository import (
        SourceReaderSelectionRepository,
    )
    from koinon.integrations.content_sources.reader_selection_service import SourceReaderSelections
    from koinon.integrations.content_sources.sync_entities import (
        SourceImportedVersion,
        SourceMappingPolicy,
        SourceSyncState,
    )
    from koinon.knowledge.entities import DomainBinding

    evidence, snapshots, context = reviews
    sessions = await imported_graph(context)
    async with sessions.begin() as session:
        await session.execute(
            update(PersonalSourceConnection).values(
                issuer="https://accounts.google.com",
                config_fingerprint="f" * 64,
                scopes=["https://www.googleapis.com/auth/drive.readonly"],
            )
        )
        connection = await session.get(PersonalSourceConnection, "connection")
        authority, fingerprint = source_authority(connection)
        session.add(
            SourceMappingPolicy(
                id="policy",
                tenant_id="north",
                owner="owner",
                mapping_id="mapping",
                revision=1,
                mapping_revision=1,
                authority_sha256=fingerprint,
                policy_json={"authority": authority},
                policy_sha256=digest({"authority": authority}),
                root_ancestry_json=["root"],
                review_id="policy-review",
                review_digest="a" * 64,
                review_expires_at=datetime.now(UTC) + timedelta(hours=1),
                accepted_by="owner",
                accepted_at=datetime.now(UTC),
            )
        )
        await session.flush()
        session.add(
            SourceSyncState(
                mapping_id="mapping", tenant_id="north", accepted_policy_id="policy", enabled=False
            )
        )
        await session.execute(update(SourceMapping).values(config_fingerprint="f" * 64))
        await session.execute(update(SourceObject).values(state="imported"))
        await session.execute(
            update(SourceImportAttempt).values(
                receipt_json={"version_id": "v1"}, committed_at=datetime.now(UTC)
            )
        )
        session.add(
            DomainBinding(
                id="binding",
                tenant_id="north",
                catalog_id="asset",
                workspace_id="workspace",
                domain="canon",
                entity_kind="document",
                native_id="native-doc",
                native_workspace_id="native-space",
                created_by="owner",
            )
        )
        session.add(
            SourceImportedVersion(
                attempt_id="attempt",
                tenant_id="north",
                source_id="source",
                asset_id="asset",
                domain="canon",
                native_workspace_id="native-space",
                native_source_id="native-doc",
                native_asset_id="native-doc",
                native_version_id="v1",
                extraction_id="extraction",
            )
        )

    class Remote:
        calls = []
        connections = SimpleNamespace(
            registrations=SimpleNamespace(get=lambda provider: SimpleNamespace(fingerprint="f" * 64))
        )

        async def check(self, actor, tenant, connection, targets):
            unit = current_unit_of_work("primary")
            assert unit is None or unit.completed
            self.calls.append((actor, tenant, connection))
            return tuple(RemoteReadObservation(target, datetime.now(UTC), 1) for target in targets)

    catalog = context.get_bean(CatalogService)
    records = context.get_bean(SourceReadRepository)
    selections = SourceReaderSelections(context.get_bean(SourceReaderSelectionRepository), catalog)
    await selections.replace(
        "owner",
        "north",
        ReaderSelectionInput(
            expected_revision=0,
            operation_id=uuid4(),
            connections=[{"provider": "google_drive", "connection_id": "connection"}],
        ),
    )
    remote = Remote()
    reader = SourceReader(SourceReadAuthority(records, remote, catalog), selections, records)
    evidence.source_reader = SimpleNamespace(get=lambda: reader)
    reference = SourceReference(
        id="source-pin",
        asset_id="asset",
        source_id="source",
        title="Protected document",
        kind="document",
        source_version_id="v1",
        extraction_id="extraction",
        source_part_id="part",
        source_part_sha256="a" * 64,
        page_basis="recorded_loader",
        used_revision="source-part-sha256:" + "a" * 64,
    )
    original = snapshots.snapshot

    async def source_snapshot(*args, **kwargs):
        return (await original(*args, **kwargs)).model_copy(update={"sources": (reference,)})

    monkeypatch.setattr(snapshots, "snapshot", source_snapshot)
    return context.get_bean(KnowledgeExports), sessions, remote


@pytest.mark.parametrize("surface", ["get", "download"])
async def test_current_reader_disconnect_blocks_saved_export(reviews, monkeypatch, surface):
    from sqlalchemy import update

    from koinon.integrations.content_sources.entities import PersonalSourceConnection
    from koinon.integrations.content_sources.errors import SourceError

    service, sessions, remote = await reader_export(reviews, monkeypatch)
    _, created = await created_export(reviews[2])
    assert remote.calls and all(actor == "owner" for actor, _, _ in remote.calls)
    async with sessions.begin() as session:
        await session.execute(update(PersonalSourceConnection).values(status="disconnected", revision=2))
    with pytest.raises(SourceError):
        await getattr(service, surface)("owner", "north", created.id)


@pytest.mark.parametrize("surface", ["get", "download"])
async def test_denied_export_preflight_never_loads_protected_review_body(reviews, monkeypatch, surface):
    from sqlalchemy import event, update

    from koinon.integrations.content_sources.entities import PersonalSourceConnection
    from koinon.integrations.content_sources.errors import SourceError

    service, sessions, _ = await reader_export(reviews, monkeypatch)
    _, created = await created_export(reviews[2])
    async with sessions.begin() as session:
        await session.execute(update(PersonalSourceConnection).values(status="disconnected", revision=2))
    engine = reviews[2].get_bean(DataSourceRegistry).primary.engine.sync_engine
    queries = []

    def observed(connection, cursor, statement, parameters, context, many):
        queries.append(statement)

    event.listen(engine, "before_cursor_execute", observed)
    try:
        with pytest.raises(SourceError):
            await getattr(service, surface)("owner", "north", created.id)
    finally:
        event.remove(engine, "before_cursor_execute", observed)
    assert queries
    assert not any("koinon_evidence_reviews.title" in statement for statement in queries)


async def test_foreign_owner_and_borrowed_connection_cannot_release_exports(reviews, monkeypatch):
    from koinon.catalog.errors import AccessDenied
    from koinon.exports.dtos import ExportBrowseInput
    from koinon.integrations.content_sources.entities import PersonalSourceConnection
    from koinon.integrations.content_sources.errors import SourceError

    service, sessions, remote = await reader_export(reviews, monkeypatch)
    _, created = await created_export(reviews[2])
    remote.calls.clear()
    with pytest.raises(AccessDenied):
        await service.download("other", "north", created.id)
    async with sessions.begin() as session:
        session.add(
            PersonalSourceConnection(
                id="foreign",
                tenant_id="north",
                owner="other",
                provider="google_drive",
                status="connected",
                external_subject="provider-other",
            )
        )
    with pytest.raises(SourceError):
        await service.browse(
            "owner",
            "north",
            ExportBrowseInput(
                reader_source_connections=[{"provider": "google_drive", "connection_id": "foreign"}]
            ),
        )
    assert remote.calls == []


async def test_disconnect_between_source_check_and_commit_preserves_unused_review(reviews, monkeypatch):
    from contextlib import asynccontextmanager

    from sqlalchemy import select, update

    from koinon.evidence.entities import EvidenceReview
    from koinon.exports.entities import ExportRecord
    from koinon.integrations.content_sources.entities import PersonalSourceConnection
    from koinon.integrations.content_sources.errors import SourceError
    from koinon.integrations.content_sources.read_service import SourceReadOperation

    service, sessions, _ = await reader_export(reviews, monkeypatch)
    preview = await service.preview(
        "owner",
        "north",
        ConversationExportInput(kind="conversation", thread_id="t", message_ids=["m"], format="json"),
    )
    original = SourceReadOperation.local_fence

    @asynccontextmanager
    async def disconnect_before_fence(operation):
        async with sessions.begin() as session:
            await session.execute(update(PersonalSourceConnection).values(status="disconnected", revision=2))
        async with original(operation):
            yield

    monkeypatch.setattr(SourceReadOperation, "local_fence", disconnect_before_fence)
    with pytest.raises(SourceError):
        await service.create(
            "owner", "north", ExportCreate(review_id=preview.id, expected_revision=preview.revision)
        )
    async with sessions() as session:
        assert (await session.get(EvidenceReview, preview.id)).consumed_at is None
        assert list(await session.scalars(select(ExportRecord.id))) == []


async def shared_cursor_store(service, context):
    from types import SimpleNamespace

    from pyfly.cache.adapters.postgres import PostgresCacheAdapter

    from koinon.integrations.content_sources.read_cursors import SourceBrowseCursors

    cache = PostgresCacheAdapter(context.get_bean(DataSourceRegistry).primary.engine)
    await cache.start()
    service.cursors = SimpleNamespace(get=lambda: SourceBrowseCursors(cache))
    return cache


async def test_reader_browse_hides_denied_rows_without_totals_and_rechecks_each_page(reviews, monkeypatch):
    from sqlalchemy import update

    from koinon.exports.dtos import ExportBrowseInput
    from koinon.integrations.content_sources.entities import PersonalSourceConnection

    service, sessions, _ = await reader_export(reviews, monkeypatch)
    await created_export(reviews[2])
    await created_export(reviews[2])
    cache = await shared_cursor_store(service, reviews[2])
    try:
        first = await service.browse("owner", "north", ExportBrowseInput(page_size=1))
        assert len(first.items) == 1 and first.next_cursor
        assert first.total is None and first.total_is_exact is False
        opted_out = await service.browse(
            "owner", "north", ExportBrowseInput(page_size=1, reader_source_connections=[])
        )
        assert opted_out.items == () and opted_out.next_cursor and opted_out.total is None
        async with sessions.begin() as session:
            await session.execute(update(PersonalSourceConnection).values(status="disconnected", revision=2))
        second = await service.browse(
            "owner", "north", ExportBrowseInput(page_size=1, cursor=first.next_cursor)
        )
        assert second.items == () and second.next_cursor and second.total is None
        last = await service.browse(
            "owner", "north", ExportBrowseInput(page_size=1, cursor=second.next_cursor)
        )
        assert last.items == () and last.next_cursor is None
    finally:
        await cache.stop()


async def test_reader_cursor_cannot_survive_filter_or_selection_changes(reviews, monkeypatch):
    from pyfly.kernel import InvalidRequestException

    from koinon.exports.dtos import ExportBrowseInput
    from koinon.integrations.content_sources.read_dtos import ReaderSelectionInput

    service, _, _ = await reader_export(reviews, monkeypatch)
    await created_export(reviews[2])
    cache = await shared_cursor_store(service, reviews[2])
    try:
        first = await service.browse("owner", "north", ExportBrowseInput(page_size=1))
        with pytest.raises(InvalidRequestException) as changed:
            await service.browse(
                "owner", "north", ExportBrowseInput(page_size=1, cursor=first.next_cursor, q="other")
            )
        assert changed.value.code == "SOURCE_CURSOR_EXPIRED"
        reader = service.reviews.source_reader.get()
        await reader.selections.replace(
            "owner", "north", ReaderSelectionInput(expected_revision=1, operation_id=uuid4(), connections=[])
        )
        with pytest.raises(InvalidRequestException) as changed:
            await service.browse("owner", "north", ExportBrowseInput(page_size=1, cursor=first.next_cursor))
        assert changed.value.code == "SOURCE_CURSOR_EXPIRED"
    finally:
        await cache.stop()


async def test_source_revoked_after_render_never_releases_download(reviews, monkeypatch):
    import koinon.exports.service as module
    from koinon.integrations.content_sources.errors import SourceError

    service, _, _ = await reader_export(reviews, monkeypatch)
    _, created = await created_export(reviews[2])
    original = module.render_transcript
    uri = (
        reviews[2]
        .get_bean(DataSourceRegistry)
        .primary.engine.url.set(drivername="postgresql")
        .render_as_string(hide_password=False)
    )

    def revoke_after_render(*args, **kwargs):
        rendered = original(*args, **kwargs)
        with psycopg.connect(uri) as connection:
            connection.execute("UPDATE koinon_content_connections SET status='disconnected',revision=2")
        return rendered

    monkeypatch.setattr(module, "render_transcript", revoke_after_render)
    with pytest.raises(SourceError):
        await service.download("owner", "north", created.id)
    assert service._downloads == 0


@pytest.mark.parametrize("change", ["cancelled", "expired", "review_changed"])
async def test_export_state_changed_during_render_never_releases_download(reviews, monkeypatch, change):
    import koinon.exports.service as module
    from koinon.catalog.errors import AccessDenied

    service, created = await created_export(reviews[2])
    original = module.render_transcript
    uri = (
        reviews[2]
        .get_bean(DataSourceRegistry)
        .primary.engine.url.set(drivername="postgresql")
        .render_as_string(hide_password=False)
    )

    def cancel_after_render(*args, **kwargs):
        rendered = original(*args, **kwargs)
        with psycopg.connect(uri) as connection:
            if change == "cancelled":
                connection.execute("UPDATE koinon_exports SET cancelled_at=now() WHERE id=%s", (created.id,))
            elif change == "expired":
                connection.execute("UPDATE koinon_exports SET expires_at=now() WHERE id=%s", (created.id,))
            else:
                connection.execute(
                    "UPDATE koinon_evidence_reviews SET revision=%s "
                    "WHERE id=(SELECT review_id FROM koinon_exports WHERE id=%s)",
                    ("b" * 64, created.id),
                )
        return rendered

    monkeypatch.setattr(module, "render_transcript", cancel_after_render)
    with pytest.raises(AccessDenied) as error:
        await service.download("owner", "north", created.id)
    assert error.value.code == "EXPORT_UNAVAILABLE"


@pytest.mark.parametrize("origin_path", ["results", "dependencies", "turns"])
async def test_legacy_counts_resolve_remembered_origins_and_exclude_unknowns(reviews, origin_path):
    from koinon.assistants.entities import (
        AgentConfiguration,
        ChatMessage,
        ChatRun,
        ChatThread,
        Provider,
        ToolResult,
    )
    from koinon.assistants.memory.dtos import MemoryDependency, MemoryManifest, MemoryResultPin
    from koinon.assistants.memory.entities import ChatMemoryManifest
    from koinon.evidence.entities import EvidenceReview
    from koinon.evidence.reviews import digest
    from koinon.exports.entities import ExportRecord
    from koinon.exports.repositories import KnowledgeExportRepository
    from koinon.organization_chat.dtos import OrganizationMemoryPolicy

    _, _, context = reviews
    sessions = await imported_graph(context)
    now = datetime.now(UTC)
    async with sessions.begin() as session:
        session.add(
            Provider(
                id="provider",
                tenant_id="north",
                name="Controlled",
                kind="openai",
                base_url="https://fixture.invalid",
            )
        )
        await session.flush()
        session.add(
            AgentConfiguration(
                id="agent", tenant_id="north", provider_id="provider", name="Agent", model_id="fixture"
            )
        )
        await session.flush()
        for kind in ("local", "imported", "missing"):
            run, thread, answer, user = (kind + suffix for suffix in ("-run", "-thread", "-answer", "-user"))
            result_id, generation_id = kind + "-result", kind + "-generation"
            session.add(ChatThread(id=thread, tenant_id="north", subject="owner", title="Saved thread"))
            await session.flush()
            session.add_all(
                [
                    ChatMessage(id=answer, thread_id=thread, role="assistant", text="Stored answer"),
                    ChatMessage(id=user, thread_id=thread, role="user", text="Question"),
                ]
            )
            await session.flush()
            session.add(
                ChatRun(
                    id=run,
                    tenant_id="north",
                    thread_id=thread,
                    message_id=answer,
                    user_message_id=user,
                    agent_id="agent",
                    agent_revision=1,
                    provider_revision=1,
                    client_request_id=kind,
                    payload_hash="a" * 64,
                )
            )
            await session.flush()
            payload = {
                "source_manifest": {
                    "complete": True,
                    "sources": [] if kind == "local" else [{"asset_id": "asset"}],
                }
            }
            result_hash = digest({"kind": "search", "payload": payload})
            if kind != "missing":
                session.add(ToolResult(id=result_id, run_id=run, kind="search", payload=payload))
            session.add(ToolResult(id=generation_id, run_id=run, kind="generation", payload={}))
            await session.flush()
            pin = MemoryResultPin(id=result_id, sha256=result_hash)
            binding = {
                "run_id": run,
                "generation_id": None,
                "manifest_sha256": None,
                "results": [pin.model_dump(mode="json")],
            }
            if origin_path != "results":
                dependency = MemoryDependency(
                    run_id=run,
                    generation_id=generation_id,
                    thread_id=thread,
                    conversation_title="Prior conversation",
                    user_created_at=now,
                    user_message_id=user,
                    user_sha256="a" * 64,
                    answer_message_id=answer,
                    answer_sha256="b" * 64,
                    scope_sha256="c" * 64,
                    attachment_sha256="d" * 64,
                    result_pins=(pin,),
                )
                manifest = MemoryManifest(
                    generation_id=generation_id,
                    run_id=run,
                    tenant_id="north",
                    subject="owner",
                    thread_id=thread,
                    mode="current_thread",
                    scope_sha256="c" * 64,
                    organization_policy_revision=0,
                    effective_policy=OrganizationMemoryPolicy(),
                    input_sha256="a" * 64,
                    created_at=now,
                    **{origin_path: (dependency,)},
                )
                document = manifest.model_dump(mode="json")
                fingerprint = digest(document)
                session.add(
                    ChatMemoryManifest(
                        id=kind + "-manifest",
                        generation_id=generation_id,
                        run_id=run,
                        tenant_id="north",
                        subject="owner",
                        thread_id=thread,
                        start_sequence=0,
                        scope_sha256="c" * 64,
                        manifest_json=document,
                        manifest_sha256=fingerprint,
                        created_at=now,
                    )
                )
                binding = {
                    "run_id": run,
                    "generation_id": generation_id,
                    "manifest_sha256": fingerprint,
                    "results": [],
                }
            session.add(
                EvidenceReview(
                    id=kind + "-review",
                    tenant_id="north",
                    owner_subject="owner",
                    kind="export",
                    title="Local notes" if kind == "local" else "Protected notes",
                    revision="a" * 64,
                    request_json={},
                    snapshot_json={
                        "thread_id": thread,
                        "messages": [{"id": answer}],
                        "memory_bindings": [binding],
                    },
                    manifest_json=[],
                    created_at=now,
                    expires_at=now + timedelta(days=1),
                )
            )
            await session.flush()
            session.add(
                ExportRecord(
                    id=kind + "-export",
                    tenant_id="north",
                    owner_subject="owner",
                    review_id=kind + "-review",
                    created_at=now,
                    expires_at=now + timedelta(days=1),
                )
            )
    async with sessions() as session:
        repository = KnowledgeExportRepository(session=session)
        result = await repository.page("owner", "north")
        assert result["total"] == 1 and [row.id for row in result["items"]] == ["local-export"]
        hidden = await repository.page("owner", "north", q="Protected")
        assert hidden["items"] == [] and hidden["total"] == hidden["pages"] == 0
