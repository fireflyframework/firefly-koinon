# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Run only against a newly owned disposable PostgreSQL fixture."""

import os

import psycopg
import pytest
import sqlalchemy as sa
from psycopg import sql
from sqlalchemy.sql import visitors
from sqlalchemy.sql.elements import ColumnClause
from sqlalchemy.sql.selectable import TableClause

from koinon.operations.settings import OperationalSettings
from koinon.workers.observations import queue_specifications
from koinon.workers.scaler_installation import install
from koinon.workers.scaling import ScalingLimits, render_demand_function


@pytest.mark.skipif(
    not os.environ.get("KOINON_OWNED_SCALER_TEST_DSN"), reason="requires new owned PostgreSQL fixture"
)
def test_native_function_counts_bulk_retries_active_and_due_schedules_without_raw_access():
    contract = render_demand_function(ScalingLimits())
    with psycopg.connect(os.environ["KOINON_OWNED_SCALER_TEST_DSN"]) as connection:
        types = {}
        for spec in queue_specifications(sa.func.current_timestamp(), OperationalSettings(), schema="public"):
            from koinon.workers.observations import queue_statement

            for node in visitors.iterate(
                queue_statement(spec.table, spec.ready, spec.active, spec.retry, spec.created, limit=100)
            ):
                if isinstance(node, ColumnClause) and isinstance(node.table, TableClause):
                    affinity = node.type._type_affinity
                    kind = (
                        "boolean"
                        if issubclass(affinity, sa.Boolean)
                        else "timestamptz"
                        if issubclass(affinity, sa.DateTime)
                        else "integer"
                        if issubclass(affinity, sa.Integer)
                        else "text"
                    )
                    types[(node.table.name, node.name)] = kind
        for table, columns in contract.columns.items():
            connection.execute(
                sql.SQL("CREATE TABLE public.{} ({})").format(
                    sql.Identifier(table),
                    sql.SQL(",").join(
                        sql.SQL("{} {}").format(sql.Identifier(column), sql.SQL(types[(table, column)]))
                        for column in columns
                    ),
                )
            )
        connection.execute("ALTER TABLE public.lattice_jobs ADD COLUMN payload text")
        connection.execute("ALTER TABLE public.lattice_jobs ENABLE ROW LEVEL SECURITY")
        connection.execute("ALTER TABLE public.lattice_jobs FORCE ROW LEVEL SECURITY")
        connection.execute("CREATE ROLE test_scaler LOGIN")
        install(connection, contract, owner="test_demand_owner", reader="test_scaler")
        assert connection.execute(contract.query).fetchone()[0] == 0
        connection.execute("INSERT INTO public.koinon_bulk_batches(id,cancelled) VALUES ('b',false)")
        connection.execute(
            "INSERT INTO public.koinon_bulk_items(batch_id,job_id,status) VALUES ('b','j','queued')"
        )
        connection.execute(
            "INSERT INTO public.lattice_jobs "
            "(id,kind,status,available_at,attempts,max_attempts,created_at,payload) "
            "VALUES ('j','knowledge.bulk.intake','queued',"
            "CURRENT_TIMESTAMP-interval '1 minute',999,3,CURRENT_TIMESTAMP,'private payload')"
        )
        assert connection.execute(contract.query).fetchone()[0] == 1
        connection.execute(
            "UPDATE public.lattice_jobs SET status='running',lease_until=CURRENT_TIMESTAMP+interval "
            "'1 minute'"
        )
        connection.execute("UPDATE public.koinon_bulk_batches SET cancelled=true")
        assert connection.execute(contract.query).fetchone()[0] == 1
        connection.execute("UPDATE public.lattice_jobs SET lease_until=CURRENT_TIMESTAMP-interval '1 minute'")
        assert connection.execute(contract.query).fetchone()[0] == 0
        connection.execute("UPDATE public.koinon_bulk_batches SET cancelled=false")
        assert connection.execute(contract.query).fetchone()[0] == 1
        connection.execute(
            "INSERT INTO public.koinon_digest_subscriptions(enabled,next_due_at) VALUES "
            "(true,CURRENT_TIMESTAMP-interval '1 second')"
        )
        assert connection.execute(contract.query).fetchone()[0] == 2
        # Idempotent install preserves grants, metadata and live counts.
        install(connection, contract, owner="test_demand_owner", reader="test_scaler")
        connection.execute("SET ROLE test_scaler")
        assert connection.execute(contract.query).fetchone()[0] == 2
        for statement in (
            "SELECT payload FROM public.lattice_jobs",
            "SELECT status FROM public.lattice_jobs",
            "SELECT * FROM public.koinon_digest_subscriptions",
            "CREATE TABLE koinon_operations.forbidden(id int)",
        ):
            with pytest.raises(psycopg.errors.InsufficientPrivilege), connection.transaction():
                connection.execute(statement)
        connection.execute("RESET ROLE")
        connection.execute("CREATE ROLE unrelated_reader LOGIN")
        connection.execute("GRANT test_demand_owner TO unrelated_reader")
        with pytest.raises(ValueError, match="reachable"), connection.transaction():
            install(connection, contract, owner="test_demand_owner", reader="test_scaler")
        connection.execute("REVOKE test_demand_owner FROM unrelated_reader")
        connection.execute("SET ROLE unrelated_reader")
        with pytest.raises(psycopg.errors.InsufficientPrivilege), connection.transaction():
            connection.execute(contract.query)
        connection.execute("RESET ROLE")
