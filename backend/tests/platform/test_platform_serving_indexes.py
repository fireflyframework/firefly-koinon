# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pyfly.context import ApplicationContext
from pyfly.core import Config
from pyfly.data.relational.datasource_registry import DataSourceRegistry
from pyfly.data.transaction import current_unit_of_work
from sqlalchemy import text

from koinon.knowledge.indexes.adapters import index_id
from koinon.platform.diagnostics import PlatformDiagnostics
from koinon.platform.mappers import counts
from koinon.platform.native import PlatformNativeObservations
from koinon.platform.repositories import IndexTarget, StatusWindow


@pytest.mark.parametrize("domain", ["documents", "structured"])
@pytest.mark.parametrize(
    "case,expected",
    [
        ("ready-without-activation", False),
        ("retired-only", False),
        ("metadata-active-native-inactive", False),
        ("active-and-retired", True),
        ("active-in-one-workspace-retired-in-another", False),
    ],
)
async def test_serving_verdict_requires_current_active_target_in_every_observed_workspace(
    tmp_path, domain, case, expected
):
    native = "canon" if domain == "documents" else "structured"
    context = ApplicationContext(
        Config(
            {
                "pyfly": {
                    "banner": {"mode": "off"},
                    "data": {
                        "relational": {
                            "enabled": True,
                            "ddl-auto": "none",
                            "url": f"sqlite+aiosqlite:///{tmp_path / 'primary.db'}",
                            "datasources": {native: {"url": f"sqlite+aiosqlite:///{tmp_path / 'native.db'}"}},
                        }
                    },
                }
            }
        )
    )
    await context.start()
    try:
        status = (
            "ready"
            if case == "ready-without-activation"
            else "retired"
            if case == "retired-only"
            else "active"
        )
        target = IndexTarget("id", "workspace", "native-workspace", "set", domain, status, 1536)
        selected = [target]
        values = {
            index_id("north", "workspace", domain, "set"): {
                "status": status,
                "active": status == "active" and case != "metadata-active-native-inactive",
                "indexed": True,
                "chunk_count": 4,
                "vector_count": 4,
                "dimensions": 1536,
            }
        }
        if case in {"active-and-retired", "active-in-one-workspace-retired-in-another"}:
            workspace = "other" if case.endswith("another") else "workspace"
            selected.append(
                IndexTarget("retired", workspace, "native-workspace", "old", domain, "retired", 1536)
            )
            values[index_id("north", workspace, domain, "old")] = {
                "status": "retired",
                "active": False,
                "indexed": False,
                "chunk_count": 9,
                "vector_count": 0,
                "dimensions": 1536,
            }
        calls = []

        class Adapter:
            async def get_native(self, **arguments):
                unit = current_unit_of_work(native)
                assert unit.read_only and unit.read_from_primary
                assert await unit.resource.scalar(text("SELECT 1")) == 1
                calls.append(arguments["identifier"])
                return values[arguments["identifier"]]

        helper = PlatformNativeObservations(
            SimpleNamespace(), SimpleNamespace(get=lambda: Adapter()), context.get_bean(DataSourceRegistry)
        )
        assert await helper.indexes("issuer|admin", "north", tuple(selected)) is expected
        records = SimpleNamespace(index_targets=AsyncMock(return_value=(tuple(selected), True)))
        diagnostics = PlatformDiagnostics(SimpleNamespace(), records, helper, SimpleNamespace(), Config({}))
        result = await diagnostics._indexes("issuer|admin", "north", domain)
        assert (result.status == "passed") is expected
        if case == "active-and-retired":
            assert set(calls) == {index_id("north", "workspace", domain, "set")}
    finally:
        await context.stop()


def test_retired_and_intentionally_cancelled_records_are_not_ready_or_failed():
    value = counts(StatusWindow(("retired", "cancelled", "failed", "ready", "active"), True))
    assert value.observed_total == 5 and value.observed_ready == 2 and value.observed_failed == 1


async def test_cancelled_ingestion_is_stopped_work_without_a_platform_failure():
    native = SimpleNamespace(ingestion=AsyncMock(return_value=StatusWindow(("cancelled",), True)))
    diagnostics = PlatformDiagnostics(
        SimpleNamespace(), SimpleNamespace(), native, SimpleNamespace(), Config({})
    )
    result = await diagnostics._ingestion("issuer|admin", "north", "documents")
    assert result.status == "unknown" and result.reason == "INGESTION_STATE_OBSERVED"
    assert result.counts.observed_total == 1 and result.counts.observed_failed == 0
