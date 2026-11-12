# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Real primary units, publisher capabilities and atomic answer proof commits."""

from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest
from psycopg import sql
from pyfly.data.relational.sqlalchemy.transaction_manager import SqlAlchemyTransactionManager
from pyfly.data.transaction import TransactionManagerRegistry, current_unit_of_work
from pyfly.data.transaction.registry import bind_registry
from sqlalchemy import update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from test_release_proof_postgres import proof_database as proof_database
from test_release_proof_postgres import seed

from koinon.answers.configuration import AnswerProofProcess, verify_process_role
from koinon.answers.release_proof_repository import AnswerReleaseProofRepository
from koinon.answers.release_proofs import (
    AnswerReleaseProofPublisher,
    PublicationRejected,
    current_publication,
    verify_persisted_release,
)
from koinon.assistants.entities import ChatMessage, ToolResult
from koinon.assistants.repositories import ChatRunRepository
from koinon.assistants.run_sources import run_source_unit

pytestmark = pytest.mark.integration


@asynccontextmanager
async def worker(db):
    import psycopg

    with psycopg.connect(str(db.url)) as admin:
        for table in (
            "koinon_agents",
            "koinon_providers",
            "koinon_content_imported_assets",
            "koinon_chat_memory_manifests",
        ):
            admin.execute(
                sql.SQL("GRANT SELECT ON TABLE public.{} TO {}").format(
                    sql.Identifier(table),
                    sql.Identifier(db.roles["publisher"]),
                )
            )
    engine = create_async_engine(db.url.set(drivername="postgresql+asyncpg", username=db.roles["publisher"]))
    registry = TransactionManagerRegistry()
    registry.register(
        SqlAlchemyTransactionManager(
            sessionmaker=async_sessionmaker(engine, expire_on_commit=False), name="primary"
        )
    )
    try:
        with bind_registry(registry):
            assistants = SimpleNamespace(runs=ChatRunRepository(), source_reader=None)
            yield assistants, AnswerReleaseProofPublisher(AnswerReleaseProofRepository())
    finally:
        await engine.dispose()


@pytest.mark.parametrize("abort", [False, True])
async def test_native_only_publication_commits_or_rolls_back_with_answer(proof_database, abort):
    import psycopg

    db = proof_database
    case = seed(db)
    with psycopg.connect(str(db.url)) as connection:
        original = connection.execute(
            "SELECT text FROM koinon_chat_messages WHERE id=%s", (case.ids["message"],)
        ).fetchone()[0]
        connection.execute("UPDATE koinon_chat_messages SET text='' WHERE id=%s", (case.ids["message"],))
    release_id = None
    async with worker(db) as (assistants, publisher):
        try:
            async with run_source_unit(
                assistants,
                case.ids["run"],
                "worker",
                write=True,
                purpose="release_answer",
                publish_proof=True,
            ):
                admission = current_publication()
                release_id = admission.release_id
                session = current_unit_of_work("primary").resource
                await session.execute(
                    update(ChatMessage).where(ChatMessage.id == case.ids["message"]).values(text=original)
                )
                session.add(
                    ToolResult(
                        id=release_id, run_id=case.ids["run"], kind="answer_release", payload=case.release
                    )
                )
                identity = await publisher.publish_verified_release(admission, release_id)
                assert identity.header.release_result_id == release_id
                with pytest.raises(PublicationRejected):
                    await publisher.publish_verified_release(admission, release_id)
                if abort:
                    raise RuntimeError("controlled crash before commit")
        except RuntimeError:
            if not abort:
                raise
    with psycopg.connect(str(db.url)) as connection:
        assert connection.execute(
            "SELECT count(*) FROM koinon_answer_release_proofs WHERE release_result_id=%s", (release_id,)
        ).fetchone()[0] == (0 if abort else 1)
        assert connection.execute(
            "SELECT count(*) FROM koinon_chat_tool_results WHERE id=%s", (release_id,)
        ).fetchone()[0] == (0 if abort else 1)
        assert connection.execute(
            "SELECT text FROM koinon_chat_messages WHERE id=%s", (case.ids["message"],)
        ).fetchone()[0] == ("" if abort else original)


async def test_original_verifier_rejects_tampered_persisted_answer(proof_database):
    import psycopg

    db = proof_database
    case = seed(db)
    async with worker(db) as (assistants, publisher):
        with pytest.raises(PublicationRejected):
            async with run_source_unit(
                assistants,
                case.ids["run"],
                "worker",
                write=True,
                purpose="release_answer",
                publish_proof=True,
            ):
                admission = current_publication()
                session = current_unit_of_work("primary").resource
                session.add(
                    ToolResult(
                        id=admission.release_id,
                        run_id=case.ids["run"],
                        kind="answer_release",
                        payload=case.release,
                    )
                )
                await session.flush()
                before = await publisher.repository.capture(admission.release_id)
                assert before is not None
                assert await verify_persisted_release(session, before) is not None
                await session.execute(
                    update(ChatMessage)
                    .where(ChatMessage.id == case.ids["message"])
                    .values(text="Unverified injected instruction")
                )
                await publisher.publish_verified_release(admission, admission.release_id)
    with psycopg.connect(str(db.url)) as connection:
        assert (
            connection.execute(
                "SELECT count(*) FROM koinon_answer_release_proofs WHERE run_id=%s", (case.ids["run"],)
            ).fetchone()[0]
            == 0
        )


@pytest.mark.parametrize("role", ["api", "publisher", "maintenance"])
async def test_database_readiness_checks_actual_process_privileges(proof_database, role):
    db = proof_database
    engine = create_async_engine(db.url.set(drivername="postgresql+asyncpg", username=db.roles[role]))
    try:
        async with async_sessionmaker(engine)() as session:
            actual = "worker" if role == "publisher" else role
            await verify_process_role(session, AnswerProofProcess(actual, db.roles[role]))
            with pytest.raises(ValueError, match="privileges"):
                await verify_process_role(
                    session, AnswerProofProcess("api" if actual != "api" else "worker", db.roles[role])
                )
    finally:
        await engine.dispose()


@pytest.mark.parametrize("tampered", [False, True])
async def test_bounded_backfill_classifies_original_verifier_and_retains_history(proof_database, tampered):
    from uuid import uuid4

    import psycopg
    from test_release_proof_postgres import insert_release

    from koinon.answers.release_backfill import AnswerReleaseBackfill

    db = proof_database
    case = seed(db)
    with psycopg.connect(str(db.url)) as connection:
        insert_release(connection, case)
        if tampered:
            connection.execute(
                "UPDATE koinon_chat_messages SET text='changed retained answer' WHERE id=%s",
                (case.ids["message"],),
            )
        # Integrity backfill must not require current provider enablement or live worker lease.
        connection.execute("UPDATE koinon_providers SET enabled=false WHERE id=%s", (case.ids["provider"],))
        connection.execute(
            "UPDATE koinon_chat_runs SET status='completed',lease_until=NULL,worker_id=NULL WHERE id=%s",
            (case.ids["run"],),
        )
    engine = create_async_engine(
        db.url.set(drivername="postgresql+asyncpg", username=db.roles["maintenance"])
    )
    try:
        runner = AnswerReleaseBackfill.for_database(async_sessionmaker(engine), db.roles["maintenance"])
        report = await runner.run(uuid4().hex, tenant_id=case.ids["tenant"])
        assert report.state == "complete" and report.processed == 1
        assert report.invalid == int(tampered) and report.projected == int(not tampered)
    finally:
        await engine.dispose()
    with psycopg.connect(str(db.url)) as connection:
        assert (
            connection.execute(
                "SELECT count(*) FROM koinon_chat_tool_results WHERE id=%s", (case.ids["release"],)
            ).fetchone()[0]
            == 1
        )
        assert connection.execute(
            "SELECT count(*) FROM koinon_answer_release_proofs WHERE release_result_id=%s",
            (case.ids["release"],),
        ).fetchone()[0] == int(not tampered)


async def test_backfill_lock_timeout_keeps_cursor_and_retries_after_rollback(proof_database):
    from uuid import uuid4

    import psycopg
    from test_release_proof_postgres import insert_release

    from koinon.answers.release_backfill import AnswerReleaseBackfill

    db = proof_database
    case = seed(db)
    with psycopg.connect(str(db.url)) as connection:
        insert_release(connection, case)
    job = uuid4().hex
    engine = create_async_engine(
        db.url.set(drivername="postgresql+asyncpg", username=db.roles["maintenance"])
    )
    holder = psycopg.connect(str(db.url))
    try:
        holder.execute("SELECT id FROM koinon_chat_runs WHERE id=%s FOR UPDATE", (case.ids["run"],))
        runner = AnswerReleaseBackfill.for_database(async_sessionmaker(engine), db.roles["maintenance"])
        blocked = await runner.run(job, tenant_id=case.ids["tenant"])
        assert blocked.state == "blocked" and blocked.blocked == 1
        with psycopg.connect(str(db.url)) as connection:
            assert (
                connection.execute(
                    "SELECT cursor_release_id FROM koinon_answer_release_projection_jobs WHERE job_id=%s",
                    (job,),
                ).fetchone()[0]
                is None
            )
        holder.rollback()
        done = await runner.run(job, tenant_id=case.ids["tenant"])
        assert done.state == "complete" and done.projected == 1
    finally:
        holder.rollback()
        holder.close()
        await engine.dispose()


@pytest.mark.parametrize("change", ["attempt", "worker", "lease", "generation", "reset"])
async def test_publication_rechecks_live_worker_and_selector(proof_database, change):
    from datetime import UTC, datetime, timedelta
    from uuid import uuid4

    from pyfly.kernel import ConflictException

    from koinon.assistants.entities import ChatEvent, ChatRun

    db = proof_database
    case = seed(db)
    async with worker(db) as (assistants, publisher):
        with pytest.raises(ConflictException):
            async with run_source_unit(
                assistants,
                case.ids["run"],
                "worker",
                write=True,
                purpose="release_answer",
                publish_proof=True,
            ):
                admission = current_publication()
                session = current_unit_of_work("primary").resource
                session.add(
                    ToolResult(
                        id=admission.release_id,
                        run_id=case.ids["run"],
                        kind="answer_release",
                        payload=case.release,
                    )
                )
                if change in {"attempt", "worker", "lease"}:
                    changes = {
                        "attempt": {"attempts": 2},
                        "worker": {"worker_id": "other-worker"},
                        "lease": {"lease_until": datetime.now(UTC) - timedelta(seconds=1)},
                    }
                    await session.execute(
                        update(ChatRun).where(ChatRun.id == case.ids["run"]).values(**changes[change])
                    )
                elif change == "generation":
                    session.add(
                        ToolResult(
                            id=uuid4().hex,
                            run_id=case.ids["run"],
                            kind="generation",
                            payload={"generation": {"start_sequence": 2}},
                        )
                    )
                else:
                    session.add(
                        ChatEvent(
                            id=uuid4().hex, run_id=case.ids["run"], sequence=1, type="message_reset", data={}
                        )
                    )
                await publisher.publish_verified_release(admission, admission.release_id)


@pytest.fixture
def provisioned_processes(proof_database, tmp_path, monkeypatch):
    """Use fresh generated credentials and the production role provisioner, never extra grants."""
    from uuid import uuid4

    import psycopg
    from sqlalchemy.engine import make_url
    from test_release_proof_postgres import load

    db = proof_database
    generated = load("deploy/generate_local_configuration.py").generate(tmp_path / "private-processes")
    environment = dict(line.split("=", 1) for line in (generated / "migration.env").read_text().splitlines())
    suffix = uuid4().hex[:10]
    urls = {}
    for key, value in environment.items():
        if key == "KOINON_MIGRATION_DATABASE_URL":
            continue
        parsed = make_url(value)
        url = parsed.set(
            username=parsed.username + "_" + suffix,
            host=db.url.host,
            port=db.url.port,
            database=db.url.database,
        )
        urls[key] = url
        monkeypatch.setenv(key, url.render_as_string(hide_password=False))
    monkeypatch.setenv("KOINON_MIGRATION_DATABASE_URL", db.url.render_as_string(hide_password=False))
    try:
        db.provisioner.provision(grants=True)
        yield urls
    finally:
        # Revoke only this fixture's UUID-suffixed identities inside its owned disposable database.
        with psycopg.connect(str(db.url), autocommit=True) as admin:
            for url in urls.values():
                exists = admin.execute(
                    "SELECT EXISTS(SELECT FROM pg_roles WHERE rolname=%s)", (url.username,)
                ).fetchone()[0]
                if exists:
                    admin.execute(sql.SQL("DROP OWNED BY {}").format(sql.Identifier(url.username)))
                    admin.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(url.username)))


@pytest.mark.parametrize("parent", ["run", "generation"])
def test_generated_roles_serialize_memory_inserts_on_parent_and_deny_mutation(
    proof_database, provisioned_processes, parent
):
    from uuid import uuid4

    import psycopg
    from psycopg.types.json import Json

    db = proof_database
    case = seed(db)
    worker_url = provisioned_processes["KOINON_ANSWER_PUBLISHER_DATABASE_URL"].set(drivername="postgresql")
    values = (
        uuid4().hex,
        case.ids["generation"],
        case.ids["run"],
        case.ids["tenant"],
        "issuer|owner",
        case.ids["thread"],
        "a" * 64,
        Json({}),
        "b" * 64,
    )
    insert = (
        "INSERT INTO koinon_chat_memory_manifests(id,generation_id,run_id,tenant_id,subject,"
        "thread_id,policy_version,start_sequence,scope_sha256,manifest_json,manifest_sha256,created_at) "
        "VALUES(%s,%s,%s,%s,%s,%s,1,1,%s,%s,%s,clock_timestamp())"
    )
    with (
        psycopg.connect(worker_url.render_as_string(hide_password=False)) as holder,
        psycopg.connect(worker_url.render_as_string(hide_password=False)) as contender,
    ):
        table = "koinon_chat_runs" if parent == "run" else "koinon_chat_tool_results"
        holder.execute(
            sql.SQL("SELECT id FROM public.{} WHERE id=%s FOR UPDATE").format(sql.Identifier(table)),
            (case.ids[parent],),
        )
        with pytest.raises(psycopg.errors.LockNotAvailable), contender.transaction():
            contender.execute("SET LOCAL lock_timeout='150ms'")
            contender.execute(insert, values)
        holder.rollback()
        with contender.transaction():
            contender.execute(insert, values)
        assert contender.execute(
            "SELECT run_id,generation_id FROM koinon_chat_memory_manifests WHERE id=%s", (values[0],)
        ).fetchone() == (case.ids["run"], case.ids["generation"])
        contender.commit()
        for statement in (
            "UPDATE koinon_chat_memory_manifests SET manifest_json='{}' WHERE id=%s",
            "UPDATE koinon_chat_memory_manifests SET run_id=run_id,generation_id=generation_id WHERE id=%s",
            "DELETE FROM koinon_chat_memory_manifests WHERE id=%s",
        ):
            with pytest.raises(psycopg.errors.InsufficientPrivilege), contender.transaction():
                contender.execute(statement, (values[0],))


async def test_audit_blocks_valid_missing_proof_and_never_writes_one(proof_database):
    from uuid import uuid4

    import psycopg
    from test_release_proof_postgres import insert_release

    from koinon.answers.release_backfill import AnswerReleaseBackfill

    db = proof_database
    case = seed(db)
    with psycopg.connect(str(db.url)) as connection:
        insert_release(connection, case)
    engine = create_async_engine(
        db.url.set(drivername="postgresql+asyncpg", username=db.roles["maintenance"])
    )
    try:
        sessions = async_sessionmaker(engine)
        auditor = AnswerReleaseBackfill.for_database(sessions, db.roles["maintenance"], audit=True)
        audit_job = uuid4().hex
        missing = await auditor.run(audit_job, tenant_id=case.ids["tenant"])
        assert missing.state == "blocked" and missing.projected == 0
        assert missing.classifications[0]["classification"] == "valid_release_missing_current_proof"
        with psycopg.connect(str(db.url)) as connection:
            assert (
                connection.execute(
                    "SELECT count(*) FROM koinon_answer_release_proofs WHERE release_result_id=%s",
                    (case.ids["release"],),
                ).fetchone()[0]
                == 0
            )
        backfill = AnswerReleaseBackfill.for_database(sessions, db.roles["maintenance"])
        assert (await backfill.run(uuid4().hex, tenant_id=case.ids["tenant"])).projected == 1
        done = await auditor.run(audit_job, tenant_id=case.ids["tenant"])
        assert done.state == "complete" and done.projected == 0 and done.processed == 1
        assert done.classifications[0]["classification"] == "verified"
        assert done.rollout_unprojected == ()
    finally:
        await engine.dispose()


async def test_coverage_tail_finds_unprojected_arrival_after_empty_high_water(proof_database):
    from uuid import uuid4

    import psycopg
    from test_release_proof_postgres import insert_release

    from koinon.answers.release_backfill import AnswerReleaseBackfill

    db = proof_database
    case = seed(db)
    engine = create_async_engine(
        db.url.set(drivername="postgresql+asyncpg", username=db.roles["maintenance"])
    )
    try:
        auditor = AnswerReleaseBackfill.for_database(
            async_sessionmaker(engine), db.roles["maintenance"], audit=True
        )
        async with auditor.unit_factory() as unit:
            claim = await unit.acquire(uuid4().hex, case.ids["tenant"])
            assert claim.state == "complete"
        with psycopg.connect(str(db.url)) as connection:
            insert_release(connection, case)
        async with auditor.unit_factory() as unit:
            tail, more = await unit.rollout_tail(claim)
        assert tail == (case.ids["release"],) and more is False
    finally:
        await engine.dispose()


async def test_coverage_detects_older_release_committed_after_audit_high_water(proof_database):
    from uuid import uuid4

    import psycopg
    from test_release_proof_postgres import insert_release

    from koinon.answers.release_backfill import AnswerReleaseBackfill

    db = proof_database
    earlier, later = seed(db), seed(db)
    assert earlier.now < later.now
    engine = create_async_engine(
        db.url.set(drivername="postgresql+asyncpg", username=db.roles["maintenance"])
    )
    try:
        sessions = async_sessionmaker(engine)
        auditor = AnswerReleaseBackfill.for_database(sessions, db.roles["maintenance"], audit=True)
        with psycopg.connect(
            str(db.url), options="-c statement_timeout=5000 -c lock_timeout=1000"
        ) as pending:
            insert_release(pending, earlier)
            with psycopg.connect(
                str(db.url), options="-c statement_timeout=5000 -c lock_timeout=1000"
            ) as committed:
                insert_release(committed, later)
            backfill = AnswerReleaseBackfill.for_database(sessions, db.roles["maintenance"])
            assert (await backfill.run(uuid4().hex)).projected == 1
            job_id = uuid4().hex
            assert (await auditor.run(job_id)).state == "complete"
            pending.commit()
        async with auditor.unit_factory() as unit:
            missing, more = await unit.rollout_tail(SimpleNamespace(job_id=job_id))
        assert missing == (earlier.ids["release"],)
        assert more is False
    finally:
        await engine.dispose()


async def test_completed_audit_resumes_coverage_after_budget_exhaustion(proof_database):
    from uuid import uuid4

    import psycopg
    from sqlalchemy.exc import DBAPIError
    from test_release_proof_postgres import insert_release

    from koinon.answers.release_backfill import AnswerReleaseBackfill

    db = proof_database
    case = seed(db)
    with psycopg.connect(str(db.url)) as connection:
        insert_release(connection, case)
    engine = create_async_engine(
        db.url.set(drivername="postgresql+asyncpg", username=db.roles["maintenance"])
    )
    try:
        sessions = async_sessionmaker(engine)
        backfill = AnswerReleaseBackfill.for_database(sessions, db.roles["maintenance"])
        assert (await backfill.run(uuid4().hex, tenant_id=case.ids["tenant"])).projected == 1
        auditor = AnswerReleaseBackfill.for_database(sessions, db.roles["maintenance"], audit=True)
        ticks = iter((0.0, 0.1, 5.0, 5.0))
        bounded = AnswerReleaseBackfill(auditor.unit_factory, audit=True, clock=lambda: next(ticks))
        job_id = uuid4().hex
        pending = await bounded.run(job_id, tenant_id=case.ids["tenant"])
        assert pending.state == "coverage_pending" and pending.processed == 1
        with psycopg.connect(str(db.url)) as connection:
            revision = connection.execute(
                "SELECT revision FROM koinon_answer_release_projection_jobs WHERE job_id=%s",
                (job_id,),
            ).fetchone()[0]
        resumed = await auditor.run(job_id, tenant_id=case.ids["tenant"])
        assert resumed.state == "complete" and resumed.processed == 0
        assert resumed.rollout_unprojected == ()
        async with auditor.unit_factory() as unit:
            marker = await unit.acquire(job_id, case.ids["tenant"])
            assert not any(hasattr(marker, field) for field in ("claim_token", "revision", "claim_until"))
        with pytest.raises(DBAPIError, match="job scope conflict"):
            await auditor.run(job_id, tenant_id="other-tenant")
        with psycopg.connect(str(db.url)) as connection:
            assert connection.execute(
                "SELECT revision FROM koinon_answer_release_projection_jobs WHERE job_id=%s",
                (job_id,),
            ).fetchone()[0] == revision
    finally:
        await engine.dispose()


@pytest.mark.parametrize("abort", [False, True])
async def test_generated_worker_publishes_without_extra_database_grants(
    proof_database, provisioned_processes, abort
):
    from contextlib import nullcontext

    import psycopg
    from pyfly.context import ApplicationContext
    from pyfly.core import Config

    from koinon.answers.configuration import register_release_proofs

    db = proof_database
    case = seed(db)
    with psycopg.connect(str(db.url)) as admin:
        admin.execute("UPDATE koinon_chat_messages SET text='' WHERE id=%s", (case.ids["message"],))
    worker_url = provisioned_processes["KOINON_ANSWER_PUBLISHER_DATABASE_URL"]
    api_url = provisioned_processes["KOINON_DATABASE_URL"]
    values = {
        "pyfly": {
            "banner": {"mode": "off"},
            "data": {
                "relational": {
                    "enabled": True,
                    "ddl-auto": "none",
                    "url": worker_url.render_as_string(hide_password=False),
                }
            },
        },
        "koinon": {
            "process": {"role": "worker"},
            "answers": {
                "release_proofs": {
                    "enabled": True,
                    "api_role": api_url.username,
                    "publisher_role": worker_url.username,
                }
            },
        },
    }
    context = ApplicationContext(Config(values))
    register_release_proofs(context, values)
    context.register_bean(ChatRunRepository)
    release_id = None
    try:
        await context.start()
        assistants = SimpleNamespace(runs=context.get_bean(ChatRunRepository), source_reader=None)
        publisher = context.get_bean(AnswerReleaseProofPublisher)
        with pytest.raises(RuntimeError, match="controlled precommit crash") if abort else nullcontext():
            async with run_source_unit(
                assistants,
                case.ids["run"],
                "worker",
                write=True,
                purpose="release_answer",
                publish_proof=True,
            ):
                admission = current_publication()
                release_id = admission.release_id
                session = current_unit_of_work("primary").resource
                await session.execute(
                    update(ChatMessage).where(ChatMessage.id == case.ids["message"]).values(text="Answer")
                )
                session.add(
                    ToolResult(
                        id=release_id, run_id=case.ids["run"], kind="answer_release", payload=case.release
                    )
                )
                identity = await publisher.publish_verified_release(admission, release_id)
                assert identity.header.run_id == case.ids["run"]
                if abort:
                    raise RuntimeError("controlled precommit crash")
        assert not admission.active
    finally:
        await context.stop()
    with psycopg.connect(str(db.url)) as admin:
        assert admin.execute(
            "SELECT count(*) FROM koinon_answer_release_proofs WHERE release_result_id=%s", (release_id,)
        ).fetchone()[0] == int(not abort)
        assert admin.execute(
            "SELECT count(*) FROM koinon_chat_tool_results WHERE id=%s", (release_id,)
        ).fetchone()[0] == int(not abort)
        assert admin.execute(
            "SELECT text FROM koinon_chat_messages WHERE id=%s", (case.ids["message"],)
        ).fetchone()[0] == ("" if abort else "Answer")


@pytest.mark.parametrize("process", ["KOINON_DATABASE_URL", "KOINON_ANSWER_MAINTENANCE_DATABASE_URL"])
def test_generated_api_and_maintenance_roles_cannot_publish_or_switch_to_worker(
    provisioned_processes, process
):
    import psycopg

    target = provisioned_processes[process].set(drivername="postgresql")
    worker_role = provisioned_processes["KOINON_ANSWER_PUBLISHER_DATABASE_URL"].username
    with psycopg.connect(target.render_as_string(hide_password=False)) as connection:
        with pytest.raises(psycopg.errors.InsufficientPrivilege), connection.transaction():
            connection.execute(
                "SELECT public.koinon_publish_release_proof(%s,%s,%s,%s)",
                ("untrusted-release", "a" * 64, "worker", 1),
            )
        with pytest.raises(psycopg.errors.InsufficientPrivilege), connection.transaction():
            connection.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(worker_role)))


async def test_backfill_hydrates_only_original_verifier_message_columns(proof_database):
    from uuid import uuid4

    import psycopg
    from sqlalchemy import select
    from sqlalchemy.exc import ProgrammingError
    from test_release_proof_postgres import insert_release

    from koinon.answers.release_backfill import AnswerReleaseBackfill

    db = proof_database
    case = seed(db)
    role = db.roles["maintenance"]
    with psycopg.connect(str(db.url)) as admin:
        insert_release(admin, case)
        admin.execute(
            sql.SQL("REVOKE SELECT ON public.koinon_chat_messages FROM {}").format(sql.Identifier(role))
        )
        admin.execute(
            sql.SQL(
                "GRANT SELECT(id,thread_id,role,text,citations,artifacts,answer_policy) "
                "ON public.koinon_chat_messages TO {}"
            ).format(sql.Identifier(role))
        )
    engine = create_async_engine(db.url.set(drivername="postgresql+asyncpg", username=role))
    try:
        sessions = async_sessionmaker(engine)
        async with sessions() as session:
            with pytest.raises(ProgrammingError, match="permission denied"):
                # The previous unbounded ORM load is genuinely denied by this role.
                await session.scalar(select(ChatMessage).where(ChatMessage.id == case.ids["message"]))
        runner = AnswerReleaseBackfill.for_database(sessions, role)
        report = await runner.run(uuid4().hex, tenant_id=case.ids["tenant"])
        assert report.state == "complete" and report.projected == 1
    finally:
        await engine.dispose()
        with psycopg.connect(str(db.url)) as admin:
            admin.execute(
                sql.SQL("GRANT SELECT ON public.koinon_chat_messages TO {}").format(sql.Identifier(role))
            )
