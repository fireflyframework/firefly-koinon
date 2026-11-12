# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Replacement plans preserve historical locators when reviewed live members reuse them."""

import copy
import importlib.util
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from alembic import command
from psycopg.types.json import Jsonb
from sqlalchemy import event

pytestmark = pytest.mark.integration
_spec = importlib.util.spec_from_file_location(
    "replacement_metadata_fixture", Path(__file__).with_name("test_metadata_provenance_schema.py")
)
_metadata = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_metadata)
source_database = _metadata.source_database
metadata_database = _metadata.metadata_database


def replacement_plan(connection, action):
    workspace, dataset, baseline = _metadata.replacement_dataset(connection)
    old = baseline["members"][0]
    removed = {
        "schema": "koinon.dataset-replacement-member.v1",
        "member_key": "root",
        "action": "remove",
        "table_id": old["table_id"],
        "catalog_table_id": old["catalog_table_id"],
        "snapshot_id": old["snapshot_id"],
    }
    table, snapshot = uuid4(), uuid4()
    if action == "retain":
        connection.execute(
            "INSERT INTO flyquery_tables(id,tenant_id,workspace_id,dataset_id,source_file_id,"
            "name,qualified_name) VALUES(%s,'tenant',%s,%s,%s,'second','second')",
            (table, workspace, dataset, baseline["native_file_id"]),
        )
        connection.execute(
            "INSERT INTO flyquery_schema_snapshots(id,tenant_id,workspace_id,dataset_id,table_id,"
            "snapshot_hash,n_columns,status,triggered_by,created_by) "
            "VALUES(%s,'tenant',%s,%s,%s,'second',1,'READY','USER','reader')",
            (snapshot, workspace, dataset, table),
        )
        connection.execute("UPDATE flyquery_tables SET current_snapshot_id=%s WHERE id=%s", (snapshot, table))
        baseline["members"].append(
            {
                **old,
                "member_key": "second",
                "table_id": str(table),
                "catalog_table_id": "catalog-second",
                "snapshot_id": str(snapshot),
            }
        )
    live = {
        **removed,
        "action": action,
        "table_id": str(table),
        "catalog_table_id": "catalog-second",
        "snapshot_id": str(uuid4()),
    }
    return workspace, dataset, baseline, [removed, live]


def set_plan(connection, operation, plan):
    connection.execute(
        "UPDATE flyquery_bulk_operations SET plan_json=%s WHERE id=%s", (Jsonb(plan), operation)
    )


@pytest.mark.parametrize("action", ["add", "retain"])
def test_live_member_reuses_removed_locator_without_rewriting_history(metadata_database, action):
    uri, _, _ = metadata_database
    with psycopg.connect(uri) as connection:
        workspace, dataset, baseline, plan = replacement_plan(connection, action)
        operation = _metadata.bulk_operation(
            connection, workspace, dataset, kind="replace", baseline=baseline
        )
        set_plan(connection, operation, plan)
        connection.commit()
        assert connection.execute(
            "SELECT baseline_json,plan_json FROM flyquery_bulk_operations WHERE id=%s", (operation,)
        ).fetchone() == (baseline, plan)
        assert connection.execute(
            "SELECT current_snapshot_id::text FROM flyquery_tables WHERE id=%s",
            (baseline["members"][0]["table_id"],),
        ).fetchone() == (baseline["members"][0]["snapshot_id"],)


def test_removed_member_cannot_forge_its_historical_locator(metadata_database):
    uri, _, _ = metadata_database
    with psycopg.connect(uri) as connection:
        workspace, dataset, baseline, plan = replacement_plan(connection, "add")
        operation = _metadata.bulk_operation(
            connection, workspace, dataset, kind="replace", baseline=baseline
        )
        plan[0]["member_key"] = "invented-tombstone"
        with (
            pytest.raises(psycopg.errors.CheckViolation, match="baseline identities"),
            connection.transaction(),
        ):
            set_plan(connection, operation, plan)
        assert connection.execute(
            "SELECT plan_json FROM flyquery_bulk_operations WHERE id=%s", (operation,)
        ).fetchone() == (None,)


@pytest.mark.parametrize(
    "problem",
    [
        "duplicate_live",
        "duplicate_removed",
        "table_identity",
        "catalog_identity",
        "missing_baseline",
        "removed_snapshot",
        "retained_snapshot",
        "too_many_live",
        "long_locator",
    ],
)
def test_locator_reuse_preserves_identity_coverage_snapshot_and_size_guards(metadata_database, problem):
    uri, _, _ = metadata_database
    with psycopg.connect(uri) as connection:
        workspace, dataset, baseline, valid = replacement_plan(connection, "retain")
        accepted = _metadata.bulk_operation(connection, workspace, dataset, kind="replace", baseline=baseline)
        set_plan(connection, accepted, valid)
        connection.commit()
        operation = _metadata.bulk_operation(
            connection, workspace, dataset, kind="replace", baseline=baseline
        )
        plan = copy.deepcopy(valid)
        if problem == "duplicate_live":
            plan.append(
                {
                    **plan[1],
                    "action": "add",
                    "table_id": str(uuid4()),
                    "catalog_table_id": "third",
                    "snapshot_id": str(uuid4()),
                }
            )
        elif problem == "duplicate_removed":
            plan.append(copy.deepcopy(plan[0]))
        elif problem == "table_identity":
            plan[1]["table_id"] = plan[0]["table_id"]
        elif problem == "catalog_identity":
            plan[1]["catalog_table_id"] = plan[0]["catalog_table_id"]
        elif problem == "missing_baseline":
            plan = plan[1:]
        elif problem == "removed_snapshot":
            plan[0]["snapshot_id"] = str(uuid4())
        elif problem == "retained_snapshot":
            plan[1]["snapshot_id"] = baseline["members"][1]["snapshot_id"]
        elif problem == "too_many_live":
            plan.extend(
                {
                    **plan[1],
                    "action": "add",
                    "member_key": f"extra-{n}",
                    "table_id": str(uuid4()),
                    "catalog_table_id": f"extra-{n}",
                    "snapshot_id": str(uuid4()),
                }
                for n in range(16)
            )
        elif problem == "long_locator":
            plan[1]["member_key"] = "x" * 2049
        with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
            set_plan(connection, operation, plan)
        assert connection.execute(
            "SELECT plan_json FROM flyquery_bulk_operations WHERE id=%s", (operation,)
        ).fetchone() == (None,)
        assert connection.execute(
            "SELECT baseline_json,plan_json FROM flyquery_bulk_operations WHERE id=%s", (accepted,)
        ).fetchone() == (baseline, valid)


def test_reused_locator_plan_is_atomic_and_operation_binding_stays_immutable(metadata_database):
    uri, _, _ = metadata_database
    with psycopg.connect(uri) as connection:
        workspace, dataset, baseline, plan = replacement_plan(connection, "add")
        operation = _metadata.bulk_operation(
            connection, workspace, dataset, kind="replace", baseline=baseline
        )
        connection.commit()
        with pytest.raises(RuntimeError, match="owned publication interruption"), connection.transaction():
            set_plan(connection, operation, plan)
            raise RuntimeError("owned publication interruption")
        assert connection.execute(
            "SELECT plan_json FROM flyquery_bulk_operations WHERE id=%s", (operation,)
        ).fetchone() == (None,)
        set_plan(connection, operation, plan)
        connection.commit()
        changed = copy.deepcopy(plan)
        changed[1]["member_key"] = "other"
        for statement, payload in (
            ("UPDATE flyquery_bulk_operations SET plan_json=%s WHERE id=%s", Jsonb(changed)),
            ("UPDATE flyquery_bulk_operations SET baseline_json=%s WHERE id=%s", Jsonb({})),
            ("UPDATE flyquery_bulk_operations SET file_id=%s WHERE id=%s", uuid4()),
            ("UPDATE flyquery_bulk_operations SET dataset_id=%s WHERE id=%s", uuid4()),
        ):
            with pytest.raises(psycopg.errors.ObjectNotInPrerequisiteState), connection.transaction():
                connection.execute(statement, (payload, operation))
        assert connection.execute(
            "SELECT dataset_id,baseline_json,plan_json FROM flyquery_bulk_operations WHERE id=%s",
            (operation,),
        ).fetchone() == (dataset, baseline, plan)


@pytest.mark.parametrize("action", ["add", "retain"])
def test_predecessor_upgrade_is_atomic_and_preserves_retained_operations(source_database, action):
    target, _, engine = source_database
    uri = target.set(drivername="postgresql").render_as_string(hide_password=False)
    migrate = _metadata._fixture.load("deploy/migrate.py")
    versions = _metadata.ROOT / "packages/structured/migrations/versions"
    with engine.connect() as connection:
        command.upgrade(migrate.history_config("structured", versions, connection), "0023_metadata_indexes")
        connection.commit()
    with psycopg.connect(uri) as connection:
        workspace, dataset, baseline, plan = replacement_plan(connection, action)
        operation = _metadata.bulk_operation(
            connection, workspace, dataset, kind="replace", baseline=baseline
        )
        ordinary = _metadata.bulk_operation(connection, workspace, dataset, kind="replace", baseline=baseline)
        ordinary_plan = [
            {
                "schema": "koinon.dataset-replacement-member.v1",
                "action": "retain",
                "member_key": member["member_key"],
                "table_id": member["table_id"],
                "catalog_table_id": member["catalog_table_id"],
                "snapshot_id": str(uuid4()),
            }
            for member in baseline["members"]
        ]
        set_plan(connection, ordinary, ordinary_plan)
        with (
            pytest.raises(psycopg.errors.CheckViolation, match="identities must be unique"),
            connection.transaction(),
        ):
            set_plan(connection, operation, plan)
        before = connection.execute(
            "SELECT to_jsonb(t) FROM flyquery_bulk_operations t ORDER BY id"
        ).fetchall()

    def interrupt(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith("UPDATE koinon_structured_version"):
            raise RuntimeError("owned function migration interruption")

    with engine.connect() as connection:
        event.listen(connection, "before_cursor_execute", interrupt)
        try:
            with pytest.raises(RuntimeError, match="owned function migration interruption"):
                command.upgrade(migrate.history_config("structured", versions, connection), "head")
        finally:
            event.remove(connection, "before_cursor_execute", interrupt)
            connection.rollback()
    with psycopg.connect(uri) as connection:
        assert connection.execute("SELECT version_num FROM koinon_structured_version").fetchone() == (
            "0023_metadata_indexes",
        )
        with (
            pytest.raises(psycopg.errors.CheckViolation, match="identities must be unique"),
            connection.transaction(),
        ):
            set_plan(connection, operation, plan)
    with engine.connect() as connection:
        command.upgrade(migrate.history_config("structured", versions, connection), "head")
        connection.commit()
        with pytest.raises(RuntimeError, match="reviewed forward migration"):
            command.downgrade(
                migrate.history_config("structured", versions, connection), "0023_metadata_indexes"
            )
        connection.rollback()
    with psycopg.connect(uri) as connection:
        assert (
            connection.execute("SELECT to_jsonb(t) FROM flyquery_bulk_operations t ORDER BY id").fetchall()
            == before
        )
        set_plan(connection, operation, plan)
        assert connection.execute(
            "SELECT baseline_json,plan_json FROM flyquery_bulk_operations WHERE id=%s", (operation,)
        ).fetchone() == (baseline, plan)
        assert connection.execute(
            "SELECT plan_json FROM flyquery_bulk_operations WHERE id=%s", (ordinary,)
        ).fetchone() == (ordinary_plan,)
