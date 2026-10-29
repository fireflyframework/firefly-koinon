# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Thin authorized calls into retained pipelines; no alternate inference engine."""

from contextlib import asynccontextmanager, contextmanager, nullcontext
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from functools import wraps
from hashlib import sha256
from importlib import import_module
from numbers import Integral
from typing import Any
from uuid import UUID, uuid4

from pydantic import ValidationError as SettingsValidationError
from pyfly.container import Container, service
from pyfly.kernel import (
    ConflictException,
    DuplicateKeyException,
    ForbiddenException,
    InvalidRequestException,
    PayloadTooLargeException,
    RateLimitException,
    ResourceNotFoundException,
    ServiceUnavailableException,
    UnauthorizedException,
    UnsupportedMediaTypeException,
    ValidationException,
)
from sqlalchemy import text
from starlette.requests import Request

from koinon.knowledge.model_bindings import KnowledgeConnectionResolver
from koinon.knowledge.native_provenance import evidence_bound
from koinon.organization_knowledge.dtos import OrganizationKnowledgeSnapshot


def request_knowledge_settings(arguments) -> OrganizationKnowledgeSnapshot | None:
    value = arguments.get("_knowledge_settings_snapshot")
    if value is None:
        return None
    try:
        raw = value.model_dump(mode="json") if isinstance(value, OrganizationKnowledgeSnapshot) else value
        snapshot = OrganizationKnowledgeSnapshot.model_validate(raw)
    except (SettingsValidationError, ValueError, TypeError):
        raise InvalidRequestException(
            "The effective knowledge settings cannot be verified", code="KNOWLEDGE_SETTINGS_INVALID"
        ) from None
    if arguments.get("tenant_id", snapshot.tenant_id) != snapshot.tenant_id:
        raise ForbiddenException(
            "Knowledge settings belong to another organization", code="DOMAIN_SCOPE_MISMATCH"
        )
    return snapshot


def model_bound(domain):
    def decorate(operation):
        @wraps(operation)
        async def bound(self, *args, **kwargs):
            purpose, roles = self.model_requirements(domain, operation.__name__, kwargs)
            async with self.model_connections(
                domain,
                kwargs["tenant_id"],
                kwargs["workspace_id"],
                kwargs["actor"],
                purpose=purpose,
                roles=roles,
                catalog_workspace_id=kwargs.get("catalog_workspace_id"),
            ):
                return await operation(self, *args, **kwargs)

        return bound

    return decorate


def _json(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return _json(value.model_dump(mode="python"))
    if is_dataclass(value) and not isinstance(value, type):
        return {key: _json(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {key: _json(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json(item) for item in value]
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, bool):
        return value
    if isinstance(value, Integral):
        integer = int(value)
        return integer if -(2**53 - 1) <= integer <= 2**53 - 1 else str(integer)
    convert = getattr(value, "tolist", None)
    if type(value).__module__.partition(".")[0] == "numpy" and callable(convert):
        native = convert()
        return str(value) if type(native) is type(value) else _json(native)
    return str(value) if isinstance(value, UUID) else value


@contextmanager
def native_scope(domain, tenant_id, workspace_id, actor):
    package = "flycanon" if domain == "canon" else "flyquery"
    module = import_module(package + ".web.conventions.context")
    domain_error = import_module(package + ".web.conventions.exceptions").FireflyHTTPException
    context = module.TenantContext(
        tenant_id=tenant_id, workspace_id=str(workspace_id), actor=actor, correlation_id=str(uuid4())
    )
    token = module.set_tenant_context(context)
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/internal",
            "headers": [],
            "state": {"legacy_tenant_context": context},
        }
    )
    try:
        yield request
    except domain_error as error:
        exception = {
            400: InvalidRequestException,
            401: UnauthorizedException,
            403: ForbiddenException,
            404: ResourceNotFoundException,
            409: ConflictException,
            413: PayloadTooLargeException,
            415: UnsupportedMediaTypeException,
            422: ValidationException,
            429: RateLimitException,
        }.get(error.status, ServiceUnavailableException)
        raise exception(str(error), code=error.code) from error
    finally:
        token.var.reset(token.token)


@service(name="knowledge.native_domains")
class NativeDomains:
    def __init__(self, container: Container):
        self.container = container

    def model_requirements(self, domain, operation, arguments):
        policy = request_knowledge_settings(arguments)
        package = "flycanon" if domain == "canon" else "flyquery"
        settings_type = getattr(
            import_module(package + ".config"), "CanonSettings" if domain == "canon" else "FlyquerySettings"
        )
        settings = self._resolve(settings_type) if self.container.contains_type(settings_type) else None
        if domain == "canon":
            roles = ["documents.embedding"]
            if operation != "search":
                return "ingest", tuple(roles)
            answer = arguments.get("answer", False)
            if arguments.get("_curated_retrieve") is not None and not arguments.get("source_ids"):
                roles = []
            mode = policy.documents.answer_mode if policy else getattr(settings, "answer_mode", "rag")
            purpose = (
                "rlm"
                if answer and mode == "rlm"
                else "answer"
                if answer
                else "search"
            )
            if answer:
                if arguments.get("_curated_retrieve") is not None and purpose == "rlm":
                    raise ServiceUnavailableException(
                        "Curated knowledge requires the qualified RAG answer path",
                        code="KNOWLEDGE_RLM_UNQUALIFIED",
                    )
                if purpose == "rlm":
                    return purpose, ("documents.rlm",)
                roles.append("documents.answer")
            expansion = (
                policy.documents.query_expansion_enabled
                if policy else getattr(settings, "query_expansion_enabled", False)
            )
            if expansion and "documents.answer" not in roles:
                roles.append("documents.answer")
            return purpose, tuple(roles)
        if operation == "query":
            roles = [
                "structured.embedding",
                "structured.grounding",
                "structured.generation",
                "structured.explainer",
            ]
            repairs = (
                policy.structured.max_refine_retries if policy else getattr(settings, "max_refine_retries", 0)
            )
            if repairs > 0:
                roles.append("structured.critic")
            return "query", tuple(roles)
        roles = ["structured.embedding", "structured.describe"]
        if getattr(settings, "relation_proposer_enabled", True):
            roles.append("structured.relation_proposal")
        if operation == "reupload_table":
            roles.append("structured.rename_detection")
        return "ingest", tuple(roles)

    @asynccontextmanager
    async def model_connections(
        self, domain, tenant_id, workspace_id, actor, *, purpose, roles, catalog_workspace_id=None
    ):
        package = "flycanon" if domain == "canon" else "flyquery"
        port = import_module(package + ".core.agents.model_bindings")
        with native_scope(domain, tenant_id, workspace_id, actor):
            active = port.current_scope()
            if active is not None:
                if not active.required:
                    raise ServiceUnavailableException(
                        "Product knowledge calls require complete explicit connection bindings",
                        code="KNOWLEDGE_MODEL_SCOPE_REQUIRED",
                    )
                yield
                return
            if not roles:
                token = port.push_bindings(
                    tenant_id=tenant_id,
                    workspace_id=str(workspace_id),
                    subject=actor,
                    bindings={},
                    embeddings={},
                )
                try:
                    yield
                finally:
                    port.reset_bindings(token)
                return
            candidates = (
                [
                    kind
                    for kind in self.container.registered_types()
                    if issubclass(kind, KnowledgeConnectionResolver)
                ]
                if hasattr(self.container, "registered_types")
                else []
            )
            if not self.container.contains_type(KnowledgeConnectionResolver) and not candidates:
                raise ServiceUnavailableException(
                    "Select an authorized knowledge connection and compatible embedding profile",
                    code="KNOWLEDGE_CONNECTION_REQUIRED",
                )
            resolver = self._resolve(KnowledgeConnectionResolver)
            async with resolver.resolve(
                domain=domain,
                tenant_id=tenant_id,
                workspace_id=str(workspace_id),
                subject=actor,
                purpose=purpose,
                roles=roles,
                catalog_workspace_id=catalog_workspace_id,
            ) as connections:
                token = port.push_bindings(
                    tenant_id=tenant_id,
                    workspace_id=str(workspace_id),
                    subject=actor,
                    bindings=connections.models,
                    embeddings=connections.embeddings,
                )
                try:
                    yield
                finally:
                    port.reset_bindings(token)

    def _resolve(self, cls):
        if self.container.contains_type(cls):
            return self.container.resolve(cls)
        candidates = [
            kind
            for kind in self.container.registered_types()
            if issubclass(kind, cls) and not getattr(kind, "__pyfly_bean_name__", "").startswith("bff.")
        ]
        if candidates:
            return self.container.resolve(candidates[0])
        raise ServiceUnavailableException(
            f"The retained {cls.__module__.split('.')[0]} pipeline is not enabled; "
            "configure its native resources",
            code="DOMAIN_PREREQUISITE_REQUIRED",
        )

    async def ensure_workspace(self, *, domain, tenant_id, catalog_id, name, actor):
        if domain == "canon":
            from flycanon.models.repositories import WorkspaceRepository

            with native_scope(domain, tenant_id, catalog_id, actor):
                repository = self._resolve(WorkspaceRepository)
                row = await repository.get(tenant_id, catalog_id)
                if row is None:
                    try:
                        await repository.insert(
                            {"id": catalog_id, "tenant_id": tenant_id, "name": name, "status": "active"}
                        )
                    except DuplicateKeyException:
                        if await repository.get(tenant_id, catalog_id) is None:
                            raise
                return catalog_id
        from flyquery.core.services.workspaces.workspace_service import WorkspaceService

        with native_scope(domain, tenant_id, catalog_id, actor):
            service = self._resolve(WorkspaceService)
            provision = getattr(service, "provision", None)
            if provision is None:
                raise ServiceUnavailableException(
                    "Structured workspace provisioning requires its native admin-backed provision service",
                    code="WORKSPACE_PROVISIONING_REQUIRED",
                )
            row = await provision(
                tenant_id=tenant_id, workspace_id=UUID(catalog_id), name=name, slug=catalog_id
            )
            if row["tenant_id"] != tenant_id or str(row["id"]) != catalog_id:
                raise InvalidRequestException("Native workspace scope mismatch", code="DOMAIN_SCOPE_MISMATCH")
            return str(row["id"])

    @model_bound("canon")
    async def ingest_document(
        self,
        *,
        tenant_id,
        workspace_id,
        filename,
        content,
        actor,
        source_catalog_id,
        catalog_workspace_id=None,
        authorize_commit=None,
    ):
        from flycanon.core.services.sources.intake_service import IntakeService
        from flycanon.interfaces.dtos.source import SourceMetadata, SubmitSourceRequest

        with native_scope("canon", tenant_id, workspace_id, actor):
            source = await self._resolve(IntakeService).submit(
                request=SubmitSourceRequest(
                    metadata=SourceMetadata(extra={"catalog_source_id": source_catalog_id})
                ),
                content=content,
                filename=filename,
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                actor=actor,
                correlation_id=str(uuid4()),
                logical_source_key=source_catalog_id,
                operation_id=f"upload:{source_catalog_id}",
                authorize_commit=authorize_commit,
            )
        if source.status != "ingested":
            raise ServiceUnavailableException(
                "The retained document pipeline did not finish ingestion", code="DOCUMENT_INGEST_INCOMPLETE"
            )
        if not source.object_store_key:
            raise ServiceUnavailableException(
                "The retained pipeline did not persist the original bytes; configure a durable object store",
                code="DOCUMENT_ORIGINAL_UNAVAILABLE",
            )
        lineage = (getattr(source, "metadata_json", None) or {}).get("_source_lineage") or {}
        return {
            "source_id": source.id,
            "n_chunks": source.n_chunks,
            "object_store_key": source.object_store_key,
            "source_version_id": lineage.get("version_id"),
            "extraction_id": lineage.get("extraction_id"),
        }

    @asynccontextmanager
    async def structured_lineage(
        self,
        *,
        tenant_id,
        workspace_id,
        actor,
        catalog_workspace_id,
        dataset_id=None,
        table_id=None,
        source_catalog_id=None,
        operation="upload",
        predecessor_snapshot_id=None,
    ):
        from koinon.knowledge.lineage.service import NativeStructuredLineage
        from koinon.knowledge.service import KnowledgeFacade

        knowledge = self._resolve(KnowledgeFacade)

        async def authorize():
            identifiers = [source_catalog_id] if source_catalog_id else []
            if dataset_id is not None:
                for native_id in (dataset_id, table_id):
                    if native_id is not None:
                        aliases = await knowledge.bindings.find_all(
                            tenant_id=tenant_id,
                            domain="structured",
                            native_id=native_id,
                            native_workspace_id=workspace_id,
                        )
                        identifiers.extend(
                            alias.catalog_id for alias in aliases if alias.entity_kind in {"dataset", "table"}
                        )
            if not identifiers:
                raise ForbiddenException(
                    "No canonical ingestion identity is bound", code="BINDING_UNAVAILABLE"
                )
            for identifier in dict.fromkeys(identifiers):
                chain = await knowledge._chain(actor, tenant_id, identifier, "ingest:write")
                if catalog_workspace_id is not None and chain[0].workspace_id != catalog_workspace_id:
                    raise ForbiddenException(
                        "Lineage workspace disagrees with catalog", code="BINDING_SCOPE_MISMATCH"
                    )
                if knowledge.catalog.restriction:
                    await knowledge.catalog.restriction.resource(actor, chain[0], write=True)

        async with self._resolve(NativeStructuredLineage).capture(
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            dataset_id=dataset_id,
            actor=actor,
            operation=operation,
            predecessor_snapshot_id=predecessor_snapshot_id,
            authorize=authorize,
        ):
            yield

    @model_bound("structured")
    async def ingest_dataset(
        self,
        *,
        tenant_id,
        workspace_id,
        filename,
        content,
        actor,
        source_catalog_id,
        catalog_workspace_id=None,
    ):
        from flyquery.core.services.datasets.dataset_service import DatasetService
        from flyquery.core.services.ingestion.ingest_service import IngestService
        from flyquery.interfaces.datasets import DatasetCreate

        with native_scope("structured", tenant_id, workspace_id, actor):
            dataset = await self._resolve(DatasetService).create(
                tenant_id,
                UUID(workspace_id),
                DatasetCreate(
                    name=filename[:150] + "-" + source_catalog_id,
                    metadata_json={"catalog_source_id": source_catalog_id},
                ),
            )
            async with self.structured_lineage(
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                dataset_id=str(dataset["id"]),
                actor=actor,
                catalog_workspace_id=catalog_workspace_id,
                source_catalog_id=source_catalog_id,
                operation="upload",
            ):
                result = await self._resolve(IngestService).ingest_upload(
                    tenant_id=tenant_id,
                    workspace_id=UUID(workspace_id),
                    dataset_id=dataset["id"],
                    filename=filename,
                    file_bytes=content,
                    actor=actor,
                    dataset_name=dataset["name"],
                )
        if not result.tables:
            raise ServiceUnavailableException(
                "The retained ingestion pipeline produced no ready tables; "
                "verify reader/model/index prerequisites",
                code="DATASET_INGEST_INCOMPLETE",
            )
        return {
            "dataset_id": str(dataset["id"]),
            "file_id": str(result.file_id),
            "tables": _json(result.tables),
        }

    @model_bound("structured")
    async def append_dataset_file(
        self,
        *,
        tenant_id,
        workspace_id,
        dataset_id,
        filename,
        content,
        actor,
        source_catalog_id,
        catalog_workspace_id=None,
    ):
        from flyquery.core.services.datasets.dataset_service import DatasetService
        from flyquery.core.services.ingestion.ingest_service import IngestService

        from koinon.knowledge.dataset_dtos import NativeDatasetFile

        with native_scope("structured", tenant_id, workspace_id, actor):
            dataset = await self._resolve(DatasetService).get(UUID(dataset_id))
            if (
                dataset is None
                or str(dataset.get("id")) != dataset_id
                or dataset.get("tenant_id") != tenant_id
                or str(dataset.get("workspace_id")) != workspace_id
                or dataset.get("status") != "ACTIVE"
            ):
                raise ForbiddenException(
                    "An active dataset in the admitted native scope is required",
                    code="DATASET_SCOPE_MISMATCH",
                )
            async with self.structured_lineage(
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                dataset_id=dataset_id,
                actor=actor,
                catalog_workspace_id=catalog_workspace_id,
                source_catalog_id=source_catalog_id,
                operation="upload",
            ):
                result = await self._resolve(IngestService).ingest_upload(
                    tenant_id=tenant_id,
                    workspace_id=UUID(workspace_id),
                    dataset_id=UUID(dataset_id),
                    filename=filename,
                    file_bytes=content,
                    actor=actor,
                    dataset_name=dataset["name"],
                    workspace_locale=dataset.get("default_locale"),
                    max_tables=128,
                    append_only=True,
                )
        return NativeDatasetFile.model_validate(
            {"file_id": result.file_id, "tables": _json(result.tables)}
        ).model_dump(mode="json")

    @model_bound("canon")
    @evidence_bound("canon")
    async def search(
        self,
        *,
        tenant_id,
        workspace_id,
        source_ids,
        question,
        limit,
        answer,
        actor,
        catalog_workspace_id=None,
        _capture=None,
        _curated_retrieve=None,
        _knowledge_settings_snapshot=None,
    ):
        from flycanon.core.services.query.handlers import AnswerKnowledgeQuery, SearchKnowledgeQuery
        from flycanon.core.services.query.runtime import DocumentQueryOptions
        from flycanon.core.services.retrieval import curated_corpus
        from flycanon.interfaces.dtos.query import AnswerRequest, SearchRequest
        from pyfly.cqrs import DefaultQueryBus

        policy = request_knowledge_settings({
            "_knowledge_settings_snapshot": _knowledge_settings_snapshot, "tenant_id": tenant_id,
        })
        options = DocumentQueryOptions.model_validate(policy.documents.model_dump()) if policy else None
        purpose, _ = self.model_requirements("canon", "search", {
            "answer": answer, "source_ids": source_ids, "_curated_retrieve": _curated_retrieve,
            "_knowledge_settings_snapshot": policy,
        })

        if not source_ids and _curated_retrieve is None:
            raise InvalidRequestException(
                "A nonempty admitted source set is required", code="EMPTY_SOURCE_SCOPE"
            )
        curated = (
            curated_corpus.bind(
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                retrieve=_curated_retrieve,
                documents=bool(source_ids),
            )
            if _curated_retrieve is not None
            else nullcontext()
        )
        with native_scope("canon", tenant_id, workspace_id, actor), curated:
            bus = self._resolve(DefaultQueryBus)
            result = {"hits": []}
            if purpose != "rlm":
                result = _json(
                    await bus.query(
                        SearchKnowledgeQuery(
                            request=SearchRequest(
                                query=question,
                                top_k=max(limit, options.retrieval_top_k) if options else limit,
                                per_query_k=options.retrieval_per_query_k if options else None,
                                source_ids=source_ids,
                            ),
                            tenant_id=tenant_id,
                            workspace_id=workspace_id,
                            runtime_options=options,
                        )
                    )
                )
                if _capture is not None:
                    _capture.search(tenant_id, workspace_id, actor, result.get("hits", []))
            if answer:
                response = _json(
                    await bus.query(
                        AnswerKnowledgeQuery(
                            request=AnswerRequest(
                                question=question, top_k=options.answer_top_k if options else min(limit, 40),
                                source_ids=source_ids,
                                extended_reasoning=options.rlm_extended_reasoning if options else False,
                            ),
                            tenant_id=tenant_id,
                            workspace_id=workspace_id,
                            runtime_options=options,
                        )
                    )
                )
                result.update(
                    answer=response["answer"],
                    citations=response["citations"],
                    no_answer=response["no_answer"],
                )
                if purpose == "rlm" and _capture is not None and not response["no_answer"]:
                    result["hits"] = [
                        {
                            "chunk_id": read.source_part_id, "source_id": read.source_id,
                            "content": read.quote, "score": 1.0, "page": None,
                            "section_path": read.section,
                            "metadata": {
                                "source_version_id": read.source_version_id,
                                "extraction_id": read.extraction_id,
                                "source_part_id": read.source_part_id,
                                "source_part_sha256": read.source_part_sha256,
                                "page_basis": "recorded_loader", "recorded_page": read.recorded_page,
                            },
                        }
                        for read in _capture.documents.values()
                        if read.source_part_id is not None
                        and read.workspace_id == workspace_id
                        and read.source_id in source_ids
                    ]
            return result

    async def document_revision(self, *, tenant_id, workspace_id, source_id, actor, lock=False):
        from flycanon.core.services.sources.lineage.dtos import DocumentScope
        from flycanon.core.services.sources.lineage.service import DocumentLineage
        from flycanon.core.services.storage.object_store import ObjectStore
        from flycanon.models.repositories import SourceRepository

        with native_scope("canon", tenant_id, workspace_id, actor):
            lineage = DocumentLineage(self._resolve(SourceRepository), self._resolve(ObjectStore))
            await lineage.require_schema()
            scope = DocumentScope(tenant_id, workspace_id, actor)
            if lock:
                from flycanon.core.services.sources.lineage.service import conditions
                from flycanon.models.entities.source_lineage import source_heads
                from sqlalchemy import select

                async with lineage.sources.session() as session:
                    head = (
                        (
                            await session.execute(
                                select(source_heads)
                                .where(*conditions(source_heads, scope, source_id))
                                .with_for_update(read=True)
                            )
                        )
                        .mappings()
                        .first()
                    )
            else:
                head = await lineage.head(scope, source_id)
            return (
                {"source_version_id": head["version_id"], "extraction_id": head["extraction_id"]}
                if head
                else None
            )

    async def document_parts(
        self, *, tenant_id, workspace_id, source_id, source_version_id, extraction_id, part_ids, actor
    ):
        from flycanon.core.services.sources.lineage.dtos import DocumentScope
        from flycanon.core.services.sources.lineage.service import DocumentLineage
        from flycanon.core.services.sources.lineage.whole_read import WholeDocumentReader
        from flycanon.core.services.storage.object_store import ObjectStore
        from flycanon.models.repositories import SourceRepository

        with native_scope("canon", tenant_id, workspace_id, actor):
            reader = WholeDocumentReader(
                DocumentLineage(self._resolve(SourceRepository), self._resolve(ObjectStore))
            )
            return await reader.resolve_parts(
                DocumentScope(tenant_id, workspace_id, actor),
                source_id=source_id,
                source_version_id=source_version_id,
                extraction_id=extraction_id,
                part_ids=tuple(part_ids),
            )

    async def document_chunks(
        self,
        *,
        tenant_id,
        workspace_id,
        source_id,
        actor,
        offset=0,
        limit=50,
        page=None,
        section=None,
        q=None,
    ):
        from flycanon.models.entities.knowledge_chunk import KnowledgeChunkRow
        from flycanon.models.repositories import ChunkRepository, SourceRepository
        from sqlalchemy import func, select

        with native_scope("canon", tenant_id, workspace_id, actor):
            source = await self._resolve(SourceRepository).get(
                source_id, tenant_id=tenant_id, workspace_id=workspace_id
            )
            if source is None:
                raise ResourceNotFoundException(
                    "The persisted document is unavailable", code="DOCUMENT_NOT_FOUND"
                )
            filters = [
                KnowledgeChunkRow.tenant_id == tenant_id,
                KnowledgeChunkRow.workspace_id == workspace_id,
                KnowledgeChunkRow.source_id == source_id,
            ]
            if page is not None:
                filters.append(KnowledgeChunkRow.page == page)
            if section:
                filters.append(KnowledgeChunkRow.section_path.icontains(section, autoescape=True))
            if q:
                filters.append(KnowledgeChunkRow.content.icontains(q, autoescape=True))
            async with self._resolve(ChunkRepository).session() as session:
                total = int(
                    (
                        await session.execute(
                            select(func.count()).select_from(KnowledgeChunkRow).where(*filters)
                        )
                    ).scalar_one()
                )
                result = await session.execute(
                    select(KnowledgeChunkRow)
                    .where(*filters)
                    .order_by(KnowledgeChunkRow.index_in_source, KnowledgeChunkRow.id)
                    .offset(offset)
                    .limit(limit)
                )
                items = [
                    {
                        "id": row.id,
                        "index": row.index_in_source,
                        "total_chunks": row.total_chunks,
                        "text": row.content,
                        "char_start": row.char_start,
                        "char_end": row.char_end,
                        "page": row.page,
                        "section_path": row.section_path,
                        "embedding_model": row.embedding_model,
                    }
                    for row in result.scalars().all()
                ]
            return {
                "items": items,
                "offset": offset,
                "limit": limit,
                "total": total,
                "next_offset": offset + len(items) if offset + len(items) < total else None,
                "revision_sha256": ((source.metadata_json or {}).get("_persisted_original") or {}).get(
                    "sha256"
                )
                or source.content_sha256,
                "source_version_id": ((source.metadata_json or {}).get("_source_lineage") or {}).get(
                    "version_id"
                ),
                "extraction_id": ((source.metadata_json or {}).get("_source_lineage") or {}).get(
                    "extraction_id"
                ),
            }

    async def document_original(self, *, tenant_id, workspace_id, source_id, actor, max_bytes):
        from flycanon.core.services.storage.object_store import ObjectStore, ObjectTooLargeError
        from flycanon.models.repositories import SourceRepository

        with native_scope("canon", tenant_id, workspace_id, actor):
            source = await self._resolve(SourceRepository).get(
                source_id, tenant_id=tenant_id, workspace_id=workspace_id
            )
            if source is None or not source.object_store_key:
                raise ResourceNotFoundException(
                    "No persisted original is available", code="ORIGINAL_NOT_FOUND"
                )
            original = (source.metadata_json or {}).get("_persisted_original") or {
                "bytes": source.content_bytes,
                "sha256": source.content_sha256,
            }
            if original["bytes"] > max_bytes:
                raise PayloadTooLargeException(
                    "Original exceeds the download limit", code="ORIGINAL_TOO_LARGE"
                )
            try:
                content = await self._resolve(ObjectStore).get_bounded(source.object_store_key, max_bytes)
            except ObjectTooLargeError as error:
                raise PayloadTooLargeException(
                    "Original exceeds the download limit", code="ORIGINAL_TOO_LARGE"
                ) from error
            except NotImplementedError as error:
                raise ServiceUnavailableException(
                    "Configure an object store with bounded original reads", code="BOUNDED_READ_REQUIRED"
                ) from error
            except FileNotFoundError as error:
                raise ResourceNotFoundException(
                    "The original bytes are unavailable", code="ORIGINAL_NOT_FOUND"
                ) from error
            if len(content) > max_bytes:
                raise PayloadTooLargeException(
                    "Original exceeds the download limit", code="ORIGINAL_TOO_LARGE"
                )
            if len(content) != original["bytes"] or sha256(content).hexdigest() != original["sha256"]:
                raise ServiceUnavailableException(
                    "Original document integrity check failed", code="ORIGINAL_INTEGRITY_FAILED"
                )
            return {
                "content": content,
                "filename": source.filename or "document",
                "content_type": "application/octet-stream",
            }

    async def replace_document(
        self,
        *,
        tenant_id,
        workspace_id,
        source_id,
        filename,
        content,
        expected_sha256,
        actor,
        force_reingest=False,
        catalog_workspace_id=None,
        logical_source_key=None,
        operation_id=None,
        authorize_commit=None,
        expected_source_version_id=None,
        expected_extraction_id=None,
    ):
        if logical_source_key is not None:
            from koinon.knowledge.document_lineage import replace_document

            return await replace_document(
                self,
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                source_id=source_id,
                filename=filename,
                content=content,
                expected_sha256=expected_sha256,
                actor=actor,
                force_reingest=force_reingest,
                catalog_workspace_id=catalog_workspace_id,
                logical_source_key=logical_source_key,
                operation_id=operation_id,
                authorize_commit=authorize_commit,
                expected_source_version_id=expected_source_version_id,
                expected_extraction_id=expected_extraction_id,
            )
        from flycanon.core.services.sources.intake_service import IntakeService
        from flycanon.interfaces.dtos.source import SubmitSourceRequest
        from flycanon.models.entities.knowledge_chunk import KnowledgeChunkRow
        from flycanon.models.entities.source import SourceRow
        from flycanon.models.repositories import SourceRepository
        from sqlalchemy import func, select

        with native_scope("canon", tenant_id, workspace_id, actor):
            async with self._resolve(SourceRepository).session() as session:
                row = (
                    (
                        await session.execute(
                            select(SourceRow)
                            .where(
                                SourceRow.id == source_id,
                                SourceRow.tenant_id == tenant_id,
                                SourceRow.workspace_id == workspace_id,
                            )
                            .with_for_update()
                        )
                    )
                    .scalars()
                    .one_or_none()
                )
                if row is None:
                    raise ResourceNotFoundException(
                        "The persisted document is unavailable", code="DOCUMENT_NOT_FOUND"
                    )
                original = (row.metadata_json or {}).get("_persisted_original") or {
                    "sha256": row.content_sha256
                }
                new_digest = sha256(content).hexdigest()
                if original["sha256"] != expected_sha256 and (
                    force_reingest or original["sha256"] != new_digest
                ):
                    raise ConflictException(
                        "Document content changed; reload its current version",
                        code="CONTENT_VERSION_CONFLICT",
                    )
                filters = [
                    KnowledgeChunkRow.source_id == source_id,
                    KnowledgeChunkRow.tenant_id == tenant_id,
                    KnowledgeChunkRow.workspace_id == workspace_id,
                ]
                previous_count = int(
                    (
                        await session.execute(
                            select(func.count()).select_from(KnowledgeChunkRow).where(*filters)
                        )
                    ).scalar_one()
                )
                previous_ids = list(
                    (
                        await session.execute(
                            select(KnowledgeChunkRow.id)
                            .where(*filters)
                            .order_by(KnowledgeChunkRow.index_in_source, KnowledgeChunkRow.id)
                            .limit(100)
                        )
                    )
                    .scalars()
                    .all()
                )
                if original["sha256"] == new_digest and not force_reingest:
                    return {
                        "previous_chunk_count": previous_count,
                        "invalidated_chunk_ids": [],
                        "chunk_ids_complete": True,
                        "n_chunks": row.n_chunks,
                        "unchanged": True,
                    }
                async with self.model_connections(
                    "canon",
                    tenant_id,
                    workspace_id,
                    actor,
                    purpose="ingest",
                    roles=("documents.embedding",),
                    catalog_workspace_id=catalog_workspace_id,
                ):
                    updated = await self._resolve(IntakeService).replace(
                        source_id=source_id,
                        request=SubmitSourceRequest(),
                        content=content,
                        tenant_id=tenant_id,
                        workspace_id=workspace_id,
                        filename=filename,
                        actor=actor,
                        correlation_id=str(uuid4()),
                        versioned_originals=True,
                    )
                persisted = (updated.metadata_json or {}).get("_persisted_original") or {}
                if not updated.object_store_key or persisted.get("sha256") != new_digest:
                    raise ServiceUnavailableException(
                        "The replacement original was not persisted; configure durable original storage",
                        code="DOCUMENT_ORIGINAL_UNAVAILABLE",
                    )
                return {
                    "previous_chunk_count": previous_count,
                    "invalidated_chunk_ids": previous_ids,
                    "chunk_ids_complete": previous_count <= len(previous_ids),
                    "n_chunks": updated.n_chunks,
                    "unchanged": False,
                }

    async def reupload_table(
        self,
        *,
        tenant_id,
        workspace_id,
        dataset_id,
        table_id,
        filename,
        content,
        expected_snapshot_id,
        actor,
        catalog_workspace_id=None,
        operation="replace",
    ):
        from flyquery.core.services.datasets.dataset_service import DatasetService
        from flyquery.core.services.ingestion.ingest_service import IngestService
        from flyquery.core.services.tables.table_service import TableService

        with native_scope("structured", tenant_id, workspace_id, actor):
            table = await self._resolve(TableService).get(
                UUID(table_id), tenant_id=tenant_id, workspace_id=UUID(workspace_id)
            )
            dataset = await self._resolve(DatasetService).get(UUID(dataset_id))
            if (
                table is None
                or dataset is None
                or str(table["dataset_id"]) != dataset_id
                or table["tenant_id"] != tenant_id
                or dataset["tenant_id"] != tenant_id
                or str(table["workspace_id"]) != workspace_id
                or str(dataset["workspace_id"]) != workspace_id
            ):
                raise ForbiddenException(
                    "The table is outside the selected dataset/workspace", code="DOMAIN_SCOPE_MISMATCH"
                )
            previous = str(table.get("current_snapshot_id") or "")
            if previous != expected_snapshot_id:
                raise ConflictException(
                    "The table snapshot changed; reload the current schema", code="CONTENT_VERSION_CONFLICT"
                )
            purpose, roles = self.model_requirements("structured", "reupload_table", {})
            async with (
                self.model_connections(
                    "structured",
                    tenant_id,
                    workspace_id,
                    actor,
                    purpose=purpose,
                    roles=roles,
                    catalog_workspace_id=catalog_workspace_id,
                ),
                self.structured_lineage(
                    tenant_id=tenant_id,
                    workspace_id=workspace_id,
                    dataset_id=dataset_id,
                    table_id=table_id,
                    actor=actor,
                    catalog_workspace_id=catalog_workspace_id,
                    operation=operation,
                    predecessor_snapshot_id=expected_snapshot_id,
                ),
            ):
                result = await self._resolve(IngestService).ingest_reupload(
                    tenant_id=tenant_id,
                    workspace_id=UUID(workspace_id),
                    dataset_id=UUID(dataset_id),
                    table_id=UUID(table_id),
                    filename=filename,
                    file_bytes=content,
                    actor=actor,
                    dataset_name=dataset["name"],
                )
            matches = [entry for entry in result.tables if str(entry.table_id) == table_id]
            if len(matches) != 1 or not matches[0].snapshot_id:
                raise ServiceUnavailableException(
                    "Re-upload did not produce the selected table snapshot", code="DATASET_INGEST_INCOMPLETE"
                )
            updated = matches[0]
            return {
                "file_id": str(result.file_id),
                "previous_snapshot_id": previous,
                "snapshot_id": str(updated.snapshot_id),
                "n_columns": updated.n_columns,
                "n_rows_actual": updated.n_rows_estimate,
            }

    async def table_original(
        self,
        *,
        tenant_id,
        workspace_id,
        dataset_id,
        table_id,
        expected_snapshot_id,
        actor,
        max_bytes,
    ):
        from flyquery.config import FlyquerySettings
        from flyquery.core.services.storage.object_store import ObjectStore
        from pyfly.data.transaction import infrastructure_unit

        try:
            parameters = {
                "tenant": tenant_id,
                "workspace": UUID(workspace_id),
                "dataset": UUID(dataset_id),
                "table": UUID(table_id),
                "snapshot": UUID(expected_snapshot_id),
            }
        except (ValueError, TypeError, AttributeError) as error:
            raise InvalidRequestException(
                "Supply the current table snapshot in If-Match", code="CONTENT_VERSION_REQUIRED"
            ) from error
        with native_scope("structured", tenant_id, workspace_id, actor):
            async with infrastructure_unit(
                self._resolve(FlyquerySettings).native_datasource(), read_only=True
            ) as session:
                row = (
                    (
                        await session.execute(
                            text("""
                    SELECT f.id, f.original_filename, f.size_bytes, f.content_hash_sha256, f.object_store_key
                    FROM flyquery_tables t
                    JOIN flyquery_files f ON f.id = t.source_file_id
                        AND f.tenant_id = t.tenant_id AND f.workspace_id = t.workspace_id
                        AND f.dataset_id = t.dataset_id
                    JOIN flyquery_schema_snapshots ss ON ss.id = t.current_snapshot_id
                        AND ss.table_id = t.id AND ss.tenant_id = t.tenant_id
                        AND ss.workspace_id = t.workspace_id AND ss.dataset_id = t.dataset_id
                    WHERE t.id = :table AND t.dataset_id = :dataset AND t.tenant_id = :tenant
                        AND t.workspace_id = :workspace AND t.current_snapshot_id = :snapshot
                        AND t.is_active = true AND t.kind = 'UPLOADED' AND ss.status = 'READY'
                """),
                            parameters,
                        )
                    )
                    .mappings()
                    .one_or_none()
                )
            if row is None:
                raise ConflictException(
                    "The table snapshot or stored upload changed; reload its schema",
                    code="CONTENT_VERSION_CONFLICT",
                )
            store = self._resolve(ObjectStore)
            if row["size_bytes"] > max_bytes:
                raise PayloadTooLargeException(
                    "Stored upload exceeds the byte limit", code="ORIGINAL_TOO_LARGE"
                )
            try:
                metadata = await store.head(row["object_store_key"])
                if metadata.size_bytes > max_bytes:
                    raise PayloadTooLargeException(
                        "Stored upload exceeds the byte limit", code="ORIGINAL_TOO_LARGE"
                    )
                stream = await store.get(row["object_store_key"])
                content = bytearray()
                try:
                    async for chunk in stream:
                        if len(content) + len(chunk) > max_bytes:
                            raise PayloadTooLargeException(
                                "Stored upload exceeds the byte limit", code="ORIGINAL_TOO_LARGE"
                            )
                        content.extend(chunk)
                finally:
                    close = getattr(stream, "aclose", None)
                    if close is not None:
                        await close()
            except FileNotFoundError as error:
                raise ResourceNotFoundException(
                    "The original upload is unavailable", code="ORIGINAL_NOT_FOUND"
                ) from error
            if len(content) != row["size_bytes"] or sha256(content).hexdigest() != row["content_hash_sha256"]:
                raise ServiceUnavailableException(
                    "Stored upload integrity check failed", code="ORIGINAL_INTEGRITY_FAILED"
                )
            return {
                "file_id": str(row["id"]),
                "filename": row["original_filename"],
                "content": bytes(content),
            }

    @evidence_bound("structured")
    async def query(
        self,
        *,
        tenant_id,
        workspace_id,
        dataset_id,
        dataset_allowlist,
        question,
        conversation_id,
        sql,
        actor,
        catalog_workspace_id=None,
        _capture=None,
        _knowledge_settings_snapshot=None,
    ):
        from flyquery.core.services.datasets.dataset_service import DatasetService
        from flyquery.web.controllers.query_controller import QueryController

        policy = request_knowledge_settings({
            "_knowledge_settings_snapshot": _knowledge_settings_snapshot, "tenant_id": tenant_id,
        })
        with native_scope("structured", tenant_id, workspace_id, actor) as request:
            dataset = await self._resolve(DatasetService).get(UUID(dataset_id))
            if (
                dataset is None
                or dataset["tenant_id"] != tenant_id
                or str(dataset["workspace_id"]) != workspace_id
                or dataset_id not in dataset_allowlist
            ):
                raise InvalidRequestException("Native dataset scope mismatch", code="DOMAIN_SCOPE_MISMATCH")
            if conversation_id:
                from flyquery.core.services.query.conversation_service import ConversationService

                conversation = await self._resolve(ConversationService).get_with_turns(UUID(conversation_id))
                if (
                    not conversation
                    or conversation.get("tenant_id") != tenant_id
                    or str(conversation.get("workspace_id")) != workspace_id
                    or any(
                        turn.get("tenant_id") != tenant_id or str(turn.get("workspace_id")) != workspace_id
                        for turn in conversation.get("turns", [])
                    )
                ):
                    raise InvalidRequestException(
                        "Conversation belongs to another context", code="INVALID_CONVERSATION"
                    )
            if sql is not None:
                from flyquery.core.services.execution.ast_classifier import AstClassifier
                from flyquery.interfaces.query import AnswerResponse
                from flyquery.interfaces.sql_execute import SqlExecuteRequest
                from flyquery.web.controllers.sql_execute_controller import SqlExecuteController

                if AstClassifier().classify(sql).classification != "SELECT":
                    raise InvalidRequestException(
                        "This query surface accepts read-only SQL", code="READ_ONLY_SQL_REQUIRED"
                    )
                response = await self._resolve(SqlExecuteController).execute(
                    request, SqlExecuteRequest(dataset_id=UUID(dataset_id), sql=sql)
                )
                raw = _json(response)
                if _capture is not None:
                    attempts = [
                        row
                        for row in _capture.sql_attempts
                        if row.executed
                        and row.outcome == "executed"
                        and row.statement_sha256 == sha256(sql.encode()).hexdigest()
                    ]
                    if len(attempts) == 1:
                        raw["snapshot_pins"] = dict(attempts[0].snapshot_pins)
                output = AnswerResponse.model_validate(raw).model_dump(mode="json")
                if _capture is not None:
                    _capture.query(tenant_id, workspace_id, actor, dataset_id, output)
                return output
            purpose, roles = self.model_requirements(
                "structured", "query", {"_knowledge_settings_snapshot": policy}
            )
            async with self.model_connections(
                "structured",
                tenant_id,
                workspace_id,
                actor,
                purpose=purpose,
                roles=roles,
                catalog_workspace_id=catalog_workspace_id,
            ):
                controller = self._resolve(QueryController)
                async with controller._session_factory() as session:
                    if policy:
                        effective_settings = controller._settings.model_copy(
                            update=policy.structured.model_dump()
                        )
                        pipeline = controller._build_service(session, settings=effective_settings)
                    else:
                        pipeline = controller._build_service(session)
                    result = await pipeline.answer(
                        tenant_id=tenant_id,
                        workspace_id=UUID(workspace_id),
                        dataset_id=UUID(dataset_id),
                        question=question,
                        scopes={"flyquery.query:read", "flyquery.sql:execute"},
                        dataset_allowlist=dataset_allowlist,
                        conversation_id=UUID(conversation_id) if conversation_id else None,
                    )
            output = _json(result)
            if _capture is not None:
                _capture.query(tenant_id, workspace_id, actor, dataset_id, output)
            return output

    async def schema(self, *, tenant_id, workspace_id, dataset_id, actor, _capture=None):
        from flyquery.core.services.tables.table_service import TableService

        with native_scope("structured", tenant_id, workspace_id, actor):
            service = self._resolve(TableService)
            tables = await service.list_for_dataset(
                UUID(dataset_id), tenant_id=tenant_id, workspace_id=UUID(workspace_id)
            )
            output = []
            for table in tables:
                objects = await service.list_objects(
                    table["id"], tenant_id=tenant_id, workspace_id=UUID(workspace_id)
                )
                if _capture is not None:
                    _capture.schema(tenant_id, workspace_id, actor, dataset_id, table, objects)
                columns = [
                    {
                        "id": str(column["id"]),
                        "name": column["qualified_name"].rsplit(".", 1)[-1],
                        "data_type": column.get("data_type") or "unknown",
                        "description": column.get("description"),
                        "pii_tag": column.get("pii_tag"),
                    }
                    for column in objects
                    if column["kind"] == "COLUMN"
                ]
                output.append(
                    {
                        "id": str(table["id"]),
                        "name": table["name"],
                        "sheet_or_json_path": table.get("sheet_or_json_path"),
                        "snapshot_id": str(table["current_snapshot_id"])
                        if table.get("current_snapshot_id")
                        else None,
                        "columns": columns,
                    }
                )
            return {"tables": output}

    async def lineage(self, *, domain, tenant_id, workspace_id, native_id, entity_kind, actor, limit):
        nodes, edges = [], []
        with native_scope(domain, tenant_id, workspace_id, actor):
            if domain == "canon":
                from flycanon.models.repositories import ChunkRepository

                chunks = await self._resolve(ChunkRepository).list_for_source(native_id)
                for chunk in chunks[:limit]:
                    if chunk.tenant_id != tenant_id or chunk.workspace_id != workspace_id:
                        raise InvalidRequestException("Fragment scope mismatch", code="DOMAIN_SCOPE_MISMATCH")
                    identifier = "canon:chunk:" + chunk.id
                    nodes.append(
                        {
                            "id": identifier,
                            "label": f"Chunk {chunk.index_in_source + 1}",
                            "kind": "chunk",
                            "native_id": chunk.id,
                        }
                    )
                    edges.append({"source": "$asset", "target": identifier, "label": "extracted"})
            else:
                from flyquery.core.services.tables.table_service import TableService

                tables = await self._resolve(TableService).list_for_dataset(
                    UUID(native_id), tenant_id=tenant_id, workspace_id=UUID(workspace_id)
                )
                for table in tables[:limit]:
                    identifier = "structured:table:" + str(table["id"])
                    nodes.append(
                        {
                            "id": identifier,
                            "label": table["name"],
                            "kind": "table",
                            "native_id": str(table["id"]),
                        }
                    )
                    edges.append({"source": "$asset", "target": identifier, "label": "materialized"})
                    if table.get("current_snapshot_id"):
                        snapshot = "structured:snapshot:" + str(table["current_snapshot_id"])
                        nodes.append(
                            {
                                "id": snapshot,
                                "label": "Current snapshot",
                                "kind": "index_version",
                                "native_id": str(table["current_snapshot_id"]),
                            }
                        )
                        edges.append({"source": identifier, "target": snapshot, "label": "current"})
        return {"nodes": nodes, "edges": edges}
