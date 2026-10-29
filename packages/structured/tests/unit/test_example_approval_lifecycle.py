# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Real repositories, transactions and vector joins over a fixture-owned SQL protocol.

PostgreSQL scalar functions, vector scoring, planner settings and MVCC row versions
are adapted for SQLite. A fixture-only counter advances on every update; the
separate owned-PostgreSQL cases verify actual xmin behavior. Example eligibility, sidecar INSERT/UPSERT and retrieval joins are the
production SQL, including current source hashes and active-space fences.
"""

import hashlib
import json
import math
import re
from contextlib import suppress
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from flyquery.core.agents.model_bindings import EmbeddingBinding, push_bindings, reset_bindings
from flyquery.core.services.examples.examples_repository import ExamplesRepository
from flyquery.core.services.examples.examples_service import ExamplesService
from flyquery.core.services.retrieval.search_index import SearchIndex
from flyquery.interfaces.examples import ExampleCreate
from flyquery.web.conventions.context import TenantContext, set_tenant_context


class Embedder:
    model = "fixture-model"
    dimensions = 1536
    fail = False

    async def embed(self, question):
        if self.fail:
            raise RuntimeError("fixture embedding failure")
        return [1.0] + [0.0] * 1535


def distance(left, right):
    left, right = json.loads(left), json.loads(right)
    return 1 - sum(a * b for a, b in zip(left, right, strict=True)) / (
        math.sqrt(sum(a * a for a in left)) * math.sqrt(sum(b * b for b in right))
    )


@pytest.fixture
async def lifecycle(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'examples.db'}")
    controls = SimpleNamespace(fail_vector=False)

    @event.listens_for(engine.sync_engine, "connect")
    def functions(connection, record):
        connection.create_function("gen_random_uuid", 0, lambda: str(uuid4()))
        connection.create_function(
            "jsonb_build_array", -1, lambda *args: json.dumps(args, ensure_ascii=False)
        )
        connection.create_function(
            "jsonb_build_object", -1, lambda *args: json.dumps(dict(zip(args[::2], args[1::2], strict=True)))
        )
        connection.create_function("convert_to", 2, lambda value, encoding: value.encode("utf-8"))
        connection.create_function("sha256", 1, lambda value: hashlib.sha256(value).digest())
        connection.create_function("encode", 2, lambda value, encoding: value.hex())
        connection.create_function("hashtextextended", 2, lambda value, seed: 0)
        connection.create_function("pg_advisory_xact_lock_shared", 1, lambda key: None)
        connection.create_function("to_regclass", 1, lambda name: name)
        connection.create_function("cosine_distance", 2, distance)

    @event.listens_for(engine.sync_engine, "before_execute", retval=True)
    def protocol(connection, clause, multiparams, parameters, execution_options):
        sql = str(clause)
        if controls.fail_vector and "INSERT INTO flyquery_embedding_vectors" in sql:
            raise RuntimeError("fixture vector publication failure")
        if sql.startswith("SET LOCAL"):
            sql = "SELECT 1"
        sql = re.sub(r"(\w+(?:\.\w+)?)\s*<=>\s*CAST\((:\w+) AS vector\)", r"cosine_distance(\1,\2)", sql)
        sql = re.sub(r"CAST\((:\w+) AS (?:vector|jsonb)\)", r"\1", sql)
        sql = sql.replace("xmin::text", "CAST(_test_review_version AS TEXT)")
        sql = sql.replace("::text", "").replace("::uuid", "")

        def convert(values):
            return {key: str(value) if isinstance(value, UUID) else value for key, value in values.items()}

        return text(sql), [convert(values) for values in multiparams], convert(parameters)

    workspace, dataset = uuid4(), uuid4()
    async with engine.begin() as connection:
        await connection.execute(
            text("""CREATE TABLE flyquery_examples (
          id TEXT PRIMARY KEY DEFAULT (gen_random_uuid()),tenant_id TEXT,workspace_id TEXT,dataset_id TEXT,
          question TEXT,generated_sql TEXT,normalised_sql TEXT,source TEXT,quality TEXT,citations_json TEXT,
          created_by TEXT,embedding TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP,last_used_at TEXT,
          usage_count INTEGER DEFAULT 0, _test_review_version INTEGER NOT NULL DEFAULT 0)""")
        )
        await connection.execute(
            text("""CREATE TRIGGER fixture_mvcc AFTER UPDATE ON flyquery_examples
          BEGIN UPDATE flyquery_examples SET _test_review_version=OLD._test_review_version+1
          WHERE id=NEW.id; END""")
        )
        await connection.execute(
            text("""CREATE TABLE flyquery_schema_objects (
          id TEXT,tenant_id TEXT,workspace_id TEXT,is_active BOOLEAN,qualified_name TEXT,data_type TEXT,
          description TEXT,synonyms_json TEXT,profile_json TEXT,sample_values_json TEXT)""")
        )
        await connection.execute(
            text("""CREATE TABLE flyquery_embedding_sets (
          id TEXT PRIMARY KEY,tenant_id TEXT,workspace_id TEXT,status TEXT)""")
        )
        await connection.execute(
            text("""CREATE TABLE flyquery_embedding_vectors (
          set_id TEXT,kind TEXT,object_id TEXT,tenant_id TEXT,workspace_id TEXT,content_hash TEXT,
          embedding TEXT,model TEXT,text TEXT,PRIMARY KEY(set_id,kind,object_id))""")
        )
        await connection.execute(
            text("INSERT INTO flyquery_embedding_sets VALUES ('active','tenant',:workspace,'active')"),
            {"workspace": workspace},
        )
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    embedder = Embedder()
    context = set_tenant_context(
        TenantContext(
            tenant_id="tenant", workspace_id=str(workspace), actor="reviewer", correlation_id="test"
        )
    )
    binding = push_bindings(
        tenant_id="tenant",
        workspace_id=str(workspace),
        subject="reviewer",
        bindings={},
        embeddings={
            "structured.embedding": EmbeddingBinding(
                embedder, "fixture:model", 1536, 1536, "active", versioned=True
            ),
        },
    )
    repository = ExamplesRepository(sessions)
    service = ExamplesService(repository, embedder)

    async def hits():
        async with sessions() as session:
            return await SearchIndex(session).approved_examples(
                "question", [1.0] + [0.0] * 1535, workspace, dataset
            )

    try:
        yield SimpleNamespace(
            service=service,
            repository=repository,
            sessions=sessions,
            workspace=workspace,
            dataset=dataset,
            embedder=embedder,
            hits=hits,
            controls=controls,
        )
    finally:
        reset_bindings(binding)
        context.var.reset(context.token)
        await engine.dispose()


async def draft(lifecycle):
    return await lifecycle.service.create(
        "tenant",
        lifecycle.workspace,
        ExampleCreate(question="Reviewed question", generated_sql="SELECT 1", dataset_id=lifecycle.dataset),
    )


async def test_explicit_approval_publishes_into_current_version_and_rejection_excludes_retained_vector(
    lifecycle,
):
    row = await draft(lifecycle)
    assert await lifecycle.hits() == []
    async with lifecycle.sessions() as session:
        assert await session.scalar(text("SELECT count(*) FROM flyquery_embedding_vectors")) == 0
    await lifecycle.service.approve(UUID(row["id"]))
    assert [str(hit.id) for hit in await lifecycle.hits()] == [row["id"]]
    async with lifecycle.sessions() as session:
        assert await session.scalar(text("SELECT count(*) FROM flyquery_embedding_vectors")) == 1
    await lifecycle.service.reject(UUID(row["id"]))
    assert await lifecycle.hits() == []
    async with lifecycle.sessions() as session:
        assert await session.scalar(text("SELECT count(*) FROM flyquery_embedding_vectors")) == 1


async def test_embedding_failure_does_not_approve_or_publish_the_draft(lifecycle):
    row = await draft(lifecycle)
    lifecycle.embedder.fail = True
    with pytest.raises(RuntimeError, match="fixture embedding failure"):
        await lifecycle.service.approve(UUID(row["id"]))
    assert (await lifecycle.repository.get(UUID(row["id"])))["quality"] == "PROPOSED"
    assert await lifecycle.hits() == []


async def test_vector_publication_failure_rolls_back_approval(lifecycle):
    row = await draft(lifecycle)
    lifecycle.controls.fail_vector = True
    with pytest.raises(RuntimeError, match="fixture vector publication failure"):
        await lifecycle.service.approve(UUID(row["id"]))
    assert (await lifecycle.repository.get(UUID(row["id"])))["quality"] == "PROPOSED"
    assert await lifecycle.hits() == []


async def test_versioned_approval_without_an_embedder_preserves_the_draft(lifecycle):
    from pyfly.kernel import ServiceUnavailableException

    row = await draft(lifecycle)
    with pytest.raises(ServiceUnavailableException) as failure:
        await ExamplesService(lifecycle.repository, None).approve(UUID(row["id"]))
    assert failure.value.code == "INDEX_EMBEDDING_REQUIRED"
    assert (await lifecycle.repository.get(UUID(row["id"])))["quality"] == "PROPOSED"
    assert await lifecycle.hits() == []


async def test_active_space_change_during_embedding_fences_approval(lifecycle):
    from pyfly.kernel import ServiceUnavailableException

    row = await draft(lifecycle)
    original = lifecycle.embedder.embed

    async def changed_space(question):
        vector = await original(question)
        async with lifecycle.sessions.begin() as session:
            await session.execute(
                text("UPDATE flyquery_embedding_sets SET id='next-active' WHERE id='active'")
            )
        return vector

    lifecycle.embedder.embed = changed_space
    with pytest.raises(ServiceUnavailableException) as failure:
        await lifecycle.service.approve(UUID(row["id"]))
    assert failure.value.code == "INDEX_ACTIVE_CHANGED"
    assert (await lifecycle.repository.get(UUID(row["id"])))["quality"] == "PROPOSED"


async def test_source_change_during_embedding_cannot_publish_the_old_vector(lifecycle):
    from pyfly.kernel import ConflictException

    row = await draft(lifecycle)
    original = lifecycle.embedder.embed

    async def changed_source(question):
        vector = await original(question)
        async with lifecycle.sessions.begin() as session:
            await session.execute(
                text("UPDATE flyquery_examples SET question='Changed after review' WHERE id=:id"),
                {"id": row["id"]},
            )
        return vector

    lifecycle.embedder.embed = changed_source
    with pytest.raises(ConflictException) as failure:
        await lifecycle.service.approve(UUID(row["id"]))
    assert failure.value.code == "EXAMPLE_REVIEW_CONFLICT"
    assert (await lifecycle.repository.get(UUID(row["id"])))["quality"] == "PROPOSED"
    assert await lifecycle.hits() == []


@pytest.mark.parametrize("starting_quality", ["PROPOSED", "REJECTED"])
async def test_committed_rejection_fences_an_approval_waiting_for_embedding(lifecycle, starting_quality):
    import asyncio

    from pyfly.kernel import ConflictException

    row = await draft(lifecycle)
    if starting_quality == "REJECTED":
        await lifecycle.service.reject(UUID(row["id"]))
    started, resume = asyncio.Event(), asyncio.Event()
    original = lifecycle.embedder.embed

    async def paused_embedding(question):
        vector = await original(question)
        started.set()
        await resume.wait()
        return vector

    lifecycle.embedder.embed = paused_embedding
    pending = asyncio.create_task(lifecycle.service.approve(UUID(row["id"])))
    try:
        await asyncio.wait_for(started.wait(), timeout=2)
        rejected = await lifecycle.service.reject(UUID(row["id"]))
        assert rejected["quality"] == "REJECTED"
        assert (await lifecycle.repository.get(UUID(row["id"])))["quality"] == "REJECTED"
        resume.set()
        with pytest.raises(ConflictException) as conflict:
            await asyncio.wait_for(pending, timeout=2)
        assert conflict.value.code == "EXAMPLE_REVIEW_CONFLICT"
        assert (await lifecycle.repository.get(UUID(row["id"])))["quality"] == "REJECTED"
        async with lifecycle.sessions() as session:
            assert await session.scalar(text("SELECT count(*) FROM flyquery_embedding_vectors")) == 0
        assert await lifecycle.hits() == []
    finally:
        resume.set()
        if not pending.done():
            pending.cancel()
            with suppress(asyncio.CancelledError):
                await pending


async def test_explicit_fresh_reapproval_of_a_rejected_example_is_supported(lifecycle):
    row = await draft(lifecycle)
    await lifecycle.service.reject(UUID(row["id"]))
    approved = await lifecycle.service.approve(UUID(row["id"]))
    assert approved["quality"] == "APPROVED"
    assert [str(hit.id) for hit in await lifecycle.hits()] == [row["id"]]
    assert "_review_version" not in approved and "xmin" not in approved
