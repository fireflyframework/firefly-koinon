# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import asyncio
import json
from types import SimpleNamespace

import pytest
from pyfly.actuator.health import HealthStatus
from pyfly.container.scanner import scan_package
from pyfly.context import ApplicationContext
from pyfly.core import Config
from pyfly.data.relational.health import SqlAlchemyHealthIndicator

from koinon.catalog.entities import Membership, Tenant
from koinon.catalog.errors import AccessDenied
from koinon.catalog.repositories import MembershipRepository, TenantRepository
from koinon.operations.service import OperationsService, storage_roundtrip


@pytest.fixture
async def operations(tmp_path):
    context = ApplicationContext(
        Config(
            {
                "pyfly": {
                    "banner": {"mode": "off"},
                    "eda": {"provider": "memory"},
                    "agentic": {"enabled": True},
                    "data": {
                        "relational": {
                            "enabled": True,
                            "ddl-auto": "create",
                            "pool": {"size": 1, "max-overflow": 0},
                            "url": f"sqlite+aiosqlite:///{tmp_path / 'operations.db'}",
                        }
                    },
                },
                "koinon": {"operations": {"worker_concurrency": 2}},
            }
        )
    )
    for package in ("koinon.catalog", "koinon.operations"):
        scan_package(package, context.container)
    context.container.register_instance(
        SqlAlchemyHealthIndicator, SqlAlchemyHealthIndicator(None), name="other.module.health"
    )
    await context.start()
    try:
        await context.get_bean(TenantRepository).save(Tenant(id="north", name="North"))
        for subject, role in [("issuer|admin", "admin"), ("issuer|viewer", "viewer")]:
            await context.get_bean(MembershipRepository).save(
                Membership(id=subject, subject=subject, tenant_id="north", role=role)
            )
        yield context.get_bean(OperationsService), context
    finally:
        await context.stop()


async def test_native_context_observes_database_without_leaking_connection_or_secret(operations):
    service, context = operations
    result = await service.describe("issuer|admin", "north")
    assert service.health is context.container.resolve_by_name("db_health_indicator")
    assert result["datasources"][0]["available"] is True
    assert result["datasources"][0]["role_policy"]["available"] is None
    assert result["limits"]["worker_concurrency"] == 2
    assert result["metrics"]["available"] is None
    assert result["storage"][0]["configured"] is False
    assert result["indexes"][0]["available"] is None
    assert "sqlite+" not in json.dumps(result) and "operations.db" not in json.dumps(result)


async def test_unknown_child_never_inherits_aggregate_up_or_raw_driver_error(operations, monkeypatch):
    service, _ = operations

    async def health():
        return HealthStatus(
            status="UP",
            details={
                "datasources": {
                    "primary": {
                        "status": "UNKNOWN",
                        "message": "postgresql://private:secret@internal/private",
                    }
                }
            },
        )

    monkeypatch.setattr(service.health, "health", health)
    result = await service.describe("issuer|admin", "north")
    assert result["datasources"][0]["available"] is None
    assert result["datasources"][0]["status"] == "unknown"
    assert "private" not in json.dumps(result) and "secret" not in json.dumps(result)


async def test_authority_precedes_any_operational_probe(operations, monkeypatch):
    service, _ = operations

    async def health():
        pytest.fail("An unauthorized caller must not trigger a probe")

    monkeypatch.setattr(service.health, "health", health)
    for subject, tenant in [("issuer|viewer", "north"), ("issuer|admin", "south")]:
        with pytest.raises(AccessDenied):
            await service.describe(subject, tenant)


async def test_storage_uses_bound_settings_and_cleans_only_probe_file(operations, tmp_path, monkeypatch):
    service, _ = operations
    original = tmp_path / "retained.bin"
    original.write_bytes(b"retained")
    monkeypatch.setattr(
        service,
        "_domain_settings",
        lambda domain: SimpleNamespace(
            object_store_backend="localfs", object_store_localfs_root=str(tmp_path), store_originals=False
        ),
    )
    result = await service._storage("documents")
    assert result["available"] is True and result["store_originals"] is False
    assert original.read_bytes() == b"retained"
    assert not list(tmp_path.glob(".koinon-probe-*"))
    assert str(tmp_path) not in json.dumps(result)
    assert storage_roundtrip(str(tmp_path / "missing")) is False
    assert not (tmp_path / "missing").exists()


async def test_cloud_storage_stays_unknown_without_network_calls(operations, monkeypatch):
    service, _ = operations
    monkeypatch.setattr(
        service,
        "_domain_settings",
        lambda domain: SimpleNamespace(object_store_backend="s3", store_originals=True),
    )
    result = await service._storage("documents")
    assert result["configured"] is True and result["available"] is None
    assert not service._storage_checks


async def test_slow_storage_probe_reuses_bounded_task_and_remains_unknown(operations, tmp_path, monkeypatch):
    service, _ = operations
    monkeypatch.setattr(
        service,
        "_domain_settings",
        lambda domain: SimpleNamespace(
            object_store_backend="localfs", object_store_localfs_root=str(tmp_path), store_originals=True
        ),
    )
    blocker = asyncio.Event()
    task = asyncio.create_task(blocker.wait())
    service._storage_checks[str(tmp_path.absolute())] = (0, task)
    result = await service._storage("documents")
    assert result["available"] is None and not task.done()
    assert len(service._storage_checks) == 1
    blocker.set()
    await task


async def test_actual_exhausted_native_pool_is_unknown_then_recovers(operations, monkeypatch):
    service, _ = operations
    await service.catalog.authorize("issuer|admin", "north", "providers:write")

    async def previously_verified(subject, tenant, permission):
        assert (subject, tenant, permission) == ("issuer|admin", "north", "providers:write")

    monkeypatch.setattr(service.catalog, "authorize", previously_verified)
    async with service.sources.primary.engine.connect():
        report = await service.describe("issuer|admin", "north")
        assert report["datasources"][0]["available"] is None
        assert report["datasources"][0]["status"] == "unknown"
    recovered = await service.describe("issuer|admin", "north")
    assert recovered["datasources"][0]["available"] is True
