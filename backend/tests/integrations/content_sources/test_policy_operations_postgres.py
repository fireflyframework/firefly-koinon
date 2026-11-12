# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Policy acceptance must commit with its immutable owner-scoped receipt."""

import psycopg
import pytest
from test_source_concurrency_postgres import source_sessions as source_sessions
from test_source_migration_postgres import source_database as source_database
from test_sync_schema_postgres import policy

pytestmark = pytest.mark.integration


async def test_acceptance_without_matching_apply_receipt_rolls_back(source_sessions):
    _, uri = source_sessions
    with psycopg.connect(uri) as connection:
        with (
            pytest.raises(psycopg.errors.CheckViolation, match="policy acceptance receipt"),
            connection.transaction(),
        ):
            policy(connection, accepted=False)
            connection.execute(
                "UPDATE koinon_content_policies SET accepted_by=owner, "
                "accepted_session_hash=repeat('d',64), "
                "accepted_operation_id='00000000-0000-0000-0000-000000000001', "
                "accepted_at=now()"
            )
        assert connection.execute("SELECT count(*) FROM koinon_content_policies").fetchone() == (0,)


def receipt(
    connection,
    *,
    action="review",
    operation=None,
    changes=None,
    identifier=None,
    policy_id="policy-mapping",
    expected_revision=None,
):
    from uuid import uuid4

    from psycopg.types.json import Json

    operation, identifier = operation or str(uuid4()), identifier or str(uuid4())
    row = connection.execute(
        "SELECT id,review_digest,review_expires_at,revision FROM koinon_content_policies WHERE id=%s",
        (policy_id,),
    ).fetchone()
    expected = row[3] if action == "apply" else expected_revision
    result = {
        "schema": "koinon.source-policy-operation.v1",
        "receipt_id": identifier,
        "operation_id": operation,
        "action": action,
        "mapping_id": "mapping",
        "policy_id": row[0],
        "expected_policy_revision": expected,
        "result_policy_revision": row[3],
        "review_digest": row[1],
        "review_expires_at": row[2].isoformat(),
        "disposition": "accepted" if action == "apply" else "reviewed",
    }
    result.update(changes or {})
    connection.execute(
        "INSERT INTO koinon_content_policy_operations "
        "VALUES(%s,'retained','issuer|alice',%s,%s,'mapping',%s,%s,%s,%s,%s,now())",
        (identifier, operation, action, row[0], expected, row[3], "a" * 64, Json(result)),
    )
    return operation


async def test_review_without_accepted_state_and_apply_commit_exact_receipts(source_sessions):
    _, uri = source_sessions
    with psycopg.connect(uri) as connection:
        policy(connection, accepted=False)
        receipt(connection)
        connection.commit()
        assert connection.execute("SELECT count(*) FROM koinon_content_sync_states").fetchone() == (0,)
        operation = receipt(connection, action="apply")
        connection.execute(
            "UPDATE koinon_content_policies SET "
            "accepted_by=owner,accepted_session_hash=repeat('d',64),accepted_operation_id=%"
            "s,accepted_at=now()",
            (operation,),
        )
        connection.commit()
        assert connection.execute("SELECT count(*) FROM koinon_content_policy_operations").fetchone() == (2,)
        for statement in (
            "DELETE FROM koinon_content_policy_operations",
            "UPDATE koinon_content_policy_operations SET action=action",
            "TRUNCATE koinon_content_policy_operations",
        ):
            with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
                connection.execute(statement)


@pytest.mark.parametrize(
    "changes",
    [
        {"title": "protected"},
        {"review_digest": "b" * 64},
        {"result_policy_revision": "1"},
        {"review_expires_at": None},
        {"disposition": "accepted"},
    ],
)
async def test_policy_receipt_cannot_hide_protected_data_or_rewrite_review(source_sessions, changes):
    _, uri = source_sessions
    with psycopg.connect(uri) as connection:
        policy(connection, accepted=False)
        with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
            receipt(connection, changes=changes)
        assert connection.execute("SELECT count(*) FROM koinon_content_policy_operations").fetchone() == (0,)


async def test_policy_namespace_rejects_cross_action_reuse(source_sessions):
    _, uri = source_sessions
    with psycopg.connect(uri) as connection:
        policy(connection, accepted=False)
        operation = receipt(connection)
        with pytest.raises(psycopg.errors.UniqueViolation), connection.transaction():
            receipt(connection, action="apply", operation=operation)
        assert connection.execute("SELECT action FROM koinon_content_policy_operations").fetchall() == [
            ("review",)
        ]


async def test_later_review_requires_its_previous_review_revision(source_sessions):
    _, uri = source_sessions
    with psycopg.connect(uri) as connection:
        policy(connection, accepted=False)
        receipt(connection)
        connection.execute("""INSERT INTO koinon_content_policies SELECT
          (jsonb_populate_record(NULL::koinon_content_policies,to_jsonb(p)||
            '{"id":"policy-second","revision":2,"review_id":"review-second"}'::jsonb)).*
          FROM koinon_content_policies p WHERE id='policy-mapping'""")
        with (
            pytest.raises(psycopg.errors.CheckViolation, match="invalid policy operation receipt"),
            connection.transaction(),
        ):
            receipt(connection, policy_id="policy-second")
        receipt(connection, policy_id="policy-second", expected_revision=1)
        connection.commit()
        assert connection.execute(
            "SELECT expected_policy_revision,result_policy_revision FROM "
            "koinon_content_policy_operations ORDER BY result_policy_revision"
        ).fetchall() == [(None, 1), (1, 2)]


async def test_policy_receipt_runtime_insert_has_no_mutation_grants(source_sessions, source_database):
    from psycopg import sql
    from test_source_migration_postgres import load

    _, uri = source_sessions
    _, role, _ = source_database
    with psycopg.connect(uri) as connection:
        policy(connection, accepted=False)
        roles = load("deploy/provision_roles.py")
        for table in ("koinon_content_policies", "koinon_content_policy_operations"):
            roles.grant_table(connection, table, role)
        connection.execute(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(role)))
        receipt(connection)
        assert connection.execute("SELECT count(*) FROM koinon_content_policy_operations").fetchone() == (1,)
        for statement in (
            "UPDATE koinon_content_policy_operations SET result_json='{}'",
            "DELETE FROM koinon_content_policy_operations",
            "TRUNCATE koinon_content_policy_operations",
        ):
            with pytest.raises(psycopg.errors.InsufficientPrivilege), connection.transaction():
                connection.execute(statement)
        connection.commit()
