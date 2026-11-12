# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Real native PostgreSQL stages with a controlled authority boundary.

These tests qualify native callback coverage and transaction effects. The product
source guard and live provider authority are qualified by the backend composition.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from dataclasses import dataclass
from hashlib import sha256
from types import SimpleNamespace
from uuid import UUID, uuid4

import psycopg
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from psycopg import sql
from pyfly.data.transaction import infrastructure_unit
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from flyquery.core.services.ingestion.lineage import LineageConflict, LineageDenied
from flyquery.core.services.ingestion.reader import ColumnSchema, MaterialiseResult
from flyquery.core.services.ingestion.stages.parse import ParsedTable
from flyquery.core.services.ingestion.stages.reconcile import (
    DeferredReconcileChanges,
    publish_reconcile_changes,
    run_reconcile,
)
from flyquery.models.entities.embedding_set import EmbeddingSet, EmbeddingVector
from flyquery.models.entities.examples import Example
from flyquery.models.entities.provenance import SourceMetadataProvenance
from flyquery.models.entities.schema import SchemaChange, SchemaObject, SchemaSnapshot

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def configure_env(monkeypatch):
    """This native-only suite needs PostgreSQL, not the HTTP app or object stores."""
    monkeypatch.setenv("FLYQUERY_RUN_MIGRATIONS", "false")


@dataclass
class NativeDatabase:
    uri: str
    sessions: async_sessionmaker
    workspace: UUID
    dataset: UUID
    table: UUID
    previous: UUID
    snapshot: UUID
    objects: dict[str, UUID]

    async def rows(self, statement, values=None):
        async with self.sessions() as session:
            return (await session.execute(text(statement), values or {})).mappings().all()


@pytest.fixture
async def native_database(request):
    configured = os.environ.get("KOINON_CONTENT_SOURCES_TEST_PG_URL")
    if configured is None:
        configured = request.getfixturevalue("postgres_container").get_connection_url()
    admin = make_url(configured).set(drivername="postgresql")
    name = "native_stage_" + uuid4().hex
    with psycopg.connect(admin.render_as_string(hide_password=False), autocommit=True) as connection:
        connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    target = admin.set(database=name)
    sync = create_engine(target.set(drivername="postgresql+psycopg"))
    engine = create_async_engine(target.set(drivername="postgresql+asyncpg"))
    try:
        with sync.begin() as connection:
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            for entity in (
                SchemaSnapshot,
                SchemaObject,
                SchemaChange,
                SourceMetadataProvenance,
                Example,
                EmbeddingSet,
                EmbeddingVector,
            ):
                entity.__table__.create(connection)
            connection.execute(
                text(
                    "CREATE TABLE stage_authority(id integer PRIMARY KEY,revision integer NOT NULL,"
                    "enabled boolean NOT NULL)"
                )
            )
            connection.execute(text("INSERT INTO stage_authority VALUES(1,1,true)"))
        db = NativeDatabase(
            target.render_as_string(hide_password=False),
            async_sessionmaker(engine, expire_on_commit=False),
            uuid4(),
            uuid4(),
            uuid4(),
            uuid4(),
            uuid4(),
            {name: uuid4() for name in ("id", "account%", "accountX")},
        )
        async with db.sessions.begin() as session:
            session.add(
                SchemaSnapshot(
                    id=db.previous,
                    tenant_id="tenant",
                    workspace_id=db.workspace,
                    dataset_id=db.dataset,
                    table_id=db.table,
                    snapshot_hash="a" * 64,
                    n_columns=3,
                    n_rows_actual=2,
                    status="READY",
                    triggered_by="USER",
                    created_by="reader",
                )
            )
            parent = uuid4()
            session.add(
                SchemaObject(
                    id=parent,
                    tenant_id="tenant",
                    workspace_id=db.workspace,
                    table_id=db.table,
                    snapshot_id=db.previous,
                    kind="TABLE",
                    qualified_name="data.records",
                    source_hash="b" * 64,
                )
            )
            for column, identifier in db.objects.items():
                session.add(
                    SchemaObject(
                        id=identifier,
                        tenant_id="tenant",
                        workspace_id=db.workspace,
                        table_id=db.table,
                        snapshot_id=db.previous,
                        kind="COLUMN",
                        parent_id=parent,
                        qualified_name="data.records." + column,
                        data_type="BIGINT" if column == "id" else "VARCHAR",
                        source_hash="b" * 64,
                    )
                )
        yield db
    finally:
        await engine.dispose()
        sync.dispose()
        with psycopg.connect(admin.render_as_string(hide_password=False), autocommit=True) as connection:
            connection.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))


async def reconcile(db, columns=None, **options):
    return await run_reconcile(
        tenant_id="tenant",
        workspace_id=db.workspace,
        dataset_id=db.dataset,
        parsed=ParsedTable(
            table_id=db.table,
            name="records",
            qualified_name="data.records",
            sheet_or_json_path=None,
            parquet_key="prepared/records.parquet",
            result=MaterialiseResult(
                target_parquet_key="prepared/records.parquet",
                parquet_byte_size=120,
                n_rows_actual=2,
                columns=columns
                or (
                    ColumnSchema("id", "BIGINT", False, 0),
                    ColumnSchema("accountX", "VARCHAR", True, 1),
                ),
            ),
        ),
        actor="reader",
        triggered_by="SCHEDULED",
        session_factory=db.sessions,
        snapshot_id=db.snapshot,
        **options,
    )


async def test_replacement_preparation_does_not_change_the_published_snapshot(native_database):
    db = native_database
    guard = DatabaseStageGuard(db)
    queries = []

    def check_sql(connection, cursor, statement, parameters, context, many):
        if any(name in statement for name in ("flyquery_schema_objects", "flyquery_schema_snapshots")):
            assert guard.active in {"reconcile_read", "reconcile_write"}
            queries.append(guard.active)

    engine = db.sessions.kw["bind"]
    event.listen(engine.sync_engine, "before_cursor_execute", check_sql)
    try:
        result = await reconcile(db, guard=guard, defer_live_changes=True)
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", check_sql)
    assert queries.count("reconcile_read") == 4
    assert {snapshot for phase, snapshot in guard.phases if phase == "reconcile_write"} == {db.snapshot}
    old = await db.rows(
        "SELECT qualified_name,is_active FROM flyquery_schema_objects WHERE snapshot_id=:snapshot AND kind='COLUMN'",
        {"snapshot": db.previous},
    )
    assert len(old) == 3 and all(row["is_active"] for row in old)
    assert await db.rows("SELECT id FROM flyquery_schema_changes") == []
    assert result.removed_columns == ["account%"]
    assert result.pending_changes.removed_object_ids == (db.objects["account%"],)
    assert await db.rows(
        "SELECT status FROM flyquery_schema_snapshots WHERE id=:snapshot", {"snapshot": db.snapshot}
    ) == [{"status": "PARTIAL"}]


async def test_deferred_changes_publish_once_with_exact_ids_and_rollback(native_database):
    db = native_database
    prepared = await reconcile(db, defer_live_changes=True)
    # A restart reads the closed immutable value, not an in-memory callback.
    changes = DeferredReconcileChanges.model_validate_json(
        prepared.pending_changes.model_dump_json(by_alias=True)
    )
    assert changes.changes[0].change == "REMOVED"
    assert changes.changes[0].before_json.data_type == "VARCHAR"
    with pytest.raises(RuntimeError, match="publication failed"):
        async with db.sessions.begin() as session:
            await publish_reconcile_changes(session, changes)
            await session.execute(
                text("UPDATE flyquery_schema_snapshots SET status='READY' WHERE id=:id"), {"id": db.snapshot}
            )
            raise RuntimeError("publication failed")
    assert await db.rows("SELECT id FROM flyquery_schema_changes") == []
    assert all(
        row["is_active"]
        for row in await db.rows(
            "SELECT is_active FROM flyquery_schema_objects WHERE snapshot_id=:snapshot",
            {"snapshot": db.previous},
        )
    )
    async with db.sessions.begin() as session:
        await publish_reconcile_changes(session, changes)
        await session.execute(
            text("UPDATE flyquery_schema_snapshots SET status='READY' WHERE id=:id"), {"id": db.snapshot}
        )
    states = {
        row["id"]: row["is_active"]
        for row in await db.rows(
            "SELECT id,is_active FROM flyquery_schema_objects WHERE snapshot_id=:snapshot AND kind='COLUMN'",
            {"snapshot": db.previous},
        )
    }
    assert states == {db.objects["id"]: True, db.objects["account%"]: False, db.objects["accountX"]: True}
    recorded = await db.rows("SELECT id,column_name,change FROM flyquery_schema_changes")
    assert recorded == [{"id": changes.changes[0].id, "column_name": "account%", "change": "REMOVED"}]
    with pytest.raises(LineageConflict, match="snapshots"):
        async with db.sessions.begin() as session:
            await publish_reconcile_changes(session, changes)
    assert await db.rows("SELECT id,column_name,change FROM flyquery_schema_changes") == recorded


@pytest.mark.parametrize("field", ["tenant_id", "workspace_id", "table_id", "removed_object_ids"])
async def test_deferred_publication_rejects_substituted_scope_or_columns(native_database, field):
    db = native_database
    prepared = await reconcile(db, defer_live_changes=True)
    value = "other" if field == "tenant_id" else (uuid4(),) if field == "removed_object_ids" else uuid4()
    forged = prepared.pending_changes.model_copy(update={field: value})
    with pytest.raises(LineageConflict):
        async with db.sessions.begin() as session:
            await publish_reconcile_changes(session, forged)
    assert await db.rows("SELECT id FROM flyquery_schema_changes") == []
    assert all(
        row["is_active"]
        for row in await db.rows(
            "SELECT is_active FROM flyquery_schema_objects WHERE snapshot_id=:snapshot",
            {"snapshot": db.previous},
        )
    )


async def test_local_reconcile_keeps_eager_changes(native_database):
    db = native_database
    result = await reconcile(db)
    assert result.pending_changes is None
    assert await db.rows("SELECT column_name,change FROM flyquery_schema_changes") == [
        {"column_name": "account%", "change": "REMOVED"}
    ]
    assert await db.rows(
        "SELECT is_active FROM flyquery_schema_objects WHERE id=:id", {"id": db.objects["account%"]}
    ) == [{"is_active": False}]


@pytest.mark.parametrize("removed", ["account%", "account_"])
async def test_local_removed_column_does_not_match_a_like_wildcard(native_database, removed):
    db = native_database
    async with db.sessions.begin() as session:
        await session.execute(
            text("UPDATE flyquery_schema_objects SET qualified_name=:name WHERE id=:id"),
            {"name": "data.records." + removed, "id": db.objects["account%"]},
        )
    await reconcile(db)
    assert await db.rows(
        "SELECT is_active FROM flyquery_schema_objects WHERE id=:id", {"id": db.objects["accountX"]}
    ) == [{"is_active": True}]


async def test_local_removal_preserves_a_dotted_column_with_the_same_suffix(native_database):
    db = native_database
    async with db.sessions.begin() as session:
        for previous, literal in (("account%", "name"), ("accountX", "customer.name")):
            await session.execute(
                text("UPDATE flyquery_schema_objects SET qualified_name=:name WHERE id=:id"),
                {"name": "data.records." + literal, "id": db.objects[previous]},
            )
    await reconcile(
        db,
        columns=(ColumnSchema("id", "BIGINT", False, 0), ColumnSchema("customer.name", "VARCHAR", True, 1)),
    )
    assert await db.rows(
        "SELECT is_active FROM flyquery_schema_objects WHERE id=:id", {"id": db.objects["accountX"]}
    ) == [{"is_active": True}]
    assert await db.rows(
        "SELECT is_active FROM flyquery_schema_objects WHERE id=:id", {"id": db.objects["account%"]}
    ) == [{"is_active": False}]


class DatabaseStageGuard:
    """Controlled authority in PostgreSQL; not the product source authorization guard."""

    def __init__(self, db, *, denied=None):
        self.db = db
        self.denied = denied
        self.active = None
        self.phases = []
        self.model_targets = ()
        self.checking = False

    async def _check(self, session, target):
        self.checking = True
        try:
            await self._validate(session, target)
        finally:
            self.checking = False

    async def _validate(self, session, target):
        row = (
            await session.execute(text("SELECT revision,enabled FROM stage_authority WHERE id=1 FOR SHARE"))
        ).one()
        if not row.enabled or row.revision != 1:
            raise LineageDenied("Stage authority changed")
        assert target.tenant_id == "tenant"
        assert target.snapshot_id in {None, self.db.previous, self.db.snapshot}
        if target.table_id is not None:
            assert target.table_id == self.db.table
        if target.object_id is not None:
            scope = (
                await session.execute(
                    text(
                        "SELECT snapshot_id FROM flyquery_schema_objects WHERE id=:id AND tenant_id=:tenant"
                    ),
                    {"id": target.object_id, "tenant": target.tenant_id},
                )
            ).scalar_one()
            assert scope == target.snapshot_id

    @asynccontextmanager
    async def unit(self, phase, target):
        assert self.active is None
        if phase == self.denied:
            raise LineageDenied("Stage denied")
        async with infrastructure_unit(self.db.sessions) as session:
            await self._check(session, target)
            self.active = str(phase)
            self.phases.append((str(phase), target.snapshot_id))
            try:
                yield
            finally:
                self.active = None

    async def before_model(self, targets):
        assert self.active is None
        self.model_targets = targets
        async with infrastructure_unit(self.db.sessions) as session:
            for target in targets:
                await self._check(session, target)
                assert target.input_sha256 is not None and len(target.input_sha256) == 64


@pytest.mark.parametrize("phase", ["reconcile_read", "reconcile_write"])
async def test_reconcile_denial_blocks_native_effects(native_database, phase):
    db = native_database
    guard = DatabaseStageGuard(db, denied=phase)
    with pytest.raises(LineageDenied, match="Stage denied"):
        await reconcile(db, guard=guard, defer_live_changes=True)
    assert await db.rows("SELECT id FROM flyquery_schema_changes") == []
    assert (
        await db.rows(
            "SELECT id FROM flyquery_schema_objects WHERE snapshot_id=:snapshot", {"snapshot": db.snapshot}
        )
        == []
    )
    assert all(
        row["is_active"]
        for row in await db.rows(
            "SELECT is_active FROM flyquery_schema_objects WHERE snapshot_id=:snapshot",
            {"snapshot": db.previous},
        )
    )


@pytest.mark.parametrize("stage", ["sample", "profile"])
@pytest.mark.parametrize("denied", ["read", "write", None])
async def test_sample_profile_guard_covers_real_native_reads_and_writes(
    native_database, tmp_path, stage, denied
):
    from flyquery.core.services.ingestion.stages.profile import run_profile
    from flyquery.core.services.ingestion.stages.sample import run_sample

    db = native_database
    await reconcile(db, defer_live_changes=True)
    parquet = tmp_path / "records.parquet"
    pq.write_table(
        pa.table({"id": [1, 2], "accountX": ["synthetic@example.invalid", "other@example.invalid"]}), parquet
    )
    guard = DatabaseStageGuard(db, denied=f"{stage}_{denied}" if denied else None)
    queries = []

    def check_sql(connection, cursor, statement, parameters, context, many):
        if "flyquery_schema_objects" in statement and not guard.checking:
            expected = f"{stage}_read" if statement.lstrip().startswith("SELECT") else f"{stage}_write"
            assert guard.active == expected
            queries.append(expected)

    engine = db.sessions.kw["bind"]
    event.listen(engine.sync_engine, "before_cursor_execute", check_sql)
    try:
        args = dict(
            tenant_id="tenant",
            snapshot_id=db.snapshot,
            parquet_key=str(parquet),
            session_factory=db.sessions,
            guard=guard,
        )
        if stage == "sample":
            invocation = run_sample(
                **args,
                settings=SimpleNamespace(
                    pii_scanner="regex",
                    pii_policy_samples="redact",
                    sample_n=10,
                ),
            )
        else:
            invocation = run_profile(
                **args, n_rows_actual=2, settings=SimpleNamespace(profile_row_threshold=10)
            )
        if denied:
            with pytest.raises(LineageDenied, match="Stage denied"):
                await invocation
        else:
            await invocation
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", check_sql)
    rows = await db.rows(
        "SELECT qualified_name,sample_values_json,pii_tag,profile_json FROM flyquery_schema_objects "
        "WHERE snapshot_id=:snapshot AND kind='COLUMN' ORDER BY qualified_name",
        {"snapshot": db.snapshot},
    )
    assert len(rows) == 2
    if denied:
        assert all(
            row["sample_values_json"] is None and row["profile_json"] is None and row["pii_tag"] is None
            for row in rows
        )
        assert queries == ([] if denied == "read" else [f"{stage}_read"])
    elif stage == "sample":
        assert rows[0]["pii_tag"] == "EMAIL" and rows[0]["sample_values_json"] == []
        assert set(rows[1]["sample_values_json"]) == {"1", "2"}
        assert queries.count("sample_write") >= 3  # Policy and both sample writes are fenced.
    else:
        assert rows[1]["profile_json"]["distinct_estimate"] == 2
        assert rows[1]["profile_json"]["min"] == "1" and rows[1]["profile_json"]["max"] == "2"
        assert queries == ["profile_read", "profile_write", "profile_write"]


@pytest.mark.parametrize("change", ["revoke", "aba", None])
async def test_model_output_rechecks_postgres_authority_before_native_writes(native_database, change):
    from flyquery.core.services.ingestion.stages.embed import run_embed

    db = native_database
    await reconcile(db, defer_live_changes=True)
    guard = DatabaseStageGuard(db)
    sent = []

    class Embedder:
        model = "synthetic"

        async def embed_batch(self, texts):
            assert guard.active is None
            assert [target.input_sha256 for target in guard.model_targets] == [
                sha256(value.encode()).hexdigest() for value in texts
            ]
            sent.extend(texts)
            if change:
                async with db.sessions.begin() as session:
                    if change == "revoke":
                        await session.execute(text("UPDATE stage_authority SET enabled=false WHERE id=1"))
                    else:
                        await session.execute(
                            text("UPDATE stage_authority SET enabled=false,revision=2 WHERE id=1")
                        )
                        await session.execute(
                            text("UPDATE stage_authority SET enabled=true,revision=3 WHERE id=1")
                        )
            return [[0.1] * 1536 for _ in texts]

    invocation = run_embed(
        tenant_id="tenant",
        snapshot_id=db.snapshot,
        session_factory=db.sessions,
        embedder=Embedder(),
        guard=guard,
    )
    if change:
        with pytest.raises(LineageDenied, match="authority changed"):
            await invocation
    else:
        assert (await invocation)["embeddings_written"] == 3
    assert len(sent) == 3
    rows = await db.rows(
        "SELECT embedding IS NOT NULL AS vector,content_tsv IS NOT NULL AS tsv "
        "FROM flyquery_schema_objects WHERE snapshot_id=:snapshot",
        {"snapshot": db.snapshot},
    )
    assert len(rows) == 3
    assert all(row["vector"] == (change is None) and row["tsv"] == (change is None) for row in rows)


@pytest.mark.parametrize("fail_sidecar", [False, True])
async def test_versioned_sidecar_joins_the_complete_output_fence(native_database, fail_sidecar):
    from flyquery.core.agents.model_bindings import EmbeddingBinding, push_bindings, reset_bindings
    from flyquery.core.services.ingestion.stages.embed import run_embed
    from flyquery.web.conventions.context import TenantContext, set_tenant_context

    db = native_database
    await reconcile(db, defer_live_changes=True)
    guard = DatabaseStageGuard(db)

    class Embedder:
        model = "synthetic"

        async def embed_batch(self, texts):
            assert guard.active is None
            return [[0.1] * 1536 for _ in texts]

    embedder = Embedder()
    async with db.sessions.begin() as session:
        session.add(
            EmbeddingSet(
                id="stage-space",
                tenant_id="tenant",
                workspace_id=db.workspace,
                provider="synthetic",
                model="synthetic",
                dimensions=1536,
                config_fingerprint="d" * 64,
                status="active",
                created_by="reader",
            )
        )
        if fail_sidecar:
            await session.execute(
                text(
                    "CREATE FUNCTION reject_stage_vector() RETURNS trigger LANGUAGE plpgsql "
                    "AS $$ BEGIN RAISE EXCEPTION 'sidecar rejected'; END $$"
                )
            )
            await session.execute(
                text(
                    "CREATE TRIGGER reject_stage_vector BEFORE INSERT ON flyquery_embedding_vectors "
                    "FOR EACH ROW EXECUTE FUNCTION reject_stage_vector()"
                )
            )
    scope = set_tenant_context(
        TenantContext(
            tenant_id="tenant", workspace_id=str(db.workspace), actor="reader", correlation_id="stage-test"
        )
    )
    bindings = push_bindings(
        tenant_id="tenant",
        workspace_id=str(db.workspace),
        subject="reader",
        bindings={},
        required=False,
        embeddings={
            "structured.embedding": EmbeddingBinding(
                embedder=embedder,
                embedding_model="synthetic",
                dimensions=1536,
                storage_dimensions=1536,
                space_id="stage-space",
                versioned=True,
            )
        },
    )
    sidecar_phases = []

    def check_sidecar(connection, cursor, statement, parameters, context, many):
        if "INSERT INTO flyquery_embedding_vectors" in statement:
            sidecar_phases.append(guard.active)
            assert guard.active == "embed_write"

    engine = db.sessions.kw["bind"]
    event.listen(engine.sync_engine, "before_cursor_execute", check_sidecar)
    try:
        invocation = run_embed(
            tenant_id="tenant",
            snapshot_id=db.snapshot,
            session_factory=db.sessions,
            embedder=embedder,
            guard=guard,
        )
        if fail_sidecar:
            from sqlalchemy.exc import DBAPIError

            with pytest.raises(DBAPIError, match="sidecar rejected"):
                await invocation
        else:
            assert (await invocation)["embeddings_written"] == 3
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", check_sidecar)
        reset_bindings(bindings)
        scope.var.reset(scope.token)
    vectors = await db.rows("SELECT object_id FROM flyquery_embedding_vectors")
    rows = await db.rows(
        "SELECT embedding IS NOT NULL AS legacy,content_tsv IS NOT NULL AS tsv "
        "FROM flyquery_schema_objects WHERE snapshot_id=:snapshot",
        {"snapshot": db.snapshot},
    )
    assert len(vectors) == (0 if fail_sidecar else 3)
    assert all(not row["legacy"] and row["tsv"] == (not fail_sidecar) for row in rows)
    assert sidecar_phases == ["embed_write"] * (1 if fail_sidecar else 3)


@pytest.mark.parametrize("denied", ["embed_read", "embed_write"])
async def test_embedding_guard_denies_each_native_boundary(native_database, denied):
    from flyquery.core.services.ingestion.stages.embed import run_embed
    from flyquery.core.services.retrieval.embedder import NullEmbedder

    db = native_database
    await reconcile(db, defer_live_changes=True)
    with pytest.raises(LineageDenied, match="Stage denied"):
        await run_embed(
            tenant_id="tenant",
            snapshot_id=db.snapshot,
            session_factory=db.sessions,
            embedder=NullEmbedder(),
            guard=DatabaseStageGuard(db, denied=denied),
        )
    rows = await db.rows(
        "SELECT embedding,content_tsv FROM flyquery_schema_objects WHERE snapshot_id=:snapshot",
        {"snapshot": db.snapshot},
    )
    assert len(rows) == 3 and all(row["embedding"] is None and row["content_tsv"] is None for row in rows)


@pytest.mark.parametrize("revoke", ["before_model", "during_model", None])
async def test_rename_model_authority_is_not_swallowed_as_optional_failure(
    native_database, monkeypatch, revoke
):
    from flyquery.core.agents import rename_detection_agent

    db = native_database
    sent = []

    async def revoke_authority():
        async with db.sessions.begin() as session:
            await session.execute(text("UPDATE stage_authority SET enabled=false,revision=2 WHERE id=1"))

    class RenameGuard(DatabaseStageGuard):
        async def before_model(self, targets):
            if revoke == "before_model":
                await revoke_authority()
            await super().before_model(targets)

    guard = RenameGuard(db)

    class RenameAgent:
        async def run(self, prompt):
            assert guard.active is None
            assert {target.snapshot_id for target in guard.model_targets} == {db.previous, db.snapshot}
            assert all(
                target.input_sha256 == sha256(prompt.encode()).hexdigest() for target in guard.model_targets
            )
            sent.append(prompt)
            if revoke == "during_model":
                await revoke_authority()
            return SimpleNamespace(
                output=SimpleNamespace(
                    items=[
                        SimpleNamespace(new_column="renamed_a", confidence=0.2, rationale="Ambiguous names")
                    ]
                )
            )

    monkeypatch.setattr(rename_detection_agent, "build_rename_detection_agent", lambda _: RenameAgent())
    invocation = reconcile(
        db,
        guard=guard,
        defer_live_changes=True,
        settings=object(),
        columns=(
            ColumnSchema("id", "BIGINT", False, 0),
            ColumnSchema("renamed_a", "VARCHAR", True, 1),
            ColumnSchema("renamed_b", "VARCHAR", True, 2),
        ),
    )
    if revoke:
        with pytest.raises(LineageDenied, match="authority changed"):
            await invocation
        assert len(sent) == (0 if revoke == "before_model" else 1)
    else:
        result = await invocation
        assert len(sent) == 2
        changes = result.pending_changes.changes
        assert sum(change.change == "RENAMED_CANDIDATE" for change in changes) == 2
        assert all(
            change.after_json.candidates[0].rationale == "Ambiguous names"
            for change in changes
            if change.change == "RENAMED_CANDIDATE"
        )
    assert await db.rows("SELECT id FROM flyquery_schema_changes") == []
    assert all(
        row["is_active"]
        for row in await db.rows(
            "SELECT is_active FROM flyquery_schema_objects WHERE snapshot_id=:snapshot",
            {"snapshot": db.previous},
        )
    )


async def test_native_output_fence_serializes_authority_change(native_database):
    import asyncio

    from sqlalchemy.exc import DBAPIError

    from flyquery.core.services.ingestion.stages.embed import run_embed
    from flyquery.core.services.retrieval.embedder import NullEmbedder

    db = native_database
    await reconcile(db, defer_live_changes=True)
    entered, release = asyncio.Event(), asyncio.Event()

    class HoldingGuard(DatabaseStageGuard):
        @asynccontextmanager
        async def unit(self, phase, target):
            async with super().unit(phase, target):
                yield
                if phase == "embed_write" and not entered.is_set():
                    entered.set()
                    await release.wait()

    task = asyncio.create_task(
        run_embed(
            tenant_id="tenant",
            snapshot_id=db.snapshot,
            session_factory=db.sessions,
            embedder=NullEmbedder(),
            guard=HoldingGuard(db),
        )
    )
    try:
        async with asyncio.timeout(5):
            await entered.wait()
        # Opposing writer cannot cross the held output fence. NOWAIT makes this
        # deterministic without sleeps or assumptions about scheduling speed.
        with pytest.raises(DBAPIError, match="could not obtain lock"):
            async with db.sessions.begin() as session:
                await session.execute(text("SELECT id FROM stage_authority WHERE id=1 FOR UPDATE NOWAIT"))
    finally:
        release.set()
        result = await task
    assert result["objects_processed"] == 3
    async with db.sessions.begin() as session:
        await session.execute(text("UPDATE stage_authority SET enabled=false WHERE id=1"))
    rows = await db.rows(
        "SELECT content_tsv IS NOT NULL AS written FROM flyquery_schema_objects WHERE snapshot_id=:snapshot",
        {"snapshot": db.snapshot},
    )
    assert len(rows) == 3 and all(row["written"] for row in rows)


async def test_literal_dot_column_survives_reconcile_sample_profile_and_removal(native_database, tmp_path):
    from flyquery.core.services.ingestion.stages.profile import run_profile
    from flyquery.core.services.ingestion.stages.sample import run_sample

    db = native_database
    dotted_columns = (
        ColumnSchema("customer.name", "VARCHAR", True, 0),
        ColumnSchema("name", "VARCHAR", True, 1),
    )
    initial = await reconcile(db, columns=dotted_columns, defer_live_changes=True)
    async with db.sessions.begin() as session:
        await session.execute(
            text("UPDATE flyquery_schema_snapshots SET status='FAILED' WHERE id=:id"), {"id": db.previous}
        )
        await session.execute(
            text("UPDATE flyquery_schema_snapshots SET status='READY' WHERE id=:id"), {"id": db.snapshot}
        )
        await session.execute(
            text(
                "UPDATE flyquery_schema_objects SET description='Full customer name',description_source='HUMAN' "
                "WHERE snapshot_id=:id AND qualified_name='data.records.customer.name'"
            ),
            {"id": db.snapshot},
        )
    db.previous, db.snapshot = initial.snapshot_id, uuid4()
    unchanged = await reconcile(db, columns=dotted_columns, defer_live_changes=True)
    assert unchanged.added_columns == [] and unchanged.removed_columns == []
    assert unchanged.pending_changes.changes == ()
    assert await db.rows(
        "SELECT description FROM flyquery_schema_objects WHERE snapshot_id=:snapshot "
        "AND qualified_name='data.records.customer.name'",
        {"snapshot": db.snapshot},
    ) == [{"description": "Full customer name"}]
    parquet = tmp_path / "dotted.parquet"
    pq.write_table(pa.table({"customer.name": ["Ada", "Grace"], "name": ["North", "South"]}), parquet)
    guard = DatabaseStageGuard(db)
    await run_sample(
        tenant_id="tenant",
        snapshot_id=db.snapshot,
        parquet_key=str(parquet),
        session_factory=db.sessions,
        guard=guard,
        settings=SimpleNamespace(pii_scanner="disabled", pii_policy_samples="redact", sample_n=10),
    )
    await run_profile(
        tenant_id="tenant",
        snapshot_id=db.snapshot,
        parquet_key=str(parquet),
        n_rows_actual=2,
        session_factory=db.sessions,
        guard=guard,
        settings=SimpleNamespace(profile_row_threshold=10),
    )
    rows = {
        row["qualified_name"]: row
        for row in await db.rows(
            "SELECT qualified_name,sample_values_json,profile_json FROM flyquery_schema_objects "
            "WHERE snapshot_id=:snapshot AND kind='COLUMN'",
            {"snapshot": db.snapshot},
        )
    }
    dotted = rows["data.records.customer.name"]
    assert set(dotted["sample_values_json"]) == {"Ada", "Grace"}
    assert {item["value"] for item in dotted["profile_json"]["top_values"]} == {"Ada", "Grace"}
    db.snapshot = uuid4()
    renamed = await reconcile(
        db,
        columns=(
            ColumnSchema("customer.full_name", "VARCHAR", True, 0),
            ColumnSchema("name", "VARCHAR", True, 1),
        ),
        defer_live_changes=True,
    )
    assert renamed.added_columns == [] and renamed.removed_columns == []
    assert len(renamed.pending_changes.changes) == 1
    rename = renamed.pending_changes.changes[0]
    assert rename.change == "RENAMED"
    assert rename.before_json.column_name == "customer.name"
    assert rename.after_json.column_name == "customer.full_name"
    assert await db.rows(
        "SELECT description FROM flyquery_schema_objects WHERE snapshot_id=:snapshot "
        "AND qualified_name='data.records.customer.full_name'",
        {"snapshot": db.snapshot},
    ) == [{"description": "Full customer name"}]
    # The exact previously published column identity must survive serialization
    # and be the only removed object, despite the retained final-name sibling.
    db.snapshot = uuid4()
    removed = await reconcile(
        db, columns=(ColumnSchema("name", "VARCHAR", True, 0),), defer_live_changes=True
    )
    assert removed.removed_columns == ["customer.name"]
    async with db.sessions.begin() as session:
        await publish_reconcile_changes(session, removed.pending_changes)
    old = {
        row["qualified_name"]: row["is_active"]
        for row in await db.rows(
            "SELECT qualified_name,is_active FROM flyquery_schema_objects "
            "WHERE snapshot_id=:snapshot AND kind='COLUMN'",
            {"snapshot": db.previous},
        )
    }
    assert old == {"data.records.customer.name": False, "data.records.name": True}


@pytest.mark.parametrize("parent", ["legacy_unique", "legacy_ambiguous", "foreign_parent"])
async def test_column_identity_requires_an_unambiguous_scoped_table(native_database, parent):
    db = native_database
    async with db.sessions.begin() as session:
        identifier = uuid4()
        await session.execute(
            text(
                "UPDATE flyquery_schema_objects SET parent_id=:parent "
                "WHERE snapshot_id=:snapshot AND kind='COLUMN'"
            ),
            {"parent": identifier if parent == "foreign_parent" else None, "snapshot": db.previous},
        )
        if parent != "legacy_unique":
            session.add(
                SchemaObject(
                    id=identifier,
                    tenant_id="other" if parent == "foreign_parent" else "tenant",
                    workspace_id=db.workspace,
                    table_id=db.table,
                    snapshot_id=db.previous,
                    kind="TABLE",
                    qualified_name="data.records",
                    source_hash="e" * 64,
                )
            )
    if parent == "legacy_unique":
        result = await reconcile(db, defer_live_changes=True)
        assert result.removed_columns == ["account%"]
        assert result.pending_changes.removed_object_ids == (db.objects["account%"],)
    else:
        with pytest.raises(LineageConflict, match="unambiguous table identity"):
            await reconcile(db, defer_live_changes=True)
    assert await db.rows("SELECT id FROM flyquery_schema_changes") == []
    assert all(
        row["is_active"]
        for row in await db.rows(
            "SELECT is_active FROM flyquery_schema_objects WHERE snapshot_id=:snapshot",
            {"snapshot": db.previous},
        )
    )
