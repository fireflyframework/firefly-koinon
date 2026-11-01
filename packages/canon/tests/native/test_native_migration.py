# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Behavioral contracts for the canon native application boundary."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[2]


def test_canon_has_no_standalone_agentic_runtime_imports():
    import ast

    legacy = []
    for path in (ROOT / "src").rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("fireflyframework_"):
                legacy.append(f"{path.name}:{node.lineno}")
    assert legacy == []


def test_every_canon_component_and_factory_bean_is_namespaced():
    import ast

    failures = []
    stereotypes = {"configuration", "service", "component", "repository", "rest_controller", "bean"}
    for path in (ROOT / "src").rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if not isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in node.decorator_list:
                target = decorator.func if isinstance(decorator, ast.Call) else decorator
                if not isinstance(target, ast.Name) or target.id not in stereotypes:
                    continue
                kwargs = decorator.keywords if isinstance(decorator, ast.Call) else []
                names = [
                    kw.value.value for kw in kwargs if kw.arg == "name" and isinstance(kw.value, ast.Constant)
                ]
                if not names or not str(names[0]).startswith("canon."):
                    failures.append(f"{path.name}:{node.name}")
    assert failures == []


def test_agent_builder_uses_the_bound_native_factory():
    from flycanon.core.agents import build_agent

    factory = SimpleNamespace(create=MagicMock(return_value=object()))
    settings = SimpleNamespace(_agent_factory=factory, agent_max_output_tokens=8192)
    result = build_agent(
        name="canon-test", model="test", output_type=dict, instructions="test", settings=settings
    )
    assert result is factory.create.return_value
    assert factory.create.call_args.args == ("canon-test",)
    assert factory.create.call_args.kwargs["model_settings"] == {"max_tokens": 8192}


def test_unbound_agent_builder_fails_with_an_actionable_message():
    from flycanon.config import CanonSettings
    from flycanon.core.agents import build_agent

    with pytest.raises(RuntimeError, match="ApplicationContext-owned AgentFactory"):
        build_agent(name="x", model="test", output_type=dict, instructions="", settings=CanonSettings())


def test_vector_store_borrows_a_datasource_and_has_no_owned_pool():
    from flycanon.core.services.retrieval.pgvector_store import RlsPgVectorVectorStore

    datasource = object()
    store = RlsPgVectorVectorStore(datasource=datasource, dimension=128)
    assert store._target is datasource
    assert not hasattr(store, "_pool")
    assert not hasattr(store, "_ensure_pool")


def test_canon_metadata_is_available_without_a_server_boot():
    from flycanon.integration import canon_metadata

    names = set(canon_metadata().tables)
    assert {"canon_sources", "canon_chunks", "canon_workspaces", "canon_knowledge_versions"} <= names


def test_repository_configuration_borrows_the_registered_datasource():
    from flycanon.config import CanonSettings
    from flycanon.core.configuration import CanonCoreConfiguration

    source = SimpleNamespace(sessionmaker=object(), engine=object())
    registry = SimpleNamespace(get=lambda name: source)
    settings = CanonSettings()
    settings.bind_native_resources(SimpleNamespace(), registry)
    repository = CanonCoreConfiguration().source_repository(settings)
    assert repository.engine is source.engine
    assert repository._session_factory is source.sessionmaker


async def test_lexical_corpus_does_not_dispose_the_borrowed_engine():
    from unittest.mock import AsyncMock

    from flycanon.core.services.retrieval.postgres_corpus import PostgresCorpus

    engine = SimpleNamespace(dispose=AsyncMock())
    source = SimpleNamespace(engine=engine)
    corpus = PostgresCorpus(datasource=source)
    assert await corpus._ensure_engine() is engine
    await corpus.close()
    engine.dispose.assert_not_awaited()


async def test_repository_write_joins_and_rolls_back_the_native_unit(repositories):
    from pyfly.data.transaction import TransactionTemplate

    from flycanon.models.entities.source import SourceRow

    repository = repositories["source"]
    row = SourceRow(
        id="native-rollback",
        tenant_id="t",
        workspace_id="w",
        kind="text",
        status="pending",
        content_sha256="rollback",
        metadata_json={},
    )
    with pytest.raises(RuntimeError, match="rollback the business operation"):
        async with TransactionTemplate(repository._session_factory).transaction():
            await repository.add(row)
            raise RuntimeError("rollback the business operation")
    assert await repository.get(row.id, tenant_id="t", workspace_id="w") is None


def test_persistent_agent_adapters_never_silently_fall_back_to_memory():
    from flycanon.config import CanonSettings
    from flycanon.core.configuration import CanonCoreConfiguration

    with pytest.raises(RuntimeError, match="primary"):
        CanonCoreConfiguration().idempotency_store(
            CanonSettings(redis_url="", allow_in_memory_adapters=False)
        )


def test_chroma_requires_a_server_unless_development_memory_is_explicit():
    from flycanon.config import CanonSettings
    from flycanon.core.services.retrieval.corpus_factory import _chroma_client

    with pytest.raises(RuntimeError, match="FLYCANON_CHROMA_HOST"):
        _chroma_client(CanonSettings(chroma_host="", allow_in_memory_adapters=False))


async def test_native_duplicate_key_keeps_the_typed_relation_conflict():
    from unittest.mock import AsyncMock

    from pyfly.kernel import DuplicateKeyException

    from flycanon.core.services.knowledge.relation_service import (
        KnowledgeRelationService,
        RelationConflictError,
    )
    from flycanon.interfaces.dtos.relation import CreateRelationRequest
    from flycanon.interfaces.enums import RelationKind

    service = KnowledgeRelationService(
        knowledge_repository=SimpleNamespace(get_item=AsyncMock(return_value=object())),
        relation_repository=SimpleNamespace(add=AsyncMock(side_effect=DuplicateKeyException("duplicate"))),
        audit=object(),
        event_publisher=None,
        settings=SimpleNamespace(),
    )
    with pytest.raises(RelationConflictError):
        await service.add(
            "a",
            CreateRelationRequest(to_item_id="b", kind=RelationKind.related),
            tenant_id="t",
            workspace_id="w",
        )


async def test_vector_validation_refuses_a_table_without_its_scope_policy():
    from unittest.mock import AsyncMock

    from pyfly.agentic.exceptions import VectorStoreError

    from flycanon.core.services.retrieval.pgvector_store import RlsPgVectorVectorStore

    store = RlsPgVectorVectorStore(datasource="canon", dimension=128, create_schema=False)
    connection = AsyncMock()
    connection.fetch.return_value = [{"column_type": "vector", "has_set_id": True, "has_policy": False}]
    with pytest.raises(VectorStoreError, match="scope policy"):
        await store._create_schema(connection)
    connection.execute.assert_not_awaited()
