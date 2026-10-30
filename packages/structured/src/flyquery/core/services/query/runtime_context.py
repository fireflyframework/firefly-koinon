# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""One operation's query components, borrowing framework-owned resources."""

from dataclasses import dataclass

from pyfly.agentic.types import AgentLike
from sqlalchemy.ext.asyncio import AsyncSession

from flyquery.config import FlyquerySettings
from flyquery.core.services.examples.auto_learner import AutoLearner
from flyquery.core.services.execution.ast_classifier import AstClassifier
from flyquery.core.services.execution.duckdb_executor import DuckDBExecutor
from flyquery.core.services.execution.scope_guard import ScopeGuard
from flyquery.core.services.execution.table_resolver import TableResolver
from flyquery.core.services.query.query_repository import QueryRepository
from flyquery.core.services.query.query_service import QueryService
from flyquery.core.services.query.result_uploader import ResultUploader
from flyquery.core.services.retrieval.hybrid_retriever import HybridRetriever
from flyquery.core.services.retrieval.reranker import Reranker


@dataclass(frozen=True)
class StructuredQueryRuntime:
    session: AsyncSession
    settings: FlyquerySettings
    pipeline: QueryService
    retriever: HybridRetriever
    reranker: Reranker
    table_resolver: TableResolver
    ast_classifier: AstClassifier
    scope_guard: ScopeGuard
    executor: DuckDBExecutor
    query_repository: QueryRepository
    result_uploader: ResultUploader
    auto_learner: AutoLearner
    grounding_agent: AgentLike
    generation_agent: AgentLike
    critic_agent: AgentLike | None
    explainer_agent: AgentLike | None
