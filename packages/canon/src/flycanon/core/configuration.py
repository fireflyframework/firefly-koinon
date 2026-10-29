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

"""``@configuration`` class -- every cross-cutting service as a pyfly bean.

Pyfly's container scans this module, sees the ``@configuration`` class,
instantiates it once, then calls each ``@bean`` method to produce the
beans. The return-type annotation determines the bean's interface so
constructor-injection works on every consumer (controller, command /
query handler, worker).

This is the **single** declaration point for everything that is not
picked up by a stereotype decorator
(``@service``/``@rest_controller``/``@command_handler``/
``@query_handler``/``@repository``).
"""

from __future__ import annotations

import logging

from pyfly.agentic.content.binary import (
    BinaryConfig,
    BinaryNormalizer,
    OfficeConverter,
    build_office_converter,
)
from pyfly.agentic.factory import AgentFactory
from pyfly.container import bean, configuration
from pyfly.core import Config
from pyfly.data.relational.datasource_registry import DataSourceRegistry
from pyfly.data.relational.health import SqlAlchemyHealthIndicator

from flycanon.config import CanonSettings

# AuditService / KnowledgeService / CandidateService / IntakeService /
# TaxonomyService / ProvenanceService carry their own ``@service``
# decorators and are auto-discovered via ``scan_packages`` rather than
# constructed via @bean factories here. The imports are retained for
# the type hints used in the remaining @bean signatures.
from flycanon.core.services.audit import AuditService  # noqa: F401
from flycanon.core.services.auth.agent_token_service import (
    AgentTokenService,
    RateLimiter,
    _RateLimiter,
)
from flycanon.core.services.auth.redis_rate_limiter import RedisRateLimiter
from flycanon.core.services.billing.cost_service import CostService
from flycanon.core.services.consolidation import (
    Consolidator,
)
from flycanon.core.services.consolidation.prompt_loader import load_prompt
from flycanon.core.services.embeddings import (
    EmbeddingRegistry,
    EmbeddingService,
    EmbeddingSetService,
)
from flycanon.core.services.ingestion import (
    Chunker,
    IngestionService,
    LoaderRegistry,
)
from flycanon.core.services.ingestion.chunker import build_default_chunker
from flycanon.core.services.ingestion.loaders import default_registry
from flycanon.core.services.query.answer_dispatcher import AnswerDispatcher
from flycanon.core.services.query.answer_service import AnswerService
from flycanon.core.services.query.rlm.chat import RlmChatClient, build_rlm_client
from flycanon.core.services.query.rlm.corpus import CanonCorpusBuilder
from flycanon.core.services.query.rlm.page_cache import CorpusPageCache, build_page_cache
from flycanon.core.services.query.rlm_answer_service import RLMAnswerService
from flycanon.core.services.query.search_service import SearchService
from flycanon.core.services.retrieval import (
    CorpusContext,
    IndexService,
    RetrievalService,
    build_corpus_context,
)
from flycanon.core.services.retrieval.query_expander import QueryExpander
from flycanon.core.services.retrieval.reranker import build_reranker
from flycanon.core.services.storage.factory import build_object_store
from flycanon.core.services.storage.object_store import ObjectStore
from flycanon.data import TenantGucCustomizer
from flycanon.models.repositories import (
    AgentTokenRepository,
    AuditRepository,
    CandidateRepository,
    ChunkRepository,
    ConversationRepository,
    CostRepository,
    EmbeddingSetRepository,
    IngestJobRepository,
    KnowledgeRepository,
    RelationRepository,
    ScopePurgeRepository,
    SourceRepository,
    TaxonomyRepository,
    WorkspaceRepository,
)
from flycanon.web.conventions.api_key_middleware import ApiKeyPrincipalFilter
from flycanon.web.conventions.idempotency import (
    IdempotencyStore,
    InMemoryIdempotencyStore,
)
from flycanon.web.conventions.redis_idempotency import RedisIdempotencyStore

logger = logging.getLogger(__name__)


@configuration(name="canon.CanonCoreConfiguration")
class CanonCoreConfiguration:
    """Wiring for everything outside the pyfly stereotype decorators.

    ``EventPublisher``-dependent services (``AuditService``,
    ``KnowledgeService``, ``CandidateService``, ``IntakeService``,
    ``TaxonomyService``) are declared as ``@service`` classes on the
    classes themselves so pyfly resolves them lazily -- by then
    pyfly's ``EdaAutoConfiguration`` has already registered the
    ``EventPublisher`` bean.
    """

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    @bean(name="canon.settings")
    def settings(
        self, agent_factory: AgentFactory, registry: DataSourceRegistry, config: Config | None = None
    ) -> CanonSettings:
        fields = {
            "backend": "object_store_backend",
            "root": "object_store_localfs_root",
            "store_originals": "store_originals",
            "s3_bucket": "object_store_s3_bucket",
            "s3_prefix": "object_store_s3_prefix",
            "s3_endpoint_url": "object_store_s3_endpoint_url",
            "s3_region": "object_store_s3_region",
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
            value = config.get("koinon.storage.documents." + key) if config is not None else None
            if value is not None:
                overrides[field] = value
        settings = CanonSettings(**overrides)
        settings._require_model_bindings = (
            bool(config.get("koinon.knowledge.require_connections", False)) if config else False
        )
        settings.bind_native_resources(agent_factory, registry)
        return settings

    @bean(name="canon.tenant_guc_customizer")
    def tenant_guc_customizer(self, settings: CanonSettings) -> TenantGucCustomizer:
        return TenantGucCustomizer(settings.datasource_name)

    # ------------------------------------------------------------------
    # Repositories -- one async engine, six repositories sharing it
    # ------------------------------------------------------------------

    @bean(name="canon.source_repository")
    def source_repository(self, settings: CanonSettings) -> SourceRepository:
        return SourceRepository(
            settings.native_datasource().sessionmaker, engine=settings.native_datasource().engine
        )

    @bean(name="canon.chunk_repository")
    def chunk_repository(self, settings: CanonSettings) -> ChunkRepository:
        return ChunkRepository(
            settings.native_datasource().sessionmaker, engine=settings.native_datasource().engine
        )

    @bean(name="canon.knowledge_repository")
    def knowledge_repository(self, settings: CanonSettings) -> KnowledgeRepository:
        return KnowledgeRepository(
            settings.native_datasource().sessionmaker, engine=settings.native_datasource().engine
        )

    @bean(name="canon.candidate_repository")
    def candidate_repository(self, settings: CanonSettings) -> CandidateRepository:
        return CandidateRepository(
            settings.native_datasource().sessionmaker, engine=settings.native_datasource().engine
        )

    @bean(name="canon.audit_repository")
    def audit_repository(self, settings: CanonSettings) -> AuditRepository:
        return AuditRepository(
            settings.native_datasource().sessionmaker, engine=settings.native_datasource().engine
        )

    @bean(name="canon.taxonomy_repository")
    def taxonomy_repository(self, settings: CanonSettings) -> TaxonomyRepository:
        return TaxonomyRepository(
            settings.native_datasource().sessionmaker, engine=settings.native_datasource().engine
        )

    @bean(name="canon.relation_repository")
    def relation_repository(self, settings: CanonSettings) -> RelationRepository:
        return RelationRepository(
            settings.native_datasource().sessionmaker, engine=settings.native_datasource().engine
        )

    @bean(name="canon.ingest_job_repository")
    def ingest_job_repository(self, settings: CanonSettings) -> IngestJobRepository:
        return IngestJobRepository(
            settings.native_datasource().sessionmaker, engine=settings.native_datasource().engine
        )

    @bean(name="canon.embedding_set_repository")
    def embedding_set_repository(self, settings: CanonSettings) -> EmbeddingSetRepository:
        return EmbeddingSetRepository(
            settings.native_datasource().sessionmaker, engine=settings.native_datasource().engine
        )

    @bean(name="canon.conversation_repository")
    def conversation_repository(self, settings: CanonSettings) -> ConversationRepository:
        return ConversationRepository(
            settings.native_datasource().sessionmaker, engine=settings.native_datasource().engine
        )

    @bean(name="canon.cost_repository")
    def cost_repository(self, settings: CanonSettings) -> CostRepository:
        return CostRepository(
            settings.native_datasource().sessionmaker, engine=settings.native_datasource().engine
        )

    @bean(name="canon.workspace_repository")
    def workspace_repository(self, settings: CanonSettings) -> WorkspaceRepository:
        """Workspace CRUD on the request engine, tenant-wide reads on the admin engine.

        ``list_for_tenant`` is a cross-workspace read; under the
        production ``flycanon_app`` role the ``canon_workspaces`` policy
        (``id = app.workspace_id``) would collapse it to the single
        workspace in the caller's header. It therefore runs on the
        BYPASSRLS engine named by ``FLYCANON_ADMIN_DATABASE_URL``. When
        that is unset the request DSN is reused (correct wherever it
        already bypasses RLS) and the fact is logged so an operator who
        sees a one-row listing in production knows which knob to turn.
        """
        source = settings.native_datasource()
        admin = settings.native_datasource(admin=True)
        return WorkspaceRepository(
            source.sessionmaker, engine=source.engine, admin_session_factory=admin.sessionmaker
        )

    @bean(name="canon.scope_purge_repository")
    def scope_purge_repository(self, settings: CanonSettings) -> ScopePurgeRepository:
        return ScopePurgeRepository(
            settings.native_datasource().sessionmaker, engine=settings.native_datasource().engine
        )

    @bean(name="canon.agent_token_repository")
    def agent_token_repository(self, settings: CanonSettings) -> AgentTokenRepository:
        return AgentTokenRepository(
            settings.native_datasource().sessionmaker, engine=settings.native_datasource().engine
        )

    # ------------------------------------------------------------------
    # Auth services
    # ------------------------------------------------------------------

    @bean(name="canon.rate_limiter")
    def rate_limiter(self, settings: CanonSettings) -> RateLimiter:
        """Per-token sliding-window rate limiter.

        Backend selection:

        * ``FLYCANON_RATE_LIMIT_BACKEND=redis`` -- always Redis.
        * ``FLYCANON_RATE_LIMIT_BACKEND=in_memory`` -- always
          in-memory (even when ``redis_url`` is set).
        * unset / ``auto`` (the default) -- Redis when ``redis_url``
          is configured, otherwise an actionable configuration error.

        In-memory is fine for single-replica dev / test posture but
        does NOT enforce ``rate_limit_rpm`` correctly across replicas;
        production deployments behind a load balancer MUST use the
        Redis variant or the per-replica buckets effectively multiply
        the budget by the replica count.
        """
        if _use_redis(settings, "rate_limit_backend"):
            client = _build_redis_client(settings)
            return RedisRateLimiter(client)
        return _RateLimiter()

    @bean(name="canon.agent_token_service")
    def agent_token_service(
        self,
        agent_token_repository: AgentTokenRepository,
        rate_limiter: RateLimiter,
    ) -> AgentTokenService:
        return AgentTokenService(agent_token_repository, rate_limiter=rate_limiter)

    # ------------------------------------------------------------------
    # Replay dedup for the agent surface
    #
    # A singleton :class:`IdempotencyStore` bean is shared by every
    # agent controller so a replayed POST with the same
    # ``Idempotency-Key`` returns the original response body without
    # re-dispatching the command. Backend selection mirrors
    # :meth:`rate_limiter`: Redis when ``redis_url`` is set (or
    # ``FLYCANON_IDEMPOTENCY_BACKEND=redis``), in-memory otherwise.
    # ------------------------------------------------------------------

    @bean(name="canon.idempotency_store")
    def idempotency_store(self, settings: CanonSettings) -> IdempotencyStore:
        if _use_redis(settings, "idempotency_backend"):
            client = _build_redis_client(settings)
            return RedisIdempotencyStore(client)
        return InMemoryIdempotencyStore()

    @bean(name="canon.api_key_principal_filter")
    def api_key_principal_filter(self) -> ApiKeyPrincipalFilter:
        """Bridge a validated API key into pyfly's ``SecurityContext``.

        Declared as a bean so pyfly's late ``WebFilter`` discovery (run
        after context start) appends it to the request filter chain;
        that is the only way to populate the security context the admin
        dashboard's ``require-auth`` gate reads. The gate itself is the
        outer :class:`ApiKeyMiddleware` in ``flycanon.main``.
        """
        return ApiKeyPrincipalFilter()

    @bean(name="canon.database_health")
    def database_health(self, source_repository: SourceRepository) -> SqlAlchemyHealthIndicator:
        """SQLAlchemy health probe -- wired into pyfly's /actuator/health."""
        return SqlAlchemyHealthIndicator(source_repository.engine)

    # ------------------------------------------------------------------
    # Ingestion + embeddings + retrieval
    # ------------------------------------------------------------------

    @bean(name="canon.loader_registry")
    def loader_registry(self) -> LoaderRegistry:
        return default_registry()

    @bean(name="canon.chunker")
    def chunker(self, settings: CanonSettings) -> Chunker:
        return build_default_chunker(
            chunk_size_tokens=settings.chunk_size_tokens,
            overlap_tokens=settings.chunk_overlap_tokens,
        )

    @bean(name="canon.ingestion_service")
    def ingestion_service(
        self,
        loader_registry: LoaderRegistry,
        chunker: Chunker,
    ) -> IngestionService:
        return IngestionService(loaders=loader_registry, chunker=chunker)

    @bean(name="canon.object_store")
    def object_store(self, settings: CanonSettings) -> ObjectStore:
        return build_object_store(settings)

    @bean(name="canon.embedding_registry")
    def embedding_registry(self, settings: CanonSettings) -> EmbeddingRegistry:
        """One embedder per ``(provider, model, dimensions)``, built on demand.

        The process default is built eagerly inside the registry so a
        misconfigured ``FLYCANON_EMBEDDING_MODEL`` still fails at boot; the
        others appear when a workspace on another embedding set is first read
        or written, which is what lets one shared flycanon serve tenants on
        different embedders and what makes a re-embed's dual-set window work.
        """
        return EmbeddingRegistry(settings=settings)

    @bean(name="canon.embedding_service")
    def embedding_service(self, embedding_registry: EmbeddingRegistry) -> EmbeddingService:
        """The process default, for the callers that legitimately have no scope.

        Quality detectors compare knowledge-item bodies against each other,
        not against a workspace's corpus, so they embed with the deployment's
        configured model rather than with a set's.
        """
        return embedding_registry.default

    @bean(name="canon.embedding_set_service")
    def embedding_set_service(
        self,
        embedding_set_repository: EmbeddingSetRepository,
        settings: CanonSettings,
    ) -> EmbeddingSetService:
        return EmbeddingSetService(repository=embedding_set_repository, settings=settings)

    @bean(name="canon.corpus_context")
    def corpus_context(self, settings: CanonSettings) -> CorpusContext:
        ctx = build_corpus_context(settings=settings)
        return ctx

    @bean(name="canon.index_service")
    def index_service(self, corpus_context: CorpusContext, chunk_repository: ChunkRepository) -> IndexService:
        return IndexService(context=corpus_context, chunk_repository=chunk_repository)

    @bean(name="canon.retrieval_service")
    def retrieval_service(
        self,
        corpus_context: CorpusContext,
        embedding_service: EmbeddingService,
        embedding_registry: EmbeddingRegistry,
        embedding_set_service: EmbeddingSetService,
        source_repository: SourceRepository,
        chunk_repository: ChunkRepository,
        knowledge_repository: KnowledgeRepository,
        settings: CanonSettings,
    ) -> RetrievalService:
        # Optional retrieval enhancements driven by env config:
        # * Reranker -- cross-encoder over the fused hit set
        #   (FLYCANON_RERANKER_MODEL = "" disables it). Adapters
        #   for Cohere + Voyage ship; falling back to NoOp when
        #   the API key is missing keeps the path resilient.
        # * Query expander -- LLM paraphrase + multi-query RRF
        #   fusion (FLYCANON_QUERY_EXPANSION_ENABLED=true). Each
        #   query expansion costs one extra LLM call so off by
        #   default.
        reranker = build_reranker(settings.reranker_model)
        expander = (
            QueryExpander(model=settings.answer_model, settings=settings)
            if settings.query_expansion_enabled
            else None
        )
        return RetrievalService(
            context=corpus_context,
            embeddings=embedding_service,
            source_repository=source_repository,
            chunk_repository=chunk_repository,
            knowledge_repository=knowledge_repository,
            default_top_k=settings.retrieval_top_k,
            default_per_query_k=settings.retrieval_per_query_k,
            rrf_k=settings.retrieval_rrf_k,
            reranker=reranker,
            reranker_top_n=settings.reranker_top_n,
            query_expander=expander,
            query_expansion_n=settings.query_expansion_n if expander else 1,
            embedding_sets=embedding_set_service,
            embedding_registry=embedding_registry,
        )

    # ------------------------------------------------------------------
    # Audit + knowledge lifecycle + taxonomy
    #
    # AuditService, KnowledgeService, ProvenanceService, TaxonomyService
    # are now ``@service``-decorated classes auto-discovered via
    # ``scan_packages``. Pyfly's container resolves their dependencies
    # (including ``EventPublisher`` from ``EdaAutoConfiguration``) at
    # first lookup -- by that point every auto-configuration has run.
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Consolidation + query
    # ------------------------------------------------------------------

    @bean(name="canon.consolidator")
    def consolidator(
        self,
        settings: CanonSettings,
    ) -> Consolidator:
        # Prompt is loaded inline so the ``PromptTemplate`` bean type
        # doesn't collide with the answer-prompt bean -- pyfly's
        # container resolves @bean params by TYPE, so two beans
        # returning the same ``PromptTemplate`` type would overwrite
        # each other under the same key.
        #
        # The ``settings`` are threaded into the Consolidator so the
        # central agent builder can read the
        # ``agent_max_output_tokens`` / ``consolidator_max_output_tokens``
        # knobs -- avoids the 4096 default truncating structured
        # multi-candidate arrays mid-emit.
        return Consolidator(
            prompt=load_prompt("consolidation"),
            default_model=settings.answer_model,
            settings=settings,
        )

    # CandidateService is ``@service``-decorated; auto-discovered.

    @bean(name="canon.search_service")
    def search_service(self, retrieval_service: RetrievalService) -> SearchService:
        return SearchService(retrieval=retrieval_service)

    @bean(name="canon.answer_service")
    def answer_service(
        self,
        retrieval_service: RetrievalService,
        settings: CanonSettings,
    ) -> AnswerService:
        # Prompt is loaded inline -- see ``consolidator`` above for the
        # rationale (avoid type-based DI collision on PromptTemplate).
        # ``settings`` are threaded through so the central agent
        # builder can honor the ``answer_max_output_tokens`` /
        # ``agent_max_output_tokens`` knobs.
        return AnswerService(
            retrieval=retrieval_service,
            prompt=load_prompt("answer"),
            default_model=settings.answer_model,
            fallback_model=settings.answer_fallback_model,
            settings=settings,
        )

    # ------------------------------------------------------------------
    # RLM query engine
    #
    # The Recursive Language Model answerer is a drop-in alternative to
    # the RAG ``answer_service`` (same ``answer()`` contract). It needs a
    # whole-document corpus builder (sources + object store + loaders) and
    # a synchronous Anthropic client to drive the CodeAct REPL; the engine
    # is run inside ``asyncio.to_thread`` by the service. No call site uses
    # it yet -- the mode dispatch lands in a later PR.
    # ------------------------------------------------------------------

    @bean(name="canon.corpus_page_cache")
    def corpus_page_cache(self, settings: CanonSettings) -> CorpusPageCache:
        """Shared page-text cache layered over the lazy RLM corpus store.

        A process singleton (so the in-memory LRU persists across
        requests) injected into :meth:`canon_corpus_builder`. Backend
        selection mirrors :meth:`rate_limiter` / :meth:`idempotency_store`
        via :func:`build_page_cache`: Redis when ``redis_url`` is set (or
        ``FLYCANON_CORPUS_CACHE_BACKEND=redis``), in-memory otherwise.
        The Redis client is synchronous because the cache is read from
        the RLM engine's worker thread.
        """
        return build_page_cache(settings)

    @bean(name="canon.canon_corpus_builder")
    def canon_corpus_builder(
        self,
        source_repository: SourceRepository,
        knowledge_repository: KnowledgeRepository,
        object_store: ObjectStore,
        loader_registry: LoaderRegistry,
        corpus_page_cache: CorpusPageCache,
    ) -> CanonCorpusBuilder:
        return CanonCorpusBuilder(
            source_repository=source_repository,
            knowledge_repository=knowledge_repository,
            object_store=object_store,
            registry=loader_registry,
            cache=corpus_page_cache,
        )

    @bean(name="canon.rlm_chat_client")
    def rlm_chat_client(self, settings: CanonSettings, agent_factory: AgentFactory) -> RlmChatClient:
        """The provider client the configured RLM models name.

        ``anthropic:`` and ``azure:`` are routed to their own clients; any
        other prefix, and a root/sub pair that straddles two providers, are
        refused here -- at boot, with the setting named -- rather than at the
        first query.
        """
        if settings._require_model_bindings:
            from flycanon.core.services.query.rlm.native_client import RequiredRlmBindingClient

            return RequiredRlmBindingClient()
        if settings.rlm_root_model.startswith("ollama:") or settings.rlm_sub_model.startswith("ollama:"):
            from flycanon.core.services.query.rlm.native_client import NativeRlmChatClient

            return NativeRlmChatClient(settings, agent_factory)
        return build_rlm_client(settings)

    @bean(name="canon.rlm_answer_service")
    def rlm_answer_service(
        self,
        canon_corpus_builder: CanonCorpusBuilder,
        rlm_chat_client: RlmChatClient,
        settings: CanonSettings,
        cost_service: CostService,
    ) -> RLMAnswerService:
        return RLMAnswerService(
            corpus_builder=canon_corpus_builder,
            client=rlm_chat_client,
            settings=settings,
            cost_service=cost_service,
        )

    @bean(name="canon.answer_dispatcher")
    def answer_dispatcher(
        self,
        answer_service: AnswerService,
        rlm_answer_service: RLMAnswerService,
        settings: CanonSettings,
    ) -> AnswerDispatcher:
        # Routes the non-streaming answer path to RLM (default) or the
        # legacy RAG ``answer_service`` per ``FLYCANON_ANSWER_MODE``.
        return AnswerDispatcher(
            rag=answer_service,
            rlm=rlm_answer_service,
            settings=settings,
        )

    # ------------------------------------------------------------------
    # Binary normalisation
    #
    # The normaliser + handlers live in the framework
    # (``pyfly.agentic.content.binary``). We map CanonSettings
    # onto a host-agnostic ``BinaryConfig`` and inject the pluggable
    # ``OfficeConverter``. ``wrap_text_as_pdf`` is False: flycanon passes
    # text / markdown / CSV through to its SourceLoader pipeline rather
    # than rendering them to PDF. ``email_render_header`` surfaces a
    # ``<stem>-headers.md`` artifact so Subject/From/To metadata still
    # reaches the loaders.
    # ------------------------------------------------------------------

    @bean(name="canon.binary_config")
    def binary_config(self, settings: CanonSettings) -> BinaryConfig:
        return BinaryConfig(
            normalize_enabled=settings.binary_normalize_enabled,
            max_bytes=settings.max_bytes,
            max_recursion_depth=settings.binary_max_recursion_depth,
            max_expanded_files=settings.binary_max_expanded_files,
            wrap_text_as_pdf=False,
            email_render_header=True,
            office_converter=settings.office_converter,
            gotenberg_url=settings.gotenberg_url,
            gotenberg_timeout_s=float(settings.gotenberg_timeout_s),
            libreoffice_path=settings.binary_libreoffice_path,
            libreoffice_timeout_s=float(settings.binary_libreoffice_timeout_s),
        )

    @bean(name="canon.office_converter")
    def office_converter(self, binary_config: BinaryConfig) -> OfficeConverter:
        kind = (binary_config.office_converter or "none").lower()
        if kind not in {"none", "", "disabled", "gotenberg", "libreoffice"}:
            raise ValueError(
                f"unknown FLYCANON_OFFICE_CONVERTER={binary_config.office_converter!r}; "
                "expected 'none', 'gotenberg', or 'libreoffice'"
            )
        return build_office_converter(binary_config)

    @bean(name="canon.binary_normalizer")
    def binary_normalizer(
        self,
        binary_config: BinaryConfig,
        office_converter: OfficeConverter,
    ) -> BinaryNormalizer:
        # The framework BinaryNormalizer builds its own PdfGuard /
        # ImageNormalizer / ArchiveUnpacker / EmailUnpacker from the config;
        # only the pluggable OfficeConverter is injected.
        return BinaryNormalizer(config=binary_config, office=office_converter)

    # IntakeService is ``@service``-decorated; auto-discovered.


# ----------------------------------------------------------------------
# Redis adapter helpers
#
# Shared by :meth:`CanonCoreConfiguration.rate_limiter` and
# :meth:`CanonCoreConfiguration.idempotency_store`. Build one async
# Redis client per process and reuse it across adapters so both share
# the connection pool.
# ----------------------------------------------------------------------


def _use_redis(settings: CanonSettings, backend_field: str) -> bool:
    """Return ``True`` when the matching adapter should use Redis.

    Three inputs decide:

    * ``settings.<backend_field>`` -- explicit env override
      (``redis`` / ``in_memory`` / ``auto``).
    * ``settings.redis_url`` -- when set, Redis is the default.
    * ``backend_field`` -- the per-adapter knob name; lets the
      rate-limit and idempotency stores be configured independently.

    Memory requires the explicit isolated-development switch. Missing Redis
    never silently weakens fleet-wide guarantees.
    """
    explicit = getattr(settings, backend_field, "auto") or "auto"
    explicit = explicit.lower()
    if explicit not in {"redis", "in_memory", "memory", "auto"}:
        raise ValueError(f"Unknown canon {backend_field}: {explicit!r}")
    if explicit in {"redis", "auto"} and settings.redis_url:
        return True
    if explicit != "redis" and settings.allow_in_memory_adapters:
        return False
    raise RuntimeError(
        f"Canon {backend_field} requires FLYCANON_REDIS_URL. "
        "Only isolated development/tests may set FLYCANON_ALLOW_IN_MEMORY_ADAPTERS=true."
    )


def _build_redis_client(settings: CanonSettings):  # noqa: ANN202
    """Async Redis client bound to ``settings.redis_url``.

    Returns the client untyped so the import of ``redis.asyncio``
    stays local to this helper -- callers receive a duck-typed handle
    that satisfies :class:`RedisRateLimiter` / :class:`RedisIdempotencyStore`
    constructors.

    Decoding is left to the adapters: :class:`RedisIdempotencyStore`
    handles both ``bytes`` and ``str`` responses so the helper does
    not need to set ``decode_responses=True``.
    """
    from redis.asyncio import from_url as _redis_from_url

    return _redis_from_url(settings.redis_url)
