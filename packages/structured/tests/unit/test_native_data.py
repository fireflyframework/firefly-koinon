# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Native datasource ownership, transactional rollback and provisioning contracts."""

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


def test_settings_and_token_factory_borrow_explicit_named_datasources():
    from flyquery.config import FlyquerySettings
    from flyquery.core.configuration import FlyqueryConfiguration

    runtime = SimpleNamespace(sessionmaker=object(), engine=object())
    admin = SimpleNamespace(sessionmaker=object(), engine=object())
    sources = {"structured": runtime, "structured_admin": admin}
    settings = FlyquerySettings()
    settings.bind_native_resources(SimpleNamespace(), SimpleNamespace(get=sources.__getitem__))
    configuration = FlyqueryConfiguration()
    assert configuration.sessions(settings).sessionmaker is runtime.sessionmaker
    assert configuration.admin_sessions(settings).sessionmaker is admin.sessionmaker
    tokens = configuration.agent_token_repository(settings)
    assert tokens._factory is runtime.sessionmaker
    assert tokens.engine is runtime.engine


async def test_repository_write_rolls_back_with_outer_native_transaction(tmp_path):
    from pyfly.data.transaction import TransactionTemplate

    from flyquery.core.services.ops.cost_event_repository import CostEventRepository

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'rollback.db'}")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.execute(text("CREATE TABLE flyquery_cost_events (id TEXT, created_at TEXT)"))
        await connection.execute(text("INSERT INTO flyquery_cost_events VALUES ('retained', '2025-01-01')"))
    repository = CostEventRepository(sessions)
    try:
        with pytest.raises(RuntimeError, match="outer operation failed"):
            async with TransactionTemplate(sessions).transaction():
                assert await repository.delete_older_than(cutoff=datetime(2026, 1, 1, tzinfo=UTC)) == 1
                raise RuntimeError("outer operation failed")
        async with sessions() as session:
            assert await session.scalar(text("SELECT count(*) FROM flyquery_cost_events")) == 1
    finally:
        await engine.dispose()


async def test_workspace_provision_uses_admin_repository_and_preallocated_uuid():
    from unittest.mock import AsyncMock

    from flyquery.core.services.workspaces.workspace_service import WorkspaceService

    identifier = uuid4()
    runtime = SimpleNamespace(create=AsyncMock())
    admin = SimpleNamespace(provision=AsyncMock(return_value={"id": identifier, "tenant_id": "north"}))
    service = WorkspaceService(runtime, admin)
    result = await service.provision(
        tenant_id="north", workspace_id=identifier, name="Evidence", slug=str(identifier)
    )
    assert result["id"] == identifier
    admin.provision.assert_awaited_once_with(
        tenant_id="north", workspace_id=identifier, name="Evidence", slug=str(identifier)
    )
    runtime.create.assert_not_awaited()


def test_unbound_registry_fails_with_an_actionable_message():
    from flyquery.config import FlyquerySettings

    with pytest.raises(RuntimeError, match="ApplicationContext-owned DataSourceRegistry"):
        FlyquerySettings().native_datasource()


def test_native_container_qualifies_runtime_and_admin_away_from_primary():
    from pyfly.container import Container

    from flyquery.core.services.datasets.dataset_repository import DatasetRepository
    from flyquery.core.services.workspaces.workspace_repository import WorkspaceAdminRepository
    from flyquery.data import StructuredSessionBinding

    container = Container()
    primary, runtime, admin = object(), object(), object()
    for name, value in (
        ("primary.sessions", primary),
        ("structured.sessions", runtime),
        ("structured.admin_sessions", admin),
    ):
        container.register_instance(StructuredSessionBinding, StructuredSessionBinding(value), name=name)
    container.register(DatasetRepository)
    container.register(WorkspaceAdminRepository)
    assert container.resolve(DatasetRepository)._factory is runtime
    assert container.resolve(WorkspaceAdminRepository)._factory is admin


async def test_ingest_worker_binds_event_scope_and_refuses_unscoped_events():
    from unittest.mock import AsyncMock

    from pyfly.kernel import InvalidRequestException

    from flyquery.core.services.ingestion.workers import IngestWorker
    from flyquery.web.conventions.context import current_tenant_context

    worker = IngestWorker.__new__(IngestWorker)

    async def handle(envelope):
        context = current_tenant_context()
        assert context.tenant_id == "north" and context.workspace_id == "workspace"
        assert context.actor == "system:structured-worker"

    worker._handle_scoped = AsyncMock(side_effect=handle)
    await worker._handle_ingest_requested(
        SimpleNamespace(payload={"tenant_id": "north", "workspace_id": "workspace", "job_id": str(uuid4())})
    )
    assert current_tenant_context() is None
    with pytest.raises(InvalidRequestException, match="tenant/workspace"):
        await worker._handle_ingest_requested(SimpleNamespace(payload={"job_id": str(uuid4())}))
    assert worker._handle_scoped.await_count == 1


async def test_ingest_worker_rejects_a_job_that_disagrees_with_event_scope():
    from unittest.mock import AsyncMock

    from pyfly.kernel import InvalidRequestException

    from flyquery.core.services.ingestion.workers import IngestWorker
    from flyquery.web.conventions.context import current_tenant_context

    workspace = str(uuid4())
    worker = IngestWorker.__new__(IngestWorker)
    worker._load_job = AsyncMock(
        return_value={"tenant_id": "south", "workspace_id": workspace, "job_kind": "INGEST"}
    )
    worker._mark_running = AsyncMock()
    with pytest.raises(InvalidRequestException, match="disagrees"):
        await worker._handle_ingest_requested(
            SimpleNamespace(payload={"tenant_id": "north", "workspace_id": workspace, "job_id": str(uuid4())})
        )
    worker._mark_running.assert_not_awaited()
    assert current_tenant_context() is None


def test_transaction_guc_hook_uses_only_bound_validated_scope(monkeypatch):
    from unittest.mock import MagicMock

    from flyquery.data import workspace_scope
    from flyquery.web.conventions import db

    callbacks = []
    monkeypatch.setattr(db.install_tenant_guc_hook, "_installed", False, raising=False)

    def register(*args):
        def capture(callback):
            callbacks.append(callback)
            return callback

        return capture

    monkeypatch.setattr(db.event, "listens_for", register)
    db.install_tenant_guc_hook()
    connection = SimpleNamespace(dialect=SimpleNamespace(name="postgresql"), execute=MagicMock())
    callbacks[0](None, None, connection)
    connection.execute.assert_not_called()
    with workspace_scope("trusted-tenant", "trusted-workspace"):
        callbacks[0](None, None, connection)
    statements = [str(call.args[0]) for call in connection.execute.call_args_list]
    assert statements == [
        "SET LOCAL app.tenant_id = 'trusted-tenant'",
        "SET LOCAL app.workspace_id = 'trusted-workspace'",
    ]


async def test_workspace_creation_uses_control_plane_and_keeps_original_defaults():
    from unittest.mock import AsyncMock

    from flyquery.core.services.workspaces.workspace_service import WorkspaceService
    from flyquery.interfaces.workspaces import WorkspaceCreate

    runtime = SimpleNamespace(create=AsyncMock())
    admin = SimpleNamespace(create=AsyncMock(side_effect=lambda **fields: fields))
    result = await WorkspaceService(runtime, admin).create(
        "north", WorkspaceCreate(slug="evidence", name="Evidence")
    )
    assert result["tenant_id"] == "north" and result["allow_direct_sql"] is False
    admin.create.assert_awaited_once()
    runtime.create.assert_not_awaited()


async def test_retention_enumerates_control_plane_scopes_but_sweeps_with_runtime_context():
    from unittest.mock import AsyncMock

    from flyquery.core.services.retention.retention_worker import RetentionWorker
    from flyquery.web.conventions.context import current_tenant_context

    scopes = [{"tenant_id": "north", "id": "workspace-one"}, {"tenant_id": "south", "id": "workspace-two"}]
    worker = RetentionWorker.__new__(RetentionWorker)
    worker._workspace_admin = SimpleNamespace(scopes=AsyncMock(return_value=scopes))
    admitted = []

    async def sweep():
        context = current_tenant_context()
        admitted.append((context.tenant_id, context.workspace_id))
        return {"ingest_events_deleted": 1}

    worker._run_scoped = AsyncMock(side_effect=sweep)
    result = await worker.run_once()
    assert admitted == [("north", "workspace-one"), ("south", "workspace-two")]
    assert result["ingest_events_deleted"] == 2
    assert current_tenant_context() is None


async def test_callback_refuses_foreign_row_before_external_delivery():
    from flyquery.core.services.callbacks.callback_worker import CallbackWorker
    from flyquery.data import workspace_scope

    worker = CallbackWorker.__new__(CallbackWorker)
    with workspace_scope("north", "workspace"), pytest.raises(RuntimeError, match="scope"):
        await worker._dispatch(None, {"tenant_id": "south", "workspace_id": "workspace"})


async def test_legacy_token_url_constructor_cannot_create_an_unmanaged_engine():
    from flyquery.models.repositories.agent_token_repository import AgentTokenRepository

    repository = None
    try:
        with pytest.raises(RuntimeError, match="DataSourceRegistry"):
            repository = AgentTokenRepository.from_url("sqlite+aiosqlite:///:memory:")
    finally:
        if repository is not None:
            await repository.engine.dispose()


async def test_named_session_beans_do_not_replace_the_native_primary(tmp_path):
    from pyfly.container import bean, configuration
    from pyfly.context import ApplicationContext
    from pyfly.core import Config
    from pyfly.data.relational.datasource_registry import DataSourceRegistry
    from pyfly.data.transaction import infrastructure_unit

    from flyquery.config import FlyquerySettings
    from flyquery.core.configuration import FlyqueryConfiguration

    @configuration
    class Sources:
        @bean
        def settings(self, registry: DataSourceRegistry) -> FlyquerySettings:
            settings = FlyquerySettings()
            settings.bind_native_resources(SimpleNamespace(), registry)
            return settings

        sessions = FlyqueryConfiguration.sessions
        admin_sessions = FlyqueryConfiguration.admin_sessions
        tenant_guc_customizer = FlyqueryConfiguration.tenant_guc_customizer

    context = ApplicationContext(
        Config(
            {
                "pyfly": {
                    "data": {
                        "relational": {
                            "enabled": True,
                            "ddl-auto": "none",
                            "url": f"sqlite+aiosqlite:///{tmp_path / 'primary.db'}",
                            "datasources": {
                                name: {"url": f"sqlite+aiosqlite:///{tmp_path / (name + '.db')}"}
                                for name in ("structured", "structured_admin")
                            },
                        }
                    }
                }
            }
        )
    )
    context.register_bean(Sources)
    await context.start()
    try:
        registry = context.get_bean(DataSourceRegistry)
        assert len(registry.get("structured").customizers) == 1
        assert not registry.primary.customizers and not registry.get("structured_admin").customizers
        async with infrastructure_unit() as session:
            rows = (await session.execute(text("PRAGMA database_list"))).all()
            assert rows[0][2].endswith("/primary.db")
    finally:
        await context.stop()
