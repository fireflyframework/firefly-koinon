# Copyright 2024-2026 Firefly Software Foundation
# Modifications Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""DI configuration bean for flyquery."""

from __future__ import annotations

from pyfly.agentic.factory import AgentFactory
from pyfly.cache import CacheAdapter
from pyfly.container import bean, configuration
from pyfly.core import Config
from pyfly.data.relational.datasource_registry import DataSourceRegistry

from flyquery.config import FlyquerySettings
from flyquery.core.services.auth.agent_token_service import (
    AgentTokenService,
    RateLimiter,
    _RateLimiter,
)
from flyquery.core.services.auth.postgres_rate_limiter import PostgresRateLimiter
from flyquery.core.services.cache_support import cache_backend
from flyquery.core.services.execution.ast_classifier import AstClassifier
from flyquery.core.services.execution.duckdb_executor import DuckDBExecutor
from flyquery.core.services.execution.scope_guard import ScopeGuard
from flyquery.core.services.retrieval.embedder import Embedder, build_embedder
from flyquery.core.services.retrieval.reranker import Reranker, build_reranker
from flyquery.core.services.storage.object_store import ObjectStore
from flyquery.core.services.storage.object_store_factory import build_object_store
from flyquery.core.services.workspaces.workspace_repository import (
    WorkspaceAdminRepository,
    WorkspaceRepository,
)
from flyquery.core.services.workspaces.workspace_service import WorkspaceService
from flyquery.data import StructuredSessionBinding, TenantGucCustomizer
from flyquery.models.repositories.agent_token_repository import AgentTokenRepository
from flyquery.web.conventions.idempotency import (
    IdempotencyStore,
    InMemoryIdempotencyStore,
)
from flyquery.web.conventions.postgres_idempotency import PostgresIdempotencyStore


@configuration(name="structured.FlyqueryConfiguration")
class FlyqueryConfiguration:
    """Exposes :class:`FlyquerySettings` and core auth services to the pyfly DI container."""

    @bean(name="structured.settings")
    def settings(
        self, agent_factory: AgentFactory, registry: DataSourceRegistry, config: Config | None = None
    ) -> FlyquerySettings:
        fields = {
            "backend": "object_store",
            "root": "object_store_base",
            "presign_ttl_seconds": "object_store_presign_ttl_s",
            "azure_account_url": "object_store_azure_account_url",
            "azure_container": "object_store_azure_container",
            "azure_prefix": "object_store_azure_prefix",
            "gcs_bucket": "object_store_gcs_bucket",
            "gcs_project": "object_store_gcs_project",
            "gcs_prefix": "object_store_gcs_prefix",
            "gcs_endpoint_url": "object_store_gcs_endpoint_url",
            "request_timeout_seconds": "object_store_request_timeout_seconds",
            "max_object_bytes": "object_store_max_object_bytes",
        }
        overrides = {}
        for key, field in fields.items():
            value = config.get("koinon.storage.structured." + key) if config is not None else None
            if value is not None:
                overrides[field] = value
        settings = FlyquerySettings(**overrides)
        if config is not None and config.get("koinon.knowledge.ingestion") is not None:
            from koinon_storage.profile import LibraryIngestionProfile

            profile = LibraryIngestionProfile.from_config(config)
            configured = settings.model_dump()
            configured.update(
                {
                    "max_file_mb": (profile.raw_max_bytes + 1024**2 - 1) // 1024**2,
                    "max_file_bytes": profile.raw_max_bytes,
                    "ingest_decompressed_max_bytes": profile.expanded_max_bytes,
                    "ingest_scratch_max_bytes": profile.scratch_max_bytes,
                    "ingest_reader_rss_max_bytes": profile.child_rss_max_bytes,
                    "ingest_reader_timeout_seconds": profile.wall_seconds,
                }
            )
            settings = FlyquerySettings(**configured)
        settings._require_model_bindings = (
            bool(config.get("koinon.knowledge.require_connections", False)) if config else False
        )
        settings.bind_native_resources(agent_factory, registry)
        return settings

    @bean(name="structured.tenant_guc_customizer")
    def tenant_guc_customizer(self, settings: FlyquerySettings) -> TenantGucCustomizer:
        return TenantGucCustomizer(settings.datasource_name)

    @bean(name="structured.sessions")
    def sessions(self, settings: FlyquerySettings) -> StructuredSessionBinding:
        return StructuredSessionBinding(settings.native_datasource().sessionmaker)

    @bean(name="structured.admin_sessions")
    def admin_sessions(self, settings: FlyquerySettings) -> StructuredSessionBinding:
        return StructuredSessionBinding(settings.native_datasource(admin=True).sessionmaker)

    @bean(name="structured.workspace_service")
    def workspace_service(
        self, repository: WorkspaceRepository, admin: WorkspaceAdminRepository
    ) -> WorkspaceService:
        return WorkspaceService(repository, admin)

    # ------------------------------------------------------------------
    # Auth services
    # ------------------------------------------------------------------

    @bean(name="structured.rate_limiter")
    def rate_limiter(self, settings: FlyquerySettings, cache: CacheAdapter | None = None) -> RateLimiter:
        """Use native primary PostgreSQL unless an alternate backend is explicit."""
        backend = cache_backend(settings, "rate_limit_backend")
        if backend == "postgres":
            return PostgresRateLimiter(cache)
        if backend == "redis":
            from flyquery.core.services.auth.redis_rate_limiter import RedisRateLimiter

            return RedisRateLimiter(_build_redis_client(settings))
        return _RateLimiter()

    @bean(name="structured.agent_token_repository")
    def agent_token_repository(self, settings: FlyquerySettings) -> AgentTokenRepository:
        source = settings.native_datasource()
        return AgentTokenRepository(source.sessionmaker, engine=source.engine)

    @bean(name="structured.agent_token_service")
    def agent_token_service(
        self,
        agent_token_repository: AgentTokenRepository,
        rate_limiter: RateLimiter,
    ) -> AgentTokenService:
        return AgentTokenService(agent_token_repository, rate_limiter=rate_limiter)

    # ------------------------------------------------------------------
    # ObjectStore (blob storage)
    # ------------------------------------------------------------------

    @bean(name="structured.object_store")
    def object_store(self, settings: FlyquerySettings) -> ObjectStore:
        return build_object_store(settings)

    # ------------------------------------------------------------------
    # EDA publisher
    # ------------------------------------------------------------------
    #
    # ``IngestPublisher`` registers itself via ``@service`` (see
    # ``flyquery.core.eda.ingest_publisher``). Do NOT add a @bean
    # factory here: a factory shadows the @service registration and
    # resolves ``EventPublisher`` at factory-evaluation time (before
    # ``EdaAutoConfiguration`` has wired it), so the wrapper ends up
    # with ``self._publisher = None`` and silently drops every publish
    # into the in-memory branch -- workers never see the event.

    # ------------------------------------------------------------------
    # Retrieval infrastructure
    # ------------------------------------------------------------------

    @bean(name="structured.embedder")
    def embedder(self, settings: FlyquerySettings) -> Embedder:
        """Provider-agnostic embedder via fireflyframework-agentic.

        Reads ``settings.embedding_provider`` (default ``ollama``) and
        builds the matching adapter. Falls back to a ``NullEmbedder``
        when the provider is unavailable; retrieval gracefully
        degrades to BM25 over ``content_tsv``.
        """
        return build_embedder(settings)

    @bean(name="structured.reranker")
    def reranker(self, settings: FlyquerySettings) -> Reranker:
        """Cross-encoder reranker (falls back to NoopReranker when unavailable)."""
        return build_reranker(settings)

    @bean(name="structured.ast_classifier")
    def ast_classifier(self) -> AstClassifier:
        return AstClassifier()

    @bean(name="structured.scope_guard")
    def scope_guard(self) -> ScopeGuard:
        return ScopeGuard()

    @bean(name="structured.executor")
    def executor(self, settings: FlyquerySettings, object_store: ObjectStore) -> DuckDBExecutor:
        return DuckDBExecutor(settings, object_store=object_store)

    # ------------------------------------------------------------------
    # Idempotency store (agent surface)
    # ------------------------------------------------------------------

    @bean(name="structured.idempotency_store")
    def idempotency_store(
        self, settings: FlyquerySettings, cache: CacheAdapter | None = None
    ) -> IdempotencyStore:
        """Use native primary PostgreSQL unless an alternate backend is explicit."""
        backend = cache_backend(settings, "idempotency_backend")
        if backend == "postgres":
            return PostgresIdempotencyStore(cache)
        if backend == "redis":
            from flyquery.web.conventions.redis_idempotency import RedisIdempotencyStore

            return RedisIdempotencyStore(_build_redis_client(settings))
        return InMemoryIdempotencyStore()


# ----------------------------------------------------------------------
# Redis adapter helpers
# ----------------------------------------------------------------------


def _use_redis(settings: FlyquerySettings, backend_field: str) -> bool:
    """Compatibility helper for explicit Redis selection only."""
    return cache_backend(settings, backend_field) == "redis"


def _build_redis_client(settings: FlyquerySettings):  # noqa: ANN202
    from redis.asyncio import from_url as _redis_from_url

    return _redis_from_url(settings.redis_url)
