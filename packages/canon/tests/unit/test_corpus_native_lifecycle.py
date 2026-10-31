# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""The actual corpus bean must start before the native business-transaction guard."""

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pyfly.agentic.vectorstores import PgVectorVectorStore, TenantScopedVectorStore
from pyfly.container import bean, configuration
from pyfly.container.exceptions import BeanCreationException
from pyfly.context import ApplicationContext
from pyfly.core import Config
from pyfly.data.transaction.context import bind_state, current_state, reset_state
from pyfly.data.transaction.unit_of_work import UnitOfWork

from flycanon.config import CanonSettings
from flycanon.core.configuration import CanonCoreConfiguration
from flycanon.core.services.retrieval.corpus_factory import CorpusContext


def corpus_application(monkeypatch, *, fail_schema=False):
    events, built = [], []
    manager = SimpleNamespace(datasource="canon")

    @asynccontextmanager
    async def begin():
        events.append("schema-unit-open")
        try:
            yield object()
        finally:
            events.append("schema-unit-close")

    engine = SimpleNamespace(dialect=SimpleNamespace(name="postgresql"), begin=begin)
    monkeypatch.setattr("pyfly.data.relational.framework_schema.framework_engine", lambda target: engine)

    def build(*, settings):
        lexical = SimpleNamespace(
            initialise=AsyncMock(side_effect=lambda: events.append("lexical-start")),
            close=AsyncMock(side_effect=lambda: events.append("lexical-close")),
        )
        vectors = PgVectorVectorStore(object(), dimension=8)
        vectors._manager = manager

        async def schema(_connection):
            assert current_state().target("canon") is None
            events.append("vector-schema")
            if fail_schema:
                raise RuntimeError("vector schema prerequisite missing")

        vectors._create_schema = AsyncMock(side_effect=schema)
        value = CorpusContext(lexical, TenantScopedVectorStore(vectors), "pgvector")
        built.append(value)
        return value

    monkeypatch.setattr("flycanon.core.configuration.build_corpus_context", build)

    @configuration
    class Retrieval:
        @bean
        def settings(self) -> CanonSettings:
            return CanonSettings()

        corpus_context = CanonCoreConfiguration.corpus_context

    context = ApplicationContext(Config({}))
    context.register_bean(Retrieval)
    return context, manager, events, built


async def test_actual_corpus_bean_initialises_before_first_native_business_unit(monkeypatch):
    context, manager, events, built = corpus_application(monkeypatch)
    await context.start()
    try:
        value = context.get_bean(CorpusContext)
        assert value is built[0]
        unit = UnitOfWork(manager, "canon", object())
        token = bind_state(current_state().with_binding("canon", unit))
        try:
            # Execute the real native PgVector guard on the same path used by its first upsert.
            await value.vector_store.initialise()
            assert current_state().target("canon") is unit
        finally:
            reset_state(token)
        assert events == ["lexical-start", "schema-unit-open", "vector-schema", "schema-unit-close"]
    finally:
        await context.stop()
    assert events[-1] == "lexical-close"
    assert not value.dense_backend._initialised


async def test_vector_schema_failure_aborts_native_startup_and_releases_created_corpus(monkeypatch):
    context, _manager, events, built = corpus_application(monkeypatch, fail_schema=True)
    with pytest.raises(BeanCreationException, match="vector schema prerequisite missing"):
        await context.start()
    assert events == [
        "lexical-start",
        "schema-unit-open",
        "vector-schema",
        "schema-unit-close",
        "lexical-close",
    ]
    assert not built[0].dense_backend._initialised
    await context.stop()
    assert events.count("lexical-close") == 1


async def test_native_restart_constructs_and_initialises_a_new_corpus_once(monkeypatch):
    context, _manager, events, built = corpus_application(monkeypatch)
    await context.start()
    first = context.get_bean(CorpusContext)
    await context.stop()
    await context.start()
    try:
        second = context.get_bean(CorpusContext)
        assert second is not first and second is built[1]
        assert events.count("vector-schema") == 2
        assert not first.dense_backend._initialised and second.dense_backend._initialised
    finally:
        await context.stop()
    assert events.count("lexical-start") == events.count("lexical-close") == 2
