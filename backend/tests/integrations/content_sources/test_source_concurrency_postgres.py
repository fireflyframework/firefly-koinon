# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Opposing connections exercise the migrated schema using the restricted runtime role."""

import asyncio
from datetime import UTC, datetime, timedelta

import psycopg
import pytest
from psycopg import sql
from sqlalchemy import select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from test_source_migration_postgres import (
    TABLES,
    load,
    upgrade_sources,
)
from test_source_migration_postgres import (
    source_database as source_database,
)

from koinon.catalog.entities import CatalogEntry
from koinon.integrations.content_sources.entities import PersonalSourceConnection
from koinon.integrations.content_sources.import_entities import SourceImportAttempt
from koinon.integrations.content_sources.import_repository import SourceImportRepository
from koinon.integrations.content_sources.mapping_entities import SourceMapping, SourceObject
from koinon.integrations.content_sources.mapping_repository import SourceMappingRepository
from koinon.integrations.content_sources.repositories import SourceConnectionRepository
from koinon.jobs.entities import Job as Job
from koinon.knowledge.bulk.entities import BulkBatch, BulkItem

pytestmark = pytest.mark.integration
TENANT, OWNER = "retained", "issuer|alice"


@pytest.fixture
async def source_sessions(source_database):
    target, role, engine = source_database
    upgrade_sources(engine)
    owner_engine = create_async_engine(target.set(drivername="postgresql+asyncpg"))
    owner_sessions = async_sessionmaker(owner_engine, expire_on_commit=False)
    async with owner_sessions.begin() as session:
        for identifier, kind, parent in (
            ("workspace", "workspace", None),
            ("project", "project", "workspace"),
            ("folder", "folder", "project"),
            ("source", "source", "folder"),
            ("asset", "document", "source"),
        ):
            session.add(
                CatalogEntry(
                    id=identifier,
                    tenant_id=TENANT,
                    kind=kind,
                    name=identifier,
                    workspace_id="workspace",
                    project_id="project",
                    parent_id=parent,
                    created_by=OWNER,
                )
            )
            await session.flush()
        session.add(
            PersonalSourceConnection(
                id="connection",
                tenant_id=TENANT,
                owner=OWNER,
                provider="google_drive",
                status="connected",
                revision=1,
                external_subject="provider-alice",
                issuer="https://accounts.google.com",
                secret_ciphertext=b"encrypted-grant",
            )
        )
        await session.flush()
        session.add(
            SourceMapping(
                id="mapping",
                tenant_id=TENANT,
                owner=OWNER,
                connection_id="connection",
                provider="google_drive",
                issuer="https://accounts.google.com",
                external_subject="provider-alice",
                drive_id="drive",
                root_id="root",
                workspace_id="workspace",
                project_id="project",
                parent_id="folder",
                request_json={"recursive": True, "removal_policy": "retire"},
                request_sha256="a" * 64,
                status="active",
                revision=1,
                reviewed_at=datetime.now(UTC),
            )
        )
        await session.flush()
        session.add(
            SourceObject(
                id="origin",
                tenant_id=TENANT,
                mapping_id="mapping",
                item_id="remote-file",
                generation=1,
                mapping_revision=1,
                remote_version="v1",
                state="pending",
            )
        )
        session.add(
            BulkBatch(
                id="batch",
                tenant_id=TENANT,
                subject=OWNER,
                workspace_id="workspace",
                project_id="project",
                parent_id="folder",
                key_hash="b" * 64,
                request_hash="c" * 64,
                request_json={},
                total_bytes=7,
                expires_at=datetime.now(UTC) + timedelta(days=1),
            )
        )
        await session.flush()
        session.add(
            BulkItem(
                id="item",
                batch_id="batch",
                ordinal=0,
                client_item_id="remote-file",
                filename="report.docx",
                mode="document",
                size_bytes=7,
                sha256="d" * 64,
                source_id="source",
                asset_id="asset",
                status="awaiting_upload",
                native_workspace_id="native-space",
            )
        )
    await owner_engine.dispose()
    uri = target.set(drivername="postgresql").render_as_string(hide_password=False)
    roles = load("deploy/provision_roles.py")
    with psycopg.connect(uri) as owner:
        owner.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(role)))
        for table in (
            *TABLES,
            "lattice_tenants",
            "lattice_catalog",
            "koinon_bulk_batches",
            "koinon_bulk_items",
        ):
            roles.grant_table(owner, table, role)
    runtime = target.set(drivername="postgresql+asyncpg", username=role, password=None)
    runtime_engine = create_async_engine(runtime)
    try:
        yield async_sessionmaker(runtime_engine, expire_on_commit=False), uri
    finally:
        await runtime_engine.dispose()


async def wait_for_blocked_connection(uri, application):
    """Observe PostgreSQL's actual lock wait, instead of assuming task scheduling order."""
    async with await psycopg.AsyncConnection.connect(uri, autocommit=True) as connection:
        async with asyncio.timeout(5):
            while True:
                cursor = await connection.execute(
                    "SELECT wait_event_type FROM pg_stat_activity "
                    "WHERE application_name=%s AND datname=current_database()",
                    (application,),
                )
                if await cursor.fetchone() == ("Lock",):
                    return


async def observe(session, version="v2", state="pending"):
    return await SourceMappingRepository(session=session).observe(
        TENANT, "mapping", 1, "origin", 1, connection_revision=1, version=version, state=state
    )


async def reserve(session):
    return await SourceImportRepository(session=session).reserve(
        TENANT, "mapping", 1, "origin", 1, "item", connection_revision=1
    )


def receipt():
    return {
        "domain": "canon",
        "native_workspace_id": "native-space",
        "native_source_id": "native-source",
        "native_asset_id": "native-document",
        "sha256": "d" * 64,
        "size_bytes": 7,
        "source_version_id": "native-version",
        "extraction_id": "extraction",
    }


@pytest.mark.parametrize("winner", ["disconnect", "refresh"])
async def test_refresh_and_disconnect_cannot_both_commit_from_one_revision(source_sessions, winner):
    sessions, uri = source_sessions
    async with sessions.begin() as seed:
        assert await SourceConnectionRepository(session=seed).reserve_refresh(
            TENANT, OWNER, "connection", 1, "rotation", datetime.now(UTC) + timedelta(minutes=5)
        )

    async def change(session, action):
        repository = SourceConnectionRepository(session=session)
        if action == "disconnect":
            return await repository.disconnect(TENANT, OWNER, "connection", 1)
        return await repository.complete_refresh(TENANT, OWNER, "connection", 1, "rotation", b"new", ["read"])

    async with sessions() as first, sessions() as second:
        assert await change(first, winner)
        await second.execute(text("SET LOCAL application_name='source-rotation-opponent'"))
        other = asyncio.create_task(change(second, "refresh" if winner == "disconnect" else "disconnect"))
        try:
            await wait_for_blocked_connection(uri, "source-rotation-opponent")
            await first.commit()
            assert not await asyncio.wait_for(other, 5)
            await second.commit()
        finally:
            if not other.done():
                other.cancel()
                await asyncio.gather(other, return_exceptions=True)
    async with sessions() as check:
        connection = await check.get(PersonalSourceConnection, "connection")
        assert connection.revision == 2 and connection.refresh_operation is None
        assert connection.secret_ciphertext == (None if winner == "disconnect" else b"new")


async def test_mapping_revision_change_fences_waiting_observation(source_sessions):
    sessions, uri = source_sessions
    async with sessions() as first, sessions() as second:
        assert await SourceMappingRepository(session=first).lock_active(TENANT, "mapping", 1, 1)
        await first.execute(update(SourceMapping).where(SourceMapping.id == "mapping").values(revision=2))
        await second.execute(text("SET LOCAL application_name='source-mapping-opponent'"))
        other = asyncio.create_task(observe(second))
        try:
            await wait_for_blocked_connection(uri, "source-mapping-opponent")
            await first.commit()
            assert not await asyncio.wait_for(other, 5)
            await second.commit()
        finally:
            if not other.done():
                other.cancel()
                await asyncio.gather(other, return_exceptions=True)
    async with sessions() as check:
        item = await check.get(SourceObject, "origin")
        assert item.generation == 1 and item.remote_version == "v1"


async def test_only_one_opposing_observation_advances_the_captured_generation(source_sessions):
    sessions, uri = source_sessions
    async with sessions() as first, sessions() as second:
        assert await observe(first, "v2")
        await second.execute(text("SET LOCAL application_name='source-generation-opponent'"))
        other = asyncio.create_task(observe(second, "v3"))
        try:
            await wait_for_blocked_connection(uri, "source-generation-opponent")
            await first.commit()
            assert not await asyncio.wait_for(other, 5)
            await second.commit()
        finally:
            if not other.done():
                other.cancel()
                await asyncio.gather(other, return_exceptions=True)
    async with sessions() as check:
        item = await check.get(SourceObject, "origin")
        assert item.generation == 2 and item.remote_version == "v2"


async def test_reservation_and_receipt_acknowledgment_are_idempotent_between_connections(source_sessions):
    sessions, uri = source_sessions
    async with sessions() as first, sessions() as second:
        attempt = await reserve(first)
        await second.execute(text("SET LOCAL application_name='source-reserve-opponent'"))
        other = asyncio.create_task(reserve(second))
        try:
            await wait_for_blocked_connection(uri, "source-reserve-opponent")
            await first.commit()
            replay = await asyncio.wait_for(other, 5)
            assert replay.id == attempt.id and replay.receipt_json is None
            await second.commit()
        finally:
            if not other.done():
                other.cancel()
                await asyncio.gather(other, return_exceptions=True)
    async with sessions.begin() as seed:
        await seed.execute(
            update(BulkItem)
            .where(BulkItem.id == "item")
            .values(status="succeeded", native_id="native-document", receipt_json=receipt())
        )
    async with sessions() as first, sessions() as second:
        assert await SourceImportRepository(session=first).record_commit(
            TENANT, attempt.id, connection_revision=1
        )
        captured = (await first.get(SourceImportAttempt, attempt.id)).committed_at
        await second.execute(text("SET LOCAL application_name='source-receipt-opponent'"))
        other = asyncio.create_task(
            SourceImportRepository(session=second).record_commit(TENANT, attempt.id, connection_revision=1)
        )
        try:
            await wait_for_blocked_connection(uri, "source-receipt-opponent")
            await first.commit()
            assert await asyncio.wait_for(other, 5)
            await second.commit()
        finally:
            if not other.done():
                other.cancel()
                await asyncio.gather(other, return_exceptions=True)
    async with sessions() as check:
        rows = (await check.scalars(select(SourceImportAttempt))).all()
        assert len(rows) == 1 and rows[0].receipt_json == receipt() and rows[0].committed_at == captured


async def test_committed_retirement_fences_waiting_native_receipt(source_sessions):
    sessions, uri = source_sessions
    async with sessions.begin() as seed:
        attempt = await reserve(seed)
        await seed.execute(
            update(BulkItem)
            .where(BulkItem.id == "item")
            .values(status="succeeded", native_id="native-document", receipt_json=receipt())
        )
    async with sessions() as first, sessions() as second:
        assert await observe(first, None, "deleted")
        await second.execute(text("SET LOCAL application_name='source-retired-opponent'"))
        other = asyncio.create_task(
            SourceImportRepository(session=second).record_commit(TENANT, attempt.id, connection_revision=1)
        )
        try:
            await wait_for_blocked_connection(uri, "source-retired-opponent")
            await first.commit()
            assert not await asyncio.wait_for(other, 5)
            await second.commit()
        finally:
            if not other.done():
                other.cancel()
                await asyncio.gather(other, return_exceptions=True)
    async with sessions() as check:
        assert (await check.get(SourceImportAttempt, attempt.id)).receipt_json is None
        assert (await check.get(SourceObject, "origin")).state == "deleted"
        assert (await check.get(BulkItem, "item")).status == "succeeded"


async def test_database_rejects_cross_tenant_origin_and_receipt_rewriting(source_sessions):
    sessions, uri = source_sessions
    async with sessions.begin() as seed:
        attempt = await reserve(seed)
        await seed.execute(
            update(BulkItem)
            .where(BulkItem.id == "item")
            .values(status="succeeded", native_id="native-document", receipt_json=receipt())
        )
    async with sessions.begin() as seed:
        assert await SourceImportRepository(session=seed).record_commit(
            TENANT, attempt.id, connection_revision=1
        )
    with psycopg.connect(uri, autocommit=True) as owner:
        owner.execute("INSERT INTO lattice_tenants(id,name,created_at) VALUES('other','Other',now())")
        with pytest.raises(psycopg.errors.ForeignKeyViolation):
            owner.execute("UPDATE koinon_content_objects SET tenant_id='other' WHERE id='origin'")
        with pytest.raises(psycopg.errors.ForeignKeyViolation):
            owner.execute("UPDATE koinon_content_mappings SET owner='issuer|bob' WHERE id='mapping'")
        for statement in (
            "UPDATE koinon_content_imports SET remote_version='forged'",
            "UPDATE koinon_content_imports SET receipt_json='{}'",
            "UPDATE koinon_content_imports SET receipt_json=NULL,committed_at=NULL",
            "DELETE FROM koinon_content_imports",
        ):
            with pytest.raises(psycopg.errors.CheckViolation):
                owner.execute(statement)
        # Retained origin FKs reject TRUNCATE before the table's own trigger can run.
        before = owner.execute("SELECT id,receipt_json FROM koinon_content_imports ORDER BY id").fetchall()
        with pytest.raises(psycopg.errors.FeatureNotSupported):
            owner.execute("TRUNCATE koinon_content_imports")
        after = owner.execute("SELECT id,receipt_json FROM koinon_content_imports ORDER BY id").fetchall()
        assert after == before
    runtime = sessions.kw["bind"].url.set(drivername="postgresql").render_as_string(hide_password=False)
    with psycopg.connect(runtime, autocommit=True) as caller:
        for statement in (
            "UPDATE koinon_content_imports SET remote_version='forged'",
            "DELETE FROM koinon_content_imports",
            "TRUNCATE koinon_content_imports",
        ):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                caller.execute(statement)
        with pytest.raises(psycopg.errors.CheckViolation):
            caller.execute("UPDATE koinon_content_imports SET receipt_json='{}'")
        assert caller.execute(
            "SELECT receipt_json->>'source_version_id' FROM koinon_content_imports"
        ).fetchone() == ("native-version",)


async def test_import_insert_cannot_bind_another_tenants_object(source_sessions):
    sessions, uri = source_sessions
    with psycopg.connect(uri) as owner:
        owner.execute("INSERT INTO lattice_tenants(id,name,created_at) VALUES('other','Other',now())")
    async with sessions() as caller:
        caller.add(
            SourceImportAttempt(
                id="foreign-attempt",
                tenant_id="other",
                mapping_id="mapping",
                mapping_revision=1,
                object_id="origin",
                generation=1,
                intake_item_id="item",
                provider="google_drive",
                external_subject="provider-alice",
                drive_id="drive",
                remote_item_id="remote-file",
                remote_version="v1",
                source_id="source",
                asset_id="asset",
                sha256="d" * 64,
                size_bytes=7,
            )
        )
        with pytest.raises(IntegrityError) as failure:
            await caller.flush()
        assert failure.value.orig.sqlstate == "23503"
