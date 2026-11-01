# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import pytest

from koinon.workers.scaling import ScalingLimits, render_demand_function, require_colocated_postgres


def topology():
    return {
        name: f"postgresql://{name}:not-a-secret@owned.example:5432/koinon"
        for name in ("primary", "canon", "canon_admin", "structured", "structured_admin")
    }


def test_generated_counts_only_function_uses_shared_ten_specs_and_live_database_clock():
    contract = render_demand_function(ScalingLimits())
    assert len(contract.queues) == 10 and {"bulk_intake", "bulk_query"} <= set(contract.queues)
    assert "CURRENT_TIMESTAMP" in contract.sql and "2026-" not in contract.sql
    assert "SECURITY DEFINER" in contract.sql and "SET search_path = pg_catalog" in contract.sql
    assert "public.flyquery_callback_outbox" in contract.sql
    assert (
        "public.flyquery_ingest_jobs" in contract.sql and "public.koinon_digest_subscriptions" in contract.sql
    )
    assert "knowledge.bulk.intake" in contract.sql and "knowledge.bulk.query" in contract.sql
    assert "payload" not in str(contract.columns) and "question" not in str(contract.columns)
    assert contract.query == "SELECT koinon_operations.worker_demand_v1()"


@pytest.mark.parametrize(
    "change",
    [
        {"canon": "postgresql://r@other.example/koinon"},
        {"structured": "postgresql://r@owned.example:5432/other"},
        {"primary": "sqlite:///local.db"},
    ],
)
def test_split_database_or_non_postgres_is_rejected_before_operator_connection(change):
    values = topology()
    values.update(change)
    with pytest.raises(ValueError, match="same PostgreSQL"):
        require_colocated_postgres(values)


def test_colocated_different_runtime_roles_are_allowed_without_returning_credentials():
    result = require_colocated_postgres(topology())
    assert result == ("owned.example", 5432, "koinon")
    assert "not-a-secret" not in repr(result)


@pytest.mark.parametrize(
    "query", ["host=other.example", "port=59999", "dbname=other", "hostaddr=127.0.0.2", "service=other"]
)
def test_routing_overrides_cannot_bypass_colocation_preflight(query):
    values = topology()
    values["canon"] = "postgresql://r@owned.example:5432/koinon?" + query
    with pytest.raises(ValueError, match="same PostgreSQL"):
        require_colocated_postgres(values)
