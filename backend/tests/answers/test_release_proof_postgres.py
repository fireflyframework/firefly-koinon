# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Real migrated PostgreSQL proof and role boundaries on an owned disposable DB."""

import importlib.util
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import psycopg
import pytest
import sqlalchemy as sa
from alembic import command
from psycopg import sql
from psycopg.types.json import Json, Jsonb
from sqlalchemy.engine import make_url

from koinon.answers.contexts import context_hash
from koinon.answers.receipts import AnswerRelease, digest, text_digest, verified_release
from koinon.answers.release_proof_dtos import ReleaseProofCapture, ReleaseProofIdentity
from koinon.assistants.entities import (
    AgentConfiguration,
    ChatMessage,
    ChatRun,
    ChatThread,
    Provider,
    ToolResult,
)
from koinon.catalog.entities import Tenant

pytestmark = pytest.mark.integration
ROOT = Path(__file__).resolve().parents[3]


def load(path):
    spec = importlib.util.spec_from_file_location(Path(path).stem, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def proof_database():
    uri = os.environ.get("KOINON_ANSWER_PROOF_TEST_PG_URL")
    if not uri:
        pytest.skip("Requires an explicitly owned proof PostgreSQL fixture")
    base = make_url(uri)
    assert base.host == "127.0.0.1" and base.port == 55439
    suffix = uuid4().hex[:12]
    database = "release_proof_" + suffix
    roles = {kind: "proof_" + kind + "_" + suffix for kind in ("api", "publisher", "maintenance")}
    target = base.set(database=database)
    engine = sa.create_engine(target.set(drivername="postgresql+psycopg"))
    with psycopg.connect(uri, autocommit=True) as admin:
        admin.execute(
            sql.SQL("CREATE DATABASE {} TEMPLATE template0 ENCODING 'UTF8'").format(sql.Identifier(database))
        )
        for role in roles.values():
            admin.execute(
                sql.SQL(
                    "CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS"
                ).format(sql.Identifier(role))
            )
    try:
        with engine.connect() as connection:
            config = load("deploy/migrate.py").history_config(
                "native", ROOT / "deploy/migrations/native_versions", connection
            )
            command.upgrade(config, "koinon_0057_proof_indexes")
            connection.commit()
        provisioner = load("deploy/provision_roles.py")
        with psycopg.connect(str(target)) as admin:
            for kind, role in roles.items():
                provisioner.grant_release_proof_role(admin, role, kind=kind)
                if kind != "maintenance":
                    for table in (
                        "koinon_chat_threads",
                        "koinon_chat_runs",
                        "koinon_chat_messages",
                        "koinon_chat_tool_results",
                        "koinon_chat_events",
                    ):
                        provisioner.grant_table(admin, table, role)
        yield SimpleNamespace(url=target, engine=engine, roles=roles, provisioner=provisioner)
    finally:
        engine.dispose()
        # Only this invocation's UUID-named disposable objects are removed.
        with psycopg.connect(uri, autocommit=True) as admin:
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(database)))
            for role in roles.values():
                admin.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(role)))


def seed(db, *, value=10.0, sources=True):
    suffix = uuid4().hex[:12]
    ids = {
        name: name + "_" + suffix
        for name in (
            "tenant",
            "provider",
            "agent",
            "thread",
            "user",
            "message",
            "run",
            "generation",
            "pin",
            "release",
        )
    }
    now = datetime.now(UTC)
    refs = [
        dict(
            id="source-" + letter,
            kind="document",
            asset_id="asset-" + letter,
            title="Protected title " + letter,
            source_version_id="version-" + letter,
            extraction_id="extract-" + letter,
            source_part_id="part-" + letter,
            source_part_sha256=letter * 64,
            used_revision="source-part-sha256:" + letter * 64,
            page_basis="recorded_loader",
            recorded_page=1,
        )
        for letter in ("a", "b")
    ]
    payload = {
        "generation_id": ids["generation"],
        "number": value,
        "asset_ids": [ref["asset_id"] for ref in refs],
        "source_manifest": {"version": 1, "complete": True, "sources": refs},
    }
    artifacts = [{"id": ids["pin"], "run_id": ids["run"]}]
    with db.engine.begin() as c:
        c.execute(Tenant.__table__.insert().values(id=ids["tenant"], name="Proof test"))
        c.execute(
            Provider.__table__.insert().values(
                id=ids["provider"],
                tenant_id=ids["tenant"],
                name="Test",
                kind="openai",
                base_url="http://invalid.test",
            )
        )
        c.execute(
            AgentConfiguration.__table__.insert().values(
                id=ids["agent"],
                tenant_id=ids["tenant"],
                provider_id=ids["provider"],
                name="Test",
                model_id="test",
            )
        )
        c.execute(
            ChatThread.__table__.insert().values(
                id=ids["thread"], tenant_id=ids["tenant"], subject="issuer|owner", title="Test"
            )
        )
        c.execute(
            ChatMessage.__table__.insert().values(
                id=ids["user"], thread_id=ids["thread"], role="user", text="Question"
            )
        )
        c.execute(
            ChatMessage.__table__.insert().values(
                id=ids["message"],
                thread_id=ids["thread"],
                role="assistant",
                text="Answer",
                artifacts=artifacts,
            )
        )
        c.execute(
            ChatRun.__table__.insert().values(
                id=ids["run"],
                tenant_id=ids["tenant"],
                thread_id=ids["thread"],
                message_id=ids["message"],
                user_message_id=ids["user"],
                agent_id=ids["agent"],
                agent_revision=1,
                provider_revision=1,
                client_request_id=suffix,
                payload_hash="0" * 64,
                status="running",
                worker_id="worker",
                attempts=1,
                lease_until=now + timedelta(minutes=10),
            )
        )
        c.execute(
            ToolResult.__table__.insert().values(
                id=ids["generation"],
                run_id=ids["run"],
                kind="generation",
                payload={"generation": {"start_sequence": 1}},
                created_at=now,
            )
        )
        c.execute(
            ToolResult.__table__.insert().values(
                id=ids["pin"], run_id=ids["run"], kind="search", payload=payload
            )
        )
    receipt = AnswerRelease(
        run_id=ids["run"],
        message_id=ids["message"],
        tenant_id=ids["tenant"],
        generation_id=ids["generation"],
        publication_sequence=2,
        outcome="grounded",
        text_sha256=text_digest("Answer"),
        citations_sha256=digest([]),
        artifacts_sha256=digest(artifacts),
        policy_sha256=digest({}),
        fact_ids=("fact",),
        result_pins=({"id": ids["pin"], "sha256": digest({"kind": "search", "payload": payload})},),
        source_refs=refs[:1] if sources else (),
        created_at=now,
    )
    seal = digest(receipt.model_dump(mode="json"))
    release = {
        "release": receipt.model_dump(mode="json"),
        "seal_sha256": seal,
        "generation_id": ids["generation"],
        "reset_sequence": 0,
        "context_sha256": context_hash(seal, 0),
    }
    return SimpleNamespace(ids=ids, release=release, payload=payload, artifacts=artifacts, now=now)


def insert_release(connection, case):
    connection.execute(
        "INSERT INTO koinon_chat_tool_results(id,run_id,kind,payload,created_at) "
        "VALUES(%s,%s,'answer_release',%s,%s)",
        (case.ids["release"], case.ids["run"], Json(case.release), case.now),
    )


def capture(connection, case):
    value = connection.execute(
        "SELECT public.koinon_capture_release_proof(%s)", (case.ids["release"],)
    ).fetchone()[0]
    return ReleaseProofCapture.model_validate(value)


def publish(db, case):
    with psycopg.connect(str(db.url.set(username=db.roles["publisher"]))) as worker:
        insert_release(worker, case)
        # The unchanged verifier is executed over authoritative persisted rows.
        message = worker.execute(
            "SELECT text,citations,artifacts,answer_policy FROM koinon_chat_messages WHERE id=%s",
            (case.ids["message"],),
        ).fetchone()
        rows = worker.execute(
            "SELECT id,run_id,kind,payload,created_at FROM koinon_chat_tool_results WHERE run_id=%s",
            (case.ids["run"],),
        ).fetchall()
        assert (
            verified_release(
                SimpleNamespace(
                    id=case.ids["message"],
                    text=message[0],
                    citations=message[1],
                    artifacts=message[2],
                    answer_policy=message[3],
                ),
                [
                    SimpleNamespace(id=r[0], run_id=r[1], kind=r[2], payload=r[3], created_at=r[4])
                    for r in rows
                ],
            )
            is not None
        )
        state = capture(worker, case)
        result = worker.execute(
            "SELECT public.koinon_publish_release_proof(%s,%s,'worker',1)",
            (case.ids["release"], state.state_sha256),
        ).fetchone()[0]
        assert ReleaseProofIdentity.model_validate(result).header.release_result_id == case.ids["release"]
    return state


def compare(db, case, source="source-a"):
    request = dict(
        tenant_id=case.ids["tenant"],
        owner_subject="issuer|owner",
        thread_id=case.ids["thread"],
        run_id=case.ids["run"],
        message_id=case.ids["message"],
        release_result_id=case.ids["release"],
        projection_version=1,
        source_reference_id=source,
    )
    with psycopg.connect(str(db.url.set(username=db.roles["api"]))) as api:
        return api.execute(
            "SELECT * FROM public.koinon_compare_release_proofs(%s)", (Jsonb([request]),)
        ).fetchall()


def test_migrated_proof_contains_only_receipt_selected_source(proof_database):
    case = seed(proof_database)
    state = publish(proof_database, case)
    assert [s.source_reference_id for s in state.sources] == ["source-a"]
    assert state.sources[0].supporting_result_ids == (case.ids["pin"],)
    result = compare(proof_database, case)
    assert len(result) == 1 and result[0][0]["source"]["source_part_id"] == "part-a"
    assert "Protected title" not in json.dumps(result) and "Answer" not in json.dumps(result)
    assert compare(proof_database, case, "source-b") == []


@pytest.mark.parametrize("before,after", [(10.0, "10"), (-0.0, "0")])
def test_equal_jsonb_numbers_cannot_hide_native_pin_change(proof_database, before, after):
    case = seed(proof_database, value=before)
    publish(proof_database, case)
    with psycopg.connect(str(proof_database.url)) as owner:
        raw = owner.execute(
            "SELECT payload::text FROM koinon_chat_tool_results WHERE id=%s", (case.ids["pin"],)
        ).fetchone()[0]
        changed = raw.replace('"number": ' + str(before), '"number": ' + after)
        assert changed != raw
        assert owner.execute("SELECT %s::jsonb=%s::jsonb", (raw, changed)).fetchone()[0]
        owner.execute(
            "UPDATE koinon_chat_tool_results SET payload=%s::json WHERE id=%s", (changed, case.ids["pin"])
        )
    assert compare(proof_database, case) == []


def test_completion_fields_do_not_invalidate_but_new_generation_does(proof_database):
    case = seed(proof_database)
    publish(proof_database, case)
    with psycopg.connect(str(proof_database.url)) as owner:
        owner.execute(
            "UPDATE koinon_chat_runs SET "
            "status='completed',sequence=99,worker_id=NULL,lease_until=NULL WHERE id=%s",
            (case.ids["run"],),
        )
        owner.execute(
            "UPDATE koinon_chat_tool_results SET "
            "payload=jsonb_set(payload::jsonb,'{generation,finished_at}','\"later\"')::json WHERE id=%s",
            (case.ids["generation"],),
        )
    assert len(compare(proof_database, case)) == 1
    with psycopg.connect(str(proof_database.url)) as owner:
        owner.execute(
            "INSERT INTO koinon_chat_tool_results(id,run_id,kind,payload,created_at) "
            "VALUES(%s,%s,'generation',%s,now())",
            ("new_" + case.ids["generation"], case.ids["run"], Json({"generation": {"start_sequence": 100}})),
        )
    assert compare(proof_database, case) == []


def test_api_cannot_execute_or_switch_to_private_writer(proof_database):
    db = proof_database
    with psycopg.connect(str(db.url.set(username=db.roles["api"])), autocommit=True) as api:
        for statement, params in [
            ("SELECT public.koinon_publish_release_proof('fake','fake','worker',1)", ()),
            ("SELECT public.koinon_backfill_release_proof('fake','fake','job','claim',1)", ()),
            ("SELECT public.koinon_capture_release_proof('fake')", ()),
            ("SELECT public.koinon_prepare_release_backfill('fake','job','claim',1)", ()),
        ]:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                api.execute(statement, params)
        for role in (*db.roles.values(), "koinon_release_proof_owner"):
            if role != db.roles["api"]:
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    api.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(role)))


def test_immutability_survives_accidental_table_and_column_overgrant(proof_database):
    db = proof_database
    case = seed(db)
    publish(db, case)
    tables = db.provisioner.RELEASE_PROOF_TABLES[:3]
    with psycopg.connect(str(db.url)) as owner:
        for table in tables:
            owner.execute(
                sql.SQL("GRANT ALL ON TABLE {} TO {}").format(
                    sql.Identifier(table), sql.Identifier(db.roles["api"])
                )
            )
    try:
        with psycopg.connect(str(db.url.set(username=db.roles["api"])), autocommit=True) as api:
            for table in tables:
                for operation in (
                    "UPDATE {} SET projection_version=projection_version",
                    "DELETE FROM {}",
                    "TRUNCATE {} CASCADE",
                ):
                    with pytest.raises(psycopg.errors.InsufficientPrivilege):
                        api.execute(sql.SQL(operation).format(sql.Identifier(table)))
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                api.execute(
                    "INSERT INTO koinon_answer_release_proof_pins SELECT "
                    "release_result_id,projection_version,'forged',result_kind,"
                    "canonical_sha256,native_sha256 "
                    "FROM koinon_answer_release_proof_pins LIMIT 1"
                )
    finally:
        with psycopg.connect(str(db.url)) as owner:
            db.provisioner.grant_release_proof_role(owner, db.roles["api"], kind="api")


@pytest.mark.parametrize(
    "worker_id,forged_state,code",
    [
        ("old-worker", False, "P5504"),
        ("worker", True, "P5503"),
    ],
)
def test_publication_failure_rolls_back_receipt_and_proof(proof_database, worker_id, forged_state, code):
    db = proof_database
    case = seed(db)
    with (
        pytest.raises(psycopg.Error) as error,
        psycopg.connect(str(db.url.set(username=db.roles["publisher"]))) as worker,
    ):
        insert_release(worker, case)
        state = capture(worker, case)
        worker.execute(
            "SELECT public.koinon_publish_release_proof(%s,%s,%s,1)",
            (case.ids["release"], "0" * 64 if forged_state else state.state_sha256, worker_id),
        )
    assert error.value.sqlstate == code
    with psycopg.connect(str(db.url)) as owner:
        assert (
            owner.execute(
                "SELECT count(*) FROM koinon_chat_tool_results WHERE id=%s", (case.ids["release"],)
            ).fetchone()[0]
            == 0
        )
        assert (
            owner.execute(
                "SELECT count(*) FROM koinon_answer_release_proofs WHERE release_result_id=%s",
                (case.ids["release"],),
            ).fetchone()[0]
            == 0
        )


def test_stale_claim_and_blocked_checkpoint_preserve_cursor(proof_database):
    db = proof_database
    case = seed(db)
    with psycopg.connect(str(db.url)) as owner:
        insert_release(owner, case)
    with psycopg.connect(str(db.url.set(username=db.roles["maintenance"]))) as maint:
        claim = maint.execute(
            "SELECT public.koinon_claim_release_projection(%s,'claim',%s)",
            (case.ids["run"], case.ids["tenant"]),
        ).fetchone()[0]
        maint.commit()
        state = capture(maint, case)
        with maint.transaction():
            with pytest.raises(psycopg.Error) as error, maint.transaction():
                maint.execute(
                    "SELECT public.koinon_backfill_release_proof(%s,%s,%s,'stale',%s)",
                    (case.ids["release"], state.state_sha256, claim["job_id"], claim["revision"]),
                )
            assert error.value.sqlstate == "P5504"
        candidate = maint.execute(
            "SELECT * FROM public.koinon_release_projection_candidates(%s,'claim',%s,25)",
            (claim["job_id"], claim["revision"]),
        ).fetchone()[0]
        maint.execute(
            "SELECT public.koinon_checkpoint_release_projection(%s,'claim',%s,%s,%s,'blocked')",
            (claim["job_id"], claim["revision"], candidate["release_result_id"], candidate["created_at"]),
        )
    with psycopg.connect(str(db.url)) as owner:
        assert owner.execute(
            "SELECT state,cursor_release_id,blocked FROM koinon_answer_release_projection_jobs WHERE "
            "job_id=%s",
            (claim["job_id"],),
        ).fetchone() == ("blocked", None, 1)


def test_migration_has_usable_identity_indexes(proof_database):
    noise = seed(proof_database)
    with psycopg.connect(str(proof_database.url)) as owner:
        owner.execute(
            """INSERT INTO koinon_chat_tool_results(id,run_id,kind,payload,created_at)
          SELECT %s||n::text,%s,'search','{}',now() FROM generate_series(1,20000) n""",
            ("noise_" + noise.ids["pin"], noise.ids["run"]),
        )
        owner.execute(
            """INSERT INTO koinon_chat_events(id,run_id,sequence,type,data,created_at)
          SELECT %s||n::text,%s,n,'other','{}',now() FROM generate_series(1,20000) n""",
            ("noise_" + noise.ids["pin"], noise.ids["run"]),
        )
        owner.execute("ANALYZE koinon_chat_tool_results")
        owner.execute("ANALYZE koinon_chat_events")
        for query, index in (
            (
                "SELECT id FROM koinon_chat_tool_results WHERE kind='answer_release' ORDER BY "
                "created_at,id LIMIT 25",
                "ix_answer_release_keyset",
            ),
            (
                "SELECT id FROM koinon_chat_tool_results WHERE run_id='selected' AND "
                "kind='generation' ORDER BY id",
                "ix_answer_result_selector",
            ),
            (
                "SELECT sequence FROM koinon_chat_events WHERE run_id='selected' AND "
                "type='message_reset' ORDER BY sequence DESC LIMIT 1",
                "ix_answer_event_selector",
            ),
        ):
            plan = owner.execute("EXPLAIN (FORMAT JSON) " + query).fetchone()[0]
            serialized = json.dumps(plan)
            assert "Seq Scan" not in serialized and "Index" in serialized
            assert owner.execute(
                "SELECT indisvalid FROM pg_index WHERE indexrelid=to_regclass(%s)", (index,)
            ).fetchone() == (True,)


def test_capture_classifies_bounds_and_ambiguous_generations(proof_database):
    db = proof_database
    case = seed(db)
    with psycopg.connect(str(db.url)) as owner:
        insert_release(owner, case)
        owner.execute(
            """INSERT INTO koinon_chat_tool_results(id,run_id,kind,payload,created_at)
          SELECT %s,run_id,kind,payload,created_at FROM koinon_chat_tool_results WHERE id=%s""",
            ("tie_" + case.ids["generation"], case.ids["generation"]),
        )
    with psycopg.connect(str(db.url.set(username=db.roles["maintenance"])), autocommit=True) as maint:
        with pytest.raises(psycopg.Error) as error:
            capture(maint, case)
        assert error.value.sqlstate == "P5502"
    with psycopg.connect(str(db.url)) as owner:
        owner.execute(
            """INSERT INTO koinon_chat_tool_results(id,run_id,kind,payload,created_at)
          SELECT %s||n::text,%s,'search','{}',now() FROM generate_series(1,2001) n""",
            ("bound_" + case.ids["pin"], case.ids["run"]),
        )
    with psycopg.connect(str(db.url.set(username=db.roles["maintenance"])), autocommit=True) as maint:
        with pytest.raises(psycopg.Error) as error:
            capture(maint, case)
        assert error.value.sqlstate == "P5501"


def test_incomplete_provenance_retains_valid_receipt_without_document_entry(proof_database):
    db = proof_database
    case = seed(db)
    case.payload["source_manifest"]["complete"] = False
    case.release["release"]["result_pins"][0]["sha256"] = digest({"kind": "search", "payload": case.payload})
    case.release["seal_sha256"] = digest(case.release["release"])
    case.release["context_sha256"] = context_hash(case.release["seal_sha256"], 0)
    with psycopg.connect(str(db.url)) as owner:
        owner.execute(
            "UPDATE koinon_chat_tool_results SET payload=%s WHERE id=%s",
            (Json(case.payload), case.ids["pin"]),
        )
    state = publish(db, case)
    assert not state.header.provenance_complete and state.sources == ()
    assert len(compare(db, case, None)) == 1
    assert compare(db, case) == []


def test_deferred_constraint_rejects_header_without_exact_children(proof_database):
    db = proof_database
    case = seed(db)
    with psycopg.connect(str(db.url)) as owner:
        insert_release(owner, case)
        state = capture(owner, case)
    header = state.header.model_dump(mode="json")
    header.update(
        state_sha256=state.state_sha256,
        verifier="fixture",
        writer_kind="backfill",
        maintenance_claim_id="fixture",
        created_at=case.now.isoformat(),
    )
    for field in (
        "state_sha256",
        "canonical_seal_sha256",
        "release_native_sha256",
        "message_native_sha256",
        "selection_native_sha256",
        "active_selector_sha256",
    ):
        header[field] = "\\x" + header[field]
    with pytest.raises(psycopg.errors.CheckViolation), psycopg.connect(str(db.url)) as owner:
        owner.execute("SET LOCAL ROLE koinon_release_proof_owner")
        owner.execute(
            """INSERT INTO koinon_answer_release_proofs
          SELECT (jsonb_populate_record(NULL::koinon_answer_release_proofs,%s)).*""",
            (Jsonb(header),),
        )
    with psycopg.connect(str(db.url)) as owner:
        assert (
            owner.execute(
                "SELECT count(*) FROM koinon_answer_release_proofs WHERE release_result_id=%s",
                (case.ids["release"],),
            ).fetchone()[0]
            == 0
        )


def test_source_conflict_is_not_silently_dropped(proof_database):
    db = proof_database
    case = seed(db)
    conflicting = dict(case.payload["source_manifest"]["sources"][0], source_part_id="conflicting")
    case.payload["source_manifest"]["sources"].append(conflicting)
    with psycopg.connect(str(db.url)) as owner:
        owner.execute(
            "UPDATE koinon_chat_tool_results SET payload=%s WHERE id=%s",
            (Json(case.payload), case.ids["pin"]),
        )
        insert_release(owner, case)
    with psycopg.connect(str(db.url.set(username=db.roles["maintenance"])), autocommit=True) as maint:
        with pytest.raises(psycopg.Error) as error:
            capture(maint, case)
        assert error.value.sqlstate == "P5503"


def test_backfill_commits_exact_proof_and_checkpoint_together(proof_database):
    db = proof_database
    case = seed(db)
    with psycopg.connect(str(db.url)) as owner:
        insert_release(owner, case)
    with psycopg.connect(str(db.url.set(username=db.roles["maintenance"]))) as maint:
        claim = maint.execute(
            "SELECT public.koinon_claim_release_projection(%s,'claim',%s)",
            (case.ids["run"], case.ids["tenant"]),
        ).fetchone()[0]
        maint.commit()
        state = capture(maint, case)
        maint.execute(
            "SELECT public.koinon_backfill_release_proof(%s,%s,%s,'claim',%s)",
            (case.ids["release"], state.state_sha256, claim["job_id"], claim["revision"]),
        )
        maint.execute(
            "SELECT public.koinon_checkpoint_release_projection(%s,'claim',%s,%s,%s,'projected')",
            (claim["job_id"], claim["revision"], case.ids["release"], case.now),
        )
    assert len(compare(db, case)) == 1
    with psycopg.connect(str(db.url)) as owner:
        assert owner.execute(
            "SELECT state,projected FROM koinon_answer_release_projection_jobs WHERE job_id=%s",
            (claim["job_id"],),
        ).fetchone() == ("complete", 1)


@pytest.mark.parametrize(
    "original,changed",
    [
        ('{"number":1e1}', '{"number":10}'),
        ('{"number":-0.0}', '{"number":0}'),
        ('{"text":"é"}', '{"text":"\\u00e9"}'),
        ('{"a":1,"b":2}', '{"b":2,"a":1}'),
        ('{"nested":[null,1e1]}', '{"nested":[null,10]}'),
    ],
)
def test_native_hash_preserves_json_lexemes(proof_database, original, changed):
    with psycopg.connect(str(proof_database.url)) as owner:
        row = owner.execute(
            """SELECT %s::jsonb=%s::jsonb,
          public.koinon_release_native_hash('fixture',jsonb_build_array(%s::json::text))
          <>public.koinon_release_native_hash('fixture',jsonb_build_array(%s::json::text))""",
            (original, changed, original, changed),
        ).fetchone()
        assert row == (True, True)
        assert owner.execute("""SELECT
          public.koinon_release_native_hash('fixture',jsonb_build_array(NULL::text))
          <>public.koinon_release_native_hash('fixture',jsonb_build_array('null'::json::text))""").fetchone()[
            0
        ]


def test_fresh_metadata_installs_equivalent_guards(proof_database):
    from pyfly.data.relational.sqlalchemy import Base

    from koinon.answers.release_proof_entities import PROOF_TABLES
    from koinon.assistants.entities import ChatEvent
    from koinon.assistants.history.entities import ChatFolder

    db = proof_database
    name = "proof_metadata_" + uuid4().hex[:12]
    url = db.url.set(database=name)
    engine = sa.create_engine(url.set(drivername="postgresql+psycopg"))
    with psycopg.connect(str(db.url), autocommit=True) as owner:
        owner.execute(
            sql.SQL("CREATE DATABASE {} TEMPLATE template0 ENCODING 'UTF8'").format(sql.Identifier(name))
        )
    try:
        tables = [
            model.__table__
            for model in (
                Tenant,
                Provider,
                AgentConfiguration,
                ChatFolder,
                ChatThread,
                ChatMessage,
                ChatRun,
                ChatEvent,
                ToolResult,
            )
        ]
        Base.metadata.create_all(engine, tables=[*tables, *PROOF_TABLES])
        with psycopg.connect(str(url)) as owner:
            for kind, role in db.roles.items():
                db.provisioner.grant_release_proof_role(owner, role, kind=kind)
                if kind != "maintenance":
                    for table in tables:
                        if table.name.startswith("koinon_chat_"):
                            db.provisioner.grant_table(owner, table.name, role)
        fresh = SimpleNamespace(url=url, engine=engine, roles=db.roles, provisioner=db.provisioner)
        case = seed(fresh)
        publish(fresh, case)
        assert len(compare(fresh, case)) == 1
        test_api_cannot_execute_or_switch_to_private_writer(fresh)
        test_immutability_survives_accidental_table_and_column_overgrant(fresh)
    finally:
        engine.dispose()
        with psycopg.connect(str(db.url), autocommit=True) as owner:
            owner.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))


def test_pin_fingerprint_guard_has_a_causal_mutation_probe(proof_database):
    from koinon.answers.release_proof_guards import COMPARE_SQL

    db = proof_database
    case = seed(db)
    publish(db, case)
    with psycopg.connect(str(db.url)) as owner:
        owner.execute(
            "UPDATE koinon_chat_tool_results SET "
            "payload=jsonb_set(payload::jsonb,'{number}','11')::json WHERE id=%s",
            (case.ids["pin"],),
        )
    assert compare(db, case) == []
    mutant = COMPARE_SQL.replace(" OR state->>'state_sha256' IS DISTINCT FROM encode(stored,'hex')", "")
    assert mutant != COMPARE_SQL
    try:
        with psycopg.connect(str(db.url)) as owner:
            owner.execute(mutant)
        # The same denial assertion fails when native-state equality is omitted.
        with pytest.raises(AssertionError):
            assert compare(db, case) == []
    finally:
        with psycopg.connect(str(db.url)) as owner:
            owner.execute(COMPARE_SQL)
    assert compare(db, case) == []


def test_prepare_backfill_holds_state_against_competing_mutations(proof_database):
    db = proof_database
    case = seed(db)
    with psycopg.connect(str(db.url)) as owner:
        insert_release(owner, case)
    with psycopg.connect(str(db.url.set(username=db.roles["maintenance"]))) as maint:
        claim = maint.execute(
            "SELECT public.koinon_claim_release_projection(%s,'claim',%s)",
            (case.ids["run"], case.ids["tenant"]),
        ).fetchone()[0]
        maint.commit()
        maint.execute("SET LOCAL lock_timeout='1s'")
        maint.execute("SET LOCAL statement_timeout='5s'")
        prepared = maint.execute(
            "SELECT public.koinon_prepare_release_backfill(%s,%s,'claim',%s)",
            (case.ids["release"], claim["job_id"], claim["revision"]),
        ).fetchone()[0]
        state = ReleaseProofCapture.model_validate(prepared)
        with psycopg.connect(str(db.url), autocommit=True) as competing:
            competing.execute("SET lock_timeout='10ms'")
            for statement, parameters in (
                ("UPDATE koinon_chat_tool_results SET payload='{}' WHERE id=%s", (case.ids["pin"],)),
                ("UPDATE koinon_chat_messages SET text='changed' WHERE id=%s", (case.ids["message"],)),
                (
                    """INSERT INTO koinon_chat_events(id,run_id,sequence,type,data,created_at)
                  VALUES(%s,%s,200,'message_reset','{}',now())""",
                    ("reset_" + case.ids["run"], case.ids["run"]),
                ),
            ):
                with pytest.raises(psycopg.errors.LockNotAvailable):
                    competing.execute(statement, parameters)
        assert capture(maint, case) == state
        maint.execute(
            "SELECT public.koinon_backfill_release_proof(%s,%s,%s,'claim',%s)",
            (case.ids["release"], state.state_sha256, claim["job_id"], claim["revision"]),
        )
    assert len(compare(db, case)) == 1


def test_prepare_rejects_stale_claim_before_waiting_for_parent_locks(proof_database):
    db = proof_database
    case = seed(db)
    with psycopg.connect(str(db.url)) as owner:
        insert_release(owner, case)
    with psycopg.connect(str(db.url.set(username=db.roles["maintenance"]))) as maint:
        claim = maint.execute(
            "SELECT public.koinon_claim_release_projection(%s,'claim',%s)",
            (case.ids["run"], case.ids["tenant"]),
        ).fetchone()[0]
    with psycopg.connect(str(db.url)) as owner:
        owner.execute("SELECT id FROM koinon_chat_runs WHERE id=%s FOR UPDATE", (case.ids["run"],))
        with psycopg.connect(str(db.url.set(username=db.roles["maintenance"])), autocommit=True) as maint:
            maint.execute("SET lock_timeout='10ms'")
            with pytest.raises(psycopg.Error) as error:
                maint.execute(
                    "SELECT public.koinon_prepare_release_backfill(%s,%s,'stale',%s)",
                    (case.ids["release"], claim["job_id"], claim["revision"]),
                )
            assert error.value.sqlstate == "P5504"
