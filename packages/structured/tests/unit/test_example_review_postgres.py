# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Opt-in real PostgreSQL MVCC review races in a new private Unix-socket cluster.

No managed database, network listener, credentials, extension installation or
model service is used. pgvector publication remains covered by the separate
native repository/vector-join fixture; these cases verify actual PostgreSQL xmin.
"""

import asyncio
import getpass
import os
import shutil
import subprocess
import tempfile
from contextlib import suppress
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from flyquery.core.services.examples.examples_repository import ExamplesRepository
from flyquery.core.services.examples.examples_service import ExamplesService
from flyquery.core.services.retrieval.search_index import SearchIndex
from flyquery.interfaces.examples import ExampleCreate
from flyquery.web.conventions.context import TenantContext, set_tenant_context

pytestmark = pytest.mark.integration


@pytest.fixture(scope="session")
def owned_postgres():
    if os.environ.get("FLYQUERY_TEST_OWNED_POSTGRES") != "1":
        pytest.skip("Explicitly opt in to a new private PostgreSQL fixture")
    configured = os.environ.get("FLYQUERY_TEST_POSTGRES_BIN")
    located = shutil.which("initdb")
    binary = (
        Path(configured)
        if configured
        else Path(located).parent
        if located
        else Path("/opt/homebrew/opt/postgresql@17/bin")
    )
    if not all((binary / name).is_file() for name in ("initdb", "pg_ctl", "postgres")):
        pytest.skip("PostgreSQL server binaries are unavailable")
    with tempfile.TemporaryDirectory(prefix="koinon-review-pg-", dir="/tmp") as temporary:
        root = Path(temporary)
        socket = root / "socket"
        socket.mkdir(mode=0o700)
        data = root / "data"
        subprocess.run(
            [str(binary / "initdb"), "-D", str(data), "-A", "trust", "--no-locale", "-E", "UTF8"],
            check=True,
            capture_output=True,
            timeout=30,
        )
        options = f"-k {socket} -h '' -p 55499 -c shared_buffers=16MB -c max_connections=10 -c unix_socket_permissions=0700"
        subprocess.run(
            [
                str(binary / "pg_ctl"),
                "-D",
                str(data),
                "-l",
                str(root / "postgres.log"),
                "-o",
                options,
                "-w",
                "start",
            ],
            check=True,
            capture_output=True,
            timeout=30,
        )
        try:
            yield URL.create(
                "postgresql+psycopg",
                username=getpass.getuser(),
                database="postgres",
                query={"host": str(socket), "port": "55499"},
            )
        finally:
            subprocess.run(
                [str(binary / "pg_ctl"), "-D", str(data), "-m", "fast", "-w", "stop"],
                check=True,
                capture_output=True,
                timeout=30,
            )


class NoEmbedding:
    async def embed(self, question):
        return None


@pytest.fixture
async def postgres_review(owned_postgres):
    schema = "review_" + uuid4().hex
    engine = create_async_engine(owned_postgres, connect_args={"connect_timeout": 5})
    async with engine.begin() as connection:
        await connection.execute(text("CREATE SCHEMA " + schema))
    await engine.dispose()
    engine = create_async_engine(
        owned_postgres, connect_args={"connect_timeout": 5, "options": "-csearch_path=" + schema + ",public"}
    )
    async with engine.begin() as connection:
        await connection.execute(
            text("""CREATE TABLE flyquery_examples (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),tenant_id text,workspace_id uuid,dataset_id uuid,
          question text,generated_sql text,normalised_sql text,source text,quality text,citations_json jsonb,
          created_by text,embedding text,created_at timestamptz DEFAULT now(),last_used_at timestamptz,
          usage_count bigint DEFAULT 0)""")
        )
        await connection.execute(text("CREATE TABLE flyquery_embedding_vectors (object_id uuid)"))
    workspace, dataset = uuid4(), uuid4()
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    repository = ExamplesRepository(sessions)
    embedder = NoEmbedding()
    service = ExamplesService(repository, embedder)
    context = set_tenant_context(
        TenantContext(
            tenant_id="tenant", workspace_id=str(workspace), actor="reviewer", correlation_id="postgres-test"
        )
    )

    async def hits():
        async with sessions() as session:
            return await SearchIndex(session).approved_examples("question", None, workspace, dataset)

    try:
        yield SimpleNamespace(
            service=service,
            repository=repository,
            embedder=embedder,
            sessions=sessions,
            workspace=workspace,
            dataset=dataset,
            hits=hits,
        )
    finally:
        context.var.reset(context.token)
        await engine.dispose()


@pytest.mark.parametrize("starting_quality", ["PROPOSED", "REJECTED"])
async def test_real_postgres_later_reject_wins_even_when_quality_is_unchanged(
    postgres_review, starting_quality
):
    from pyfly.kernel import ConflictException

    fixture = postgres_review
    row = await fixture.service.create(
        "tenant",
        fixture.workspace,
        ExampleCreate(question="Review source", generated_sql="SELECT 1", dataset_id=fixture.dataset),
    )
    if starting_quality == "REJECTED":
        await fixture.service.reject(row["id"])
    started, resume = asyncio.Event(), asyncio.Event()

    async def paused(question):
        started.set()
        await resume.wait()
        return None

    fixture.embedder.embed = paused
    pending = asyncio.create_task(fixture.service.approve(row["id"]))
    try:
        await asyncio.wait_for(started.wait(), timeout=5)
        await fixture.service.reject(row["id"])
        assert (await fixture.repository.get(row["id"]))["quality"] == "REJECTED"
        resume.set()
        with pytest.raises(ConflictException) as conflict:
            await asyncio.wait_for(pending, timeout=5)
        assert conflict.value.code == "EXAMPLE_REVIEW_CONFLICT"
        assert (await fixture.repository.get(row["id"]))["quality"] == "REJECTED"
        assert await fixture.hits() == []
        async with fixture.sessions() as session:
            assert await session.scalar(text("SELECT count(*) FROM flyquery_embedding_vectors")) == 0
    finally:
        resume.set()
        if not pending.done():
            pending.cancel()
            with suppress(asyncio.CancelledError):
                await pending


async def test_real_postgres_explicit_reapproval_remains_supported(postgres_review):
    fixture = postgres_review
    row = await fixture.service.create(
        "tenant",
        fixture.workspace,
        ExampleCreate(question="Review source", generated_sql="SELECT 1", dataset_id=fixture.dataset),
    )
    await fixture.service.reject(row["id"])
    result = await fixture.service.approve(row["id"])
    assert result["quality"] == "APPROVED"
    assert [hit.id for hit in await fixture.hits()] == [row["id"]]
    assert "_review_version" not in result and "xmin" not in result


async def test_real_postgres_private_version_tracks_same_state_updates_without_public_fields(postgres_review):
    fixture = postgres_review
    row = await fixture.service.create(
        "tenant",
        fixture.workspace,
        ExampleCreate(question="Review source", generated_sql="SELECT 1", dataset_id=fixture.dataset),
    )
    await fixture.service.reject(row["id"])
    first, first_version = await fixture.repository._review_snapshot(row["id"])
    await fixture.service.reject(row["id"])
    second, second_version = await fixture.repository._review_snapshot(row["id"])
    assert first["quality"] == second["quality"] == "REJECTED"
    assert first_version != second_version
    assert first_version.isdecimal() and second_version.isdecimal()
    public = await fixture.repository.get(row["id"])
    assert "_review_version" not in public and "xmin" not in public
    assert "_review_version" not in first and "xmin" not in first
