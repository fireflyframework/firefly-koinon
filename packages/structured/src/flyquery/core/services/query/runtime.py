# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Framework-managed query composition shared by HTTP, streams and headless calls."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from pyfly.container import service
from pyfly.data.transaction import current_unit_of_work, infrastructure_unit
from pyfly.kernel import ServiceUnavailableException

from flyquery.config import FlyquerySettings
from flyquery.core.agents.critic_agent import build_critic_agent
from flyquery.core.agents.explainer_agent import build_explainer_agent
from flyquery.core.agents.generation_agent import build_generation_agent
from flyquery.core.agents.grounding_agent import build_grounding_agent
from flyquery.core.services.examples.auto_learner import AutoLearner
from flyquery.core.services.examples.examples_service import ExamplesService
from flyquery.core.services.execution.ast_classifier import AstClassifier
from flyquery.core.services.execution.duckdb_executor import DuckDBExecutor
from flyquery.core.services.execution.scope_guard import ScopeGuard
from flyquery.core.services.execution.table_resolver import ProductTableResolver, TableResolver
from flyquery.core.services.query.conversation_service import ConversationService, ProductConversation
from flyquery.core.services.query.query_repository import QueryRepository
from flyquery.core.services.query.query_service import QueryService
from flyquery.core.services.query.result_uploader import ResultUploader
from flyquery.core.services.query.runtime_context import StructuredQueryRuntime
from flyquery.core.services.retrieval.embedder import Embedder
from flyquery.core.services.retrieval.hybrid_retriever import HybridRetriever
from flyquery.core.services.retrieval.reranker import Reranker
from flyquery.core.services.retrieval.search_index import ProductSearchIndex, SearchIndex
from flyquery.core.services.semantic.semantic_repository import SemanticRepository
from flyquery.core.services.storage.object_store import ObjectStore
from flyquery.core.services.tables.table_repository import TableRepository
from flyquery.data import StructuredSessions, unwrap_sessions


@service(name="structured.StructuredQueryRuntimeFactory")
class StructuredQueryRuntimeFactory:
    def __init__(
        self,
        settings: FlyquerySettings,
        sessions: StructuredSessions,
        object_store: ObjectStore,
        query_repository: QueryRepository,
        semantic_repository: SemanticRepository,
        examples_service: ExamplesService,
        embedder: Embedder,
        reranker: Reranker,
        ast_classifier: AstClassifier,
        scope_guard: ScopeGuard,
        executor: DuckDBExecutor,
        table_repository: TableRepository,
        conversation_service: ConversationService,
    ) -> None:
        self._settings = settings
        self._sessions = unwrap_sessions(sessions)
        self._object_store = object_store
        self._query_repository = query_repository
        self._semantic_repository = semantic_repository
        self._examples_service = examples_service
        self._embedder = embedder
        self._reranker = reranker
        self._ast_classifier = ast_classifier
        self._scope_guard = scope_guard
        self._executor = executor
        self._table_repository = table_repository
        self._conversation_service = conversation_service

    @asynccontextmanager
    async def operation(
        self,
        *,
        settings_overrides: dict[str, object] | None = None,
        with_conversation: bool = False,
        preview: bool = False,
    ) -> AsyncIterator[StructuredQueryRuntime]:
        """Compose a product operation without retaining a database unit."""
        for name in (None, "primary", "canon", "structured"):
            unit = current_unit_of_work(name)
            if unit is not None and not unit.completed:
                raise ServiceUnavailableException(
                    "A product query cannot join an ambient transaction", code="QUERY_UNIT_INVALID"
                )
        runtime = self._compose(
            None,
            settings_overrides=settings_overrides,
            with_conversation=with_conversation,
            preview=preview,
        )
        yield runtime

    @asynccontextmanager
    async def unit(
        self,
        *,
        settings_overrides: dict[str, object] | None = None,
        with_conversation: bool = False,
        preview: bool = False,
    ) -> AsyncIterator[StructuredQueryRuntime]:
        """Borrow a native unit and compose one operation inside its model bindings.

        Callers provide validated organization policy overrides. No singleton
        settings or resource ownership changes. Conversation context remains
        opt-in for the existing agent and conversation entry points.
        """
        from flyquery.core.services.query.provenance import reject_product_legacy

        reject_product_legacy()
        async with infrastructure_unit(self._sessions) as session:
            yield self._compose(
                session,
                settings_overrides=settings_overrides,
                with_conversation=with_conversation,
                preview=preview,
            )

    def _compose(self, session, *, settings_overrides, with_conversation, preview):
        settings = (
            self._settings.model_copy(update=settings_overrides) if settings_overrides else self._settings
        )
        index = ProductSearchIndex(self._sessions) if session is None else SearchIndex(session)
        retriever = HybridRetriever(index, self._embedder, rrf_k=settings.rrf_k)
        resolver = (
            ProductTableResolver(self._sessions, settings)
            if session is None
            else TableResolver(session, settings)
        )
        uploader = ResultUploader(self._object_store, self._query_repository, settings)
        learner = AutoLearner(examples_service=self._examples_service)
        grounding = build_grounding_agent(settings)
        generation = build_generation_agent(settings)
        critic = build_critic_agent(settings) if not preview and settings.max_refine_retries > 0 else None
        explainer = build_explainer_agent(settings) if not preview else None
        pipeline = QueryService(
            retriever=retriever,
            reranker=self._reranker,
            grounding_agent=grounding,
            generation_agent=generation,
            critic_agent=critic,
            explainer_agent=explainer,
            ast_classifier=self._ast_classifier,
            scope_guard=self._scope_guard,
            table_resolver=resolver,
            executor=self._executor,
            query_repo=self._query_repository,
            settings=settings,
            result_uploader=uploader,
            auto_learner=learner,
            semantic_repo=index if session is None else self._semantic_repository,
            conversation_service=(
                ProductConversation(self._sessions, self._conversation_service)
                if session is None
                else self._conversation_service
            )
            if with_conversation
            else None,
            table_repository=resolver if session is None else self._table_repository,
        )
        return StructuredQueryRuntime(
            session=session,
            settings=settings,
            pipeline=pipeline,
            retriever=retriever,
            reranker=self._reranker,
            table_resolver=resolver,
            ast_classifier=self._ast_classifier,
            scope_guard=self._scope_guard,
            executor=self._executor,
            query_repository=self._query_repository,
            result_uploader=uploader,
            auto_learner=learner,
            grounding_agent=grounding,
            generation_agent=generation,
            critic_agent=critic,
            explainer_agent=explainer,
        )
