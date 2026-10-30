# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Native query composition must be reusable without an HTTP controller."""

import asyncio
import importlib

import pytest
from pyfly.core import Config
from pyfly.data.relational.datasource_registry import DataSourceRegistry
from pyfly.data.transaction import TransactionTemplate
from sqlalchemy import text

from flyquery.config import FlyquerySettings
from flyquery.core.services.execution.ast_classifier import AstClassifier
from flyquery.core.services.execution.scope_guard import ScopeGuard
from flyquery.core.services.query.query_service import QueryService
from flyquery.core.services.retrieval.reranker import LexicalReranker
from flyquery.data import StructuredSessionBinding


def runtime_module():
    module = "flyquery.core.services.query.runtime"
    assert importlib.util.find_spec(module) is not None, "A managed query runtime is required outside HTTP"
    return importlib.import_module(module)


def make_factory(module, sessions, monkeypatch, *, settings=None):
    built = []

    def agent(selected):
        built.append(selected)
        return object()

    for name in (
        "build_grounding_agent",
        "build_generation_agent",
        "build_critic_agent",
        "build_explainer_agent",
    ):
        monkeypatch.setattr(module, name, agent)
    factory = module.StructuredQueryRuntimeFactory(
        settings=settings or FlyquerySettings(max_refine_retries=2),
        sessions=StructuredSessionBinding(sessions),
        object_store=object(),
        query_repository=object(),
        semantic_repository=object(),
        examples_service=object(),
        embedder=object(),
        reranker=LexicalReranker(),
        ast_classifier=AstClassifier(),
        scope_guard=ScopeGuard(),
        executor=object(),
        table_repository=object(),
        conversation_service=object(),
    )
    return factory, built


@pytest.mark.parametrize("failure", [RuntimeError, asyncio.CancelledError])
async def test_runtime_joins_named_native_transaction_and_preserves_rollback(tmp_path, monkeypatch, failure):
    module = runtime_module()
    registry = DataSourceRegistry(
        Config(
            {
                "pyfly": {
                    "data": {
                        "relational": {
                            "url": f"sqlite+aiosqlite:///{tmp_path / 'primary.db'}",
                            "datasources": {
                                "structured": {"url": f"sqlite+aiosqlite:///{tmp_path / 'structured.db'}"}
                            },
                        }
                    }
                }
            }
        )
    )
    customizations = []

    class MarkStructuredUnit:
        async def after_begin(self, connection, datasource):
            customizations.append(datasource.name)
            await connection.execute(text("PRAGMA user_version = 37"))

    registry.add_customizer(MarkStructuredUnit(), datasource="structured")
    source = registry.get("structured")
    async with source.engine.begin() as connection:
        await connection.execute(text("CREATE TABLE query_markers (value TEXT)"))
    factory, _ = make_factory(module, source.sessionmaker, monkeypatch)
    try:
        with pytest.raises(failure):
            async with (
                TransactionTemplate(source).transaction() as outer,
                factory.unit() as runtime,
            ):
                assert runtime.session is outer.resource
                assert await runtime.session.scalar(text("PRAGMA user_version")) == 37
                await runtime.session.execute(text("INSERT INTO query_markers VALUES ('pending')"))
                raise failure("query failed")
        async with source.sessionmaker() as session:
            assert await session.scalar(text("SELECT count(*) FROM query_markers")) == 0
        assert customizations == ["structured"]
    finally:
        await registry.close()


async def test_per_call_policy_is_scoped_and_managed_collaborators_are_preserved(tmp_path, monkeypatch):
    module = runtime_module()
    registry = DataSourceRegistry(
        Config(
            {
                "pyfly": {
                    "data": {
                        "relational": {
                            "url": f"sqlite+aiosqlite:///{tmp_path / 'runtime.db'}",
                        }
                    }
                }
            }
        )
    )
    baseline = FlyquerySettings(rrf_k=60, max_refine_retries=2)
    factory, built = make_factory(module, registry.primary.sessionmaker, monkeypatch, settings=baseline)
    try:
        async with factory.unit(settings_overrides={"rrf_k": 91, "max_refine_retries": 0}) as first:
            assert first.settings.rrf_k == 91 and first.critic_agent is None
            assert first.pipeline._executor is first.executor is factory._executor
            assert first.pipeline._scope_guard is first.scope_guard is factory._scope_guard
            assert built and all(value is first.settings for value in built)
        built.clear()
        async with factory.unit() as second:
            assert second.settings.rrf_k == 60 and second.critic_agent is not None
            assert built and all(value is second.settings for value in built)
        assert baseline.rrf_k == 60 and baseline.max_refine_retries == 2
    finally:
        await registry.close()


async def test_query_service_reads_table_kinds_through_repository_not_resolver_session():
    class ForbiddenResolverSession:
        @property
        def _session(self):
            raise AssertionError("The application service must not reach into resolver sessions")

    class TableKinds:
        async def list_kinds_for_dataset_by_names(self, dataset_id, names):
            assert str(dataset_id) == "dataset" and names == ["orders"]
            return [{"name": "orders", "kind": "BASE"}]

    service = object.__new__(QueryService)
    service._table_resolver = ForbiddenResolverSession()
    service._table_repo = TableKinds()
    assert await service._table_kinds_by_name(["orders"], "dataset") == {"orders": "BASE"}


async def test_native_container_injects_runtime_and_honors_managed_dependency_override(tmp_path, monkeypatch):
    from pyfly.container import Container

    from flyquery.core.services.auth.agent_token_service import AgentTokenService
    from flyquery.core.services.derived.derived_table_service import DerivedTableService
    from flyquery.core.services.examples.examples_service import ExamplesService
    from flyquery.core.services.execution.duckdb_executor import DuckDBExecutor
    from flyquery.core.services.query.conversation_service import ConversationService
    from flyquery.core.services.query.query_repository import QueryRepository
    from flyquery.core.services.retrieval.embedder import Embedder
    from flyquery.core.services.retrieval.reranker import Reranker
    from flyquery.core.services.semantic.semantic_repository import SemanticRepository
    from flyquery.core.services.storage.object_store import ObjectStore
    from flyquery.core.services.tables.schema_snapshot_repository import SchemaSnapshotRepository
    from flyquery.core.services.tables.table_repository import TableRepository
    from flyquery.core.services.workspaces.workspace_service import WorkspaceService
    from flyquery.web.controllers.agent.sql_execute_controller import AgentSqlExecuteController
    from flyquery.web.controllers.query_controller import QueryController
    from flyquery.web.controllers.sql_execute_controller import SqlExecuteController
    from flyquery.web.conventions import IdempotencyStore

    module = runtime_module()
    registry = DataSourceRegistry(
        Config(
            {
                "pyfly": {
                    "data": {
                        "relational": {
                            "url": f"sqlite+aiosqlite:///{tmp_path / 'native.db'}",
                        }
                    }
                }
            }
        )
    )
    template, _ = make_factory(module, registry.primary.sessionmaker, monkeypatch)
    container = Container()
    dependencies = {
        FlyquerySettings: template._settings,
        ObjectStore: template._object_store,
        QueryRepository: template._query_repository,
        SemanticRepository: template._semantic_repository,
        ExamplesService: template._examples_service,
        Embedder: template._embedder,
        Reranker: template._reranker,
        AstClassifier: template._ast_classifier,
        ScopeGuard: template._scope_guard,
        DuckDBExecutor: template._executor,
        TableRepository: template._table_repository,
        ConversationService: template._conversation_service,
        IdempotencyStore: object(),
        WorkspaceService: object(),
        SchemaSnapshotRepository: object(),
        AgentTokenService: object(),
    }
    for kind, value in dependencies.items():
        container.register_instance(kind, value)
    container.register_instance(
        StructuredSessionBinding,
        StructuredSessionBinding(registry.primary.sessionmaker),
        name="structured.sessions",
    )
    container.register(module.StructuredQueryRuntimeFactory)
    container.register(QueryController)
    container.register(SqlExecuteController)
    container.register(AgentSqlExecuteController)
    container.register(DerivedTableService)
    try:
        factory = container.resolve(module.StructuredQueryRuntimeFactory)
        controller = container.resolve(QueryController)
        assert controller._runtime_factory is factory
        sql_controller = container.resolve(SqlExecuteController)
        assert container.resolve(AgentSqlExecuteController)._delegate is sql_controller
        assert sql_controller._executor is dependencies[DuckDBExecutor]
        assert container.resolve(DerivedTableService)._executor is dependencies[DuckDBExecutor]
        async with factory.unit(preview=True) as runtime:
            assert runtime.executor is dependencies[DuckDBExecutor]
            assert runtime.reranker is dependencies[Reranker]
            assert runtime.critic_agent is None and runtime.explainer_agent is None
            assert runtime.pipeline._conversation_service is None
        async with factory.unit(with_conversation=True) as runtime:
            assert runtime.pipeline._conversation_service is dependencies[ConversationService]
    finally:
        await registry.close()


async def test_http_query_uses_the_same_native_unit_for_pipeline_side_effects(tmp_path, monkeypatch):
    import uuid

    from pyfly.data.transaction import infrastructure_unit
    from starlette.requests import Request

    from flyquery.interfaces.query import QueryRequest
    from flyquery.web.controllers.query_controller import QueryController

    module = runtime_module()
    registry = DataSourceRegistry(
        Config(
            {
                "pyfly": {
                    "data": {
                        "relational": {
                            "url": f"sqlite+aiosqlite:///{tmp_path / 'http.db'}",
                        }
                    }
                }
            }
        )
    )
    source = registry.primary
    workspace, dataset = uuid.uuid4(), uuid.uuid4()
    async with source.engine.begin() as connection:
        await connection.execute(text("CREATE TABLE query_markers (value TEXT)"))
    factory, _ = make_factory(module, source.sessionmaker, monkeypatch)

    class FailingPipeline:
        def __init__(self, **dependencies):
            assert dependencies["scope_guard"] is factory._scope_guard

        async def answer(self, **arguments):
            assert arguments["workspace_id"] == workspace and arguments["dataset_id"] == dataset
            assert arguments["scopes"] == {"flyquery.query:read"}
            async with infrastructure_unit(source.sessionmaker) as session:
                await session.execute(text("INSERT INTO query_markers VALUES ('pending result')"))
            raise RuntimeError("execution failed")

    monkeypatch.setattr(module, "QueryService", FailingPipeline)
    controller = QueryController(factory, object())
    request = Request(
        {
            "type": "http",
            "headers": [
                (b"x-tenant-id", b"tenant"),
                (b"x-workspace-id", str(workspace).encode()),
            ],
        }
    )
    try:
        with pytest.raises(RuntimeError, match="execution failed"):
            await controller.query(request, QueryRequest(dataset_id=dataset, question="How many orders?"))
        async with source.sessionmaker() as session:
            assert await session.scalar(text("SELECT count(*) FROM query_markers")) == 0
    finally:
        await registry.close()


async def test_stream_disconnect_closes_its_native_unit_once_and_rolls_back(tmp_path, monkeypatch):
    import uuid
    from contextlib import asynccontextmanager
    from types import SimpleNamespace

    from pyfly.data.transaction import infrastructure_unit

    from flyquery.interfaces.query import QueryRequest
    from flyquery.web.controllers.query_controller import QueryController

    module = runtime_module()
    registry = DataSourceRegistry(
        Config(
            {
                "pyfly": {
                    "data": {
                        "relational": {
                            "url": f"sqlite+aiosqlite:///{tmp_path / 'stream.db'}",
                        }
                    }
                }
            }
        )
    )
    source = registry.primary
    async with source.engine.begin() as connection:
        await connection.execute(text("CREATE TABLE query_markers (value TEXT)"))
    factory, _ = make_factory(module, source.sessionmaker, monkeypatch)
    closed = []
    original_unit = factory.unit

    @asynccontextmanager
    async def observed_unit(**kwargs):
        try:
            async with original_unit(**kwargs) as runtime:
                yield runtime
        finally:
            closed.append(True)

    class Retriever:
        def __init__(self, *args, **kwargs):
            pass

        async def retrieve(self, *args, **kwargs):
            async with infrastructure_unit(source.sessionmaker) as session:
                await session.execute(text("INSERT INTO query_markers VALUES ('pending stream')"))
            return {}

    class Grounding:
        async def run(self, prompt):
            return SimpleNamespace(path="SYNTHESIS", confidence=0.9, tables=[], missing_info=None)

    monkeypatch.setattr(module, "HybridRetriever", Retriever)
    monkeypatch.setattr(module, "build_grounding_agent", lambda settings: Grounding())
    monkeypatch.setattr(factory, "unit", observed_unit)
    stream = QueryController(factory, object())._stream_events(
        tenant_id="tenant",
        workspace_id=uuid.uuid4(),
        request=QueryRequest(dataset_id=uuid.uuid4(), question="How many orders?"),
    )
    try:
        assert (await anext(stream)).startswith(b"event: schema_linked")
        assert not closed
        await stream.aclose()
        assert closed == [True]
        async with source.sessionmaker() as session:
            assert await session.scalar(text("SELECT count(*) FROM query_markers")) == 0
    finally:
        await stream.aclose()
        await registry.close()
