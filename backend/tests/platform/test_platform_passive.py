# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from pyfly.actuator.health import HealthStatus
from pyfly.core import Config

from koinon.platform.diagnostics import PlatformDiagnostics
from koinon.platform.repositories import StatusWindow


async def test_passive_health_does_not_run_storage_model_email_or_global_queue_operations():
    native = SimpleNamespace(ingestion=AsyncMock(return_value=StatusWindow(("running", "failed"), True)))
    records = SimpleNamespace(
        catalog_states=AsyncMock(return_value=StatusWindow(("ready",), True)),
        index_targets=AsyncMock(return_value=((), True)),
        model_default_configured=AsyncMock(return_value=True),
    )
    sources = SimpleNamespace(
        all_datasources=lambda: [SimpleNamespace(name="primary")],
        datasources=lambda: [SimpleNamespace(name="primary", qualified_name="primary")],
    )
    operations = SimpleNamespace(
        sources=sources,
        health=SimpleNamespace(
            health=AsyncMock(
                return_value=HealthStatus(
                    status="UP", details={"secret": "postgresql://private@internal.invalid/db"}
                )
            )
        ),
        _role_policy=AsyncMock(return_value={"available": True}),
        _storage=Mock(side_effect=AssertionError("No storage roundtrip on GET")),
    )
    readiness = SimpleNamespace(observe=Mock(return_value=SimpleNamespace(state="ready")))
    diagnostics = PlatformDiagnostics(operations, records, native, readiness, Config({}))
    components = await diagnostics.observe("issuer|admin", "north")
    by_id = {item.id: item for item in components}
    assert by_id["database-primary"].status == "passed"
    for identifier in (
        "storage-documents",
        "storage-structured",
        "model-configuration",
        "communications",
        "workers",
    ):
        assert by_id[identifier].status == "unknown"
    assert by_id["workers"].observed_at is None
    assert by_id["ingestion-documents"].counts.observed_failed == 1
    assert by_id["ingestion-documents"].status == "failed"
    assert "private@internal" not in "".join(item.model_dump_json() for item in components)
    operations._storage.assert_not_called()


async def test_disabled_native_modules_and_missing_observations_never_become_passed():
    operations = SimpleNamespace(
        sources=SimpleNamespace(all_datasources=lambda: [], datasources=lambda: []),
        health=SimpleNamespace(health=AsyncMock(return_value=HealthStatus(status="UNKNOWN"))),
    )
    records = SimpleNamespace(model_default_configured=AsyncMock(return_value=False))
    native = SimpleNamespace(ingestion=AsyncMock(side_effect=AssertionError("Disabled module was touched")))
    readiness = SimpleNamespace(observe=Mock(return_value=SimpleNamespace(state="disabled")))
    diagnostics = PlatformDiagnostics(
        operations, records, native, readiness, Config({"koinon": {"knowledge": {"enabled": False}}})
    )
    components = await diagnostics.observe("issuer|admin", "north")
    assert not any(item.status == "passed" for item in components)
    assert next(item for item in components if item.id == "indexes-documents").status == "disabled"
    native.ingestion.assert_not_awaited()


async def test_queued_index_reports_incomplete_work_without_calling_it_a_failed_ready_index():
    from koinon.platform.repositories import IndexTarget

    target = IndexTarget("id", "workspace", "native", "set", "documents", "queued", 1536)
    records = SimpleNamespace(index_targets=AsyncMock(return_value=((target,), True)))
    native = SimpleNamespace(indexes=AsyncMock(return_value=False))
    diagnostics = PlatformDiagnostics(SimpleNamespace(), records, native, SimpleNamespace(), Config({}))
    result = await diagnostics._indexes("issuer|admin", "north", "documents")
    assert result.status == "unknown"
    assert result.counts.observed_pending == 1
