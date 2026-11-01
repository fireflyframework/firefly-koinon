# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Scoped native index inspection; labels never stand in for persisted vectors."""

from hashlib import sha256
from uuid import UUID

from pyfly.container import component
from pyfly.data.relational.datasource_registry import DataSourceRegistry
from pyfly.data.transaction import infrastructure_unit
from pyfly.kernel import ServiceUnavailableException
from sqlalchemy import text

from koinon.knowledge.adapters import NativeDomains, native_scope
from koinon.knowledge.indexes.ann import ann_qualified


def index_id(tenant_id, workspace_id, domain, native_id):
    return sha256("\x1f".join((tenant_id, workspace_id, domain, native_id)).encode()).hexdigest()


def index_filters(alias=""):
    prefix = alias + "." if alias else ""
    return "".join(
        f" AND (CAST(:{key} AS {kind}) IS NULL OR {prefix}{column}=:{key})"
        for key, column, kind in (
            ("native_id", "id", "text"),
            ("status", "status", "text"),
            ("dimensions", "dimensions", "integer"),
            ("model_id", "model", "text"),
            ("provider_kind", "provider", "text"),
        )
    )


@component(name="knowledge.index_adapter")
class NativeIndexAdapter:
    def __init__(self, datasources: DataSourceRegistry, domains: NativeDomains):
        self.datasources, self.domains = datasources, domains

    def source(self, domain):
        try:
            return self.datasources.get("canon" if domain == "documents" else "structured")
        except KeyError as error:
            raise ServiceUnavailableException(
                "Enable the selected native knowledge data source and apply its migrations",
                code="KNOWLEDGE_INDEX_REQUIRED",
            ) from error

    async def discover(
        self,
        *,
        tenant_id,
        native_workspace_id,
        catalog_workspace_id,
        domain,
        actor,
        limit,
        offset,
        native_id=None,
        status=None,
        dimensions=None,
        model_id=None,
        provider_kind=None,
    ):
        native = "canon" if domain == "documents" else "structured"
        with native_scope(native, tenant_id, native_workspace_id, actor):
            async with infrastructure_unit(self.source(domain)) as session:
                if domain == "documents":
                    params = {
                        "tenant": tenant_id,
                        "workspace": native_workspace_id,
                        "limit": limit,
                        "offset": offset,
                        "native_id": native_id,
                        "status": status,
                        "dimensions": dimensions,
                        "model_id": model_id,
                        "provider_kind": provider_kind,
                    }
                    count = await session.scalar(
                        text(
                            "SELECT count(*) FROM canon_embedding_sets "
                            "WHERE tenant_id=:tenant AND workspace_id=:workspace" + index_filters()
                        ),
                        params,
                    )
                    from pyfly.agentic.vectorstores.scoped import scope_namespace

                    params["namespace"] = scope_namespace(tenant_id, native_workspace_id)
                    await session.execute(
                        text("SELECT set_config('app.scope_namespace',:namespace,true)"), params
                    )
                    rows = (
                        (
                            await session.execute(
                                text(
                                    "SELECT s.*,s.id=w.active_embedding_set_id AS is_active,"
                                    "(SELECT count(*) FROM canon_chunks c WHERE c.tenant_id=:tenant "
                                    "AND c.workspace_id=:workspace) AS actual_chunks,"
                                    "(SELECT count(*) FROM canon_chunks c JOIN canon_chunk_vectors v "
                                    "ON v.id=c.id AND v.set_id=s.id AND v.namespace=:namespace "
                                    "AND v.text=c.content WHERE c.tenant_id=:tenant "
                                    "AND c.workspace_id=:workspace) AS actual_vectors,"
                                    "EXISTS(SELECT 1 FROM pg_catalog.pg_indexes i "
                                    "WHERE i.schemaname='public' "
                                    "AND i.tablename='canon_chunk_vectors' "
                                    "AND i.indexname=s.index_name) AS indexed "
                                    "FROM canon_embedding_sets s JOIN canon_workspaces w "
                                    "ON w.tenant_id=s.tenant_id "
                                    "AND w.id=s.workspace_id WHERE s.tenant_id=:tenant "
                                    "AND s.workspace_id=:workspace "
                                    + index_filters("s")
                                    + " ORDER BY s.created_at DESC,s.id LIMIT :limit OFFSET :offset"
                                ),
                                params,
                            )
                        )
                        .mappings()
                        .all()
                    )
                    items = []
                    for row in rows:
                        indexed = await ann_qualified(
                            session, domain=domain, set_id=row["id"], dimensions=row["dimensions"]
                        )
                        items.append(
                            {
                                "id": index_id(tenant_id, catalog_workspace_id, domain, row["id"]),
                                "workspace_id": catalog_workspace_id,
                                "domain": domain,
                                "native_id": row["id"],
                                "space_id": row["id"],
                                "provider_kind": row["provider"],
                                "model_id": row["model"],
                                "dimensions": row["dimensions"],
                                "storage_dimensions": row["dimensions"],
                                "status": row["status"],
                                "active": bool(row["is_active"]),
                                "revision": 0,
                                "chunk_count": row["actual_chunks"],
                                "vector_count": row["actual_vectors"],
                                "indexed": indexed,
                                "qualification": "coverage_and_ann_passed"
                                if row["actual_chunks"] == row["actual_vectors"] and indexed
                                else "stale",
                                **{
                                    key: row[key].isoformat() if row[key] else None
                                    for key in ("created_at", "ready_at", "activated_at", "retired_at")
                                },
                            }
                        )
                    return {"items": items, "total": count or 0}
                return await self.structured_discovery(
                    session,
                    tenant_id=tenant_id,
                    workspace_id=native_workspace_id,
                    catalog_workspace_id=catalog_workspace_id,
                    limit=limit,
                    offset=offset,
                    native_id=native_id,
                    status=status,
                    dimensions=dimensions,
                    model_id=model_id,
                    provider_kind=provider_kind,
                )

    async def structured_discovery(
        self,
        session,
        *,
        tenant_id,
        workspace_id,
        catalog_workspace_id,
        limit,
        offset,
        native_id=None,
        status=None,
        dimensions=None,
        model_id=None,
        provider_kind=None,
    ):
        from flyquery.models.repositories.embedding_set_repository import EmbeddingSetRepository

        params = {
            "tenant": tenant_id,
            "workspace": UUID(workspace_id),
            "limit": limit,
            "offset": offset,
            "native_id": native_id,
            "status": status,
            "dimensions": dimensions,
            "model_id": model_id,
            "provider_kind": provider_kind,
        }
        legacy = (
            (
                await session.execute(
                    text("""
            SELECT count(*) AS total,count(embedding) AS vectors,
              count(DISTINCT embedding_model) AS models,min(embedding_model) AS model
            FROM flyquery_schema_objects WHERE tenant_id=:tenant
              AND workspace_id=:workspace AND is_active=true
        """),
                    params,
                )
            )
            .mappings()
            .one()
        )
        exists = await session.scalar(text("SELECT to_regclass('public.flyquery_embedding_sets')"))
        count = (
            await session.scalar(
                text(
                    "SELECT count(*) FROM flyquery_embedding_sets WHERE tenant_id=:tenant AND wor"
                    "kspace_id=:workspace" + index_filters()
                ),
                params,
            )
            if exists
            else 0
        )
        include_legacy = (
            bool(legacy["vectors"] or (legacy["total"] and not count))
            and native_id in {None, "legacy-inline"}
            and status in {None, "legacy"}
            and dimensions is None
            and provider_kind is None
            and (model_id is None or (legacy["models"] == 1 and model_id == legacy["model"]))
        )
        active = (
            await session.scalar(
                text(
                    "SELECT id FROM flyquery_embedding_sets WHERE tenant_id=:tenant AND workspace"
                    "_id=:workspace AND status='active'"
                ),
                params,
            )
            if exists
            else None
        )
        total = int(count or 0) + int(include_legacy)
        if not exists:
            rows = []
        else:
            rows = list(
                (
                    await session.execute(
                        text(
                            """
                SELECT id,provider,model,dimensions,status,created_at,ready_at,activated_at,retired_at
                FROM flyquery_embedding_sets WHERE tenant_id=:tenant AND workspace_id=:workspace
            """
                            + index_filters()
                            + " ORDER BY created_at DESC,id LIMIT :limit OFFSET :offset"
                        ),
                        params,
                    )
                )
                .mappings()
                .all()
            )
        items = []
        indexed = (
            await ann_qualified(session, domain="structured", set_id="", dimensions=1536) if exists else False
        )
        repository = EmbeddingSetRepository(self.source("structured").sessionmaker)
        for row in rows:
            counts = await repository.counts(tenant_id=tenant_id, workspace_id=workspace_id, set_id=row["id"])
            complete = counts["chunk_count"] == counts["vector_count"]
            items.append(
                {
                    "id": index_id(tenant_id, catalog_workspace_id, "structured", row["id"]),
                    "workspace_id": catalog_workspace_id,
                    "domain": "structured",
                    "native_id": row["id"],
                    "space_id": row["id"],
                    "provider_kind": row["provider"],
                    "model_id": row["model"],
                    "dimensions": row["dimensions"],
                    "storage_dimensions": 1536,
                    "status": row["status"],
                    "active": row["id"] == active,
                    "revision": 0,
                    **counts,
                    "indexed": indexed,
                    "qualification": "coverage_and_ann_passed" if complete and indexed else "stale",
                    **{
                        key: row[key].isoformat() if row[key] else None
                        for key in ("created_at", "ready_at", "activated_at", "retired_at")
                    },
                }
            )
        if include_legacy and offset <= int(count or 0) < offset + limit:
            items.append(
                {
                    "id": index_id(tenant_id, catalog_workspace_id, "structured", "legacy-inline"),
                    "workspace_id": catalog_workspace_id,
                    "domain": "structured",
                    "native_id": "legacy-inline",
                    "space_id": None,
                    "provider_kind": None,
                    "model_id": legacy["model"] if legacy["models"] == 1 else None,
                    "dimensions": None,
                    "storage_dimensions": 1536,
                    "status": "legacy",
                    "active": active is None,
                    "revision": 0,
                    "chunk_count": legacy["total"],
                    "vector_count": legacy["vectors"],
                    "indexed": None,
                    "qualification": "legacy_provider_history_required",
                }
            )
        return {"items": items, "total": total}

    async def workspace_exists(self, *, tenant_id, workspace_id, domain, actor) -> bool:
        if domain not in {"documents", "structured"}:
            raise ValueError("Select one knowledge domain")
        native = "canon" if domain == "documents" else "structured"
        control = self.datasources.get(native + "_admin")
        table = "public.canon_workspaces" if domain == "documents" else "public.flyquery_workspaces"
        with native_scope(native, tenant_id, workspace_id, actor):
            async with infrastructure_unit(control, read_only=True) as session:
                found = await session.scalar(
                    text(
                        "SELECT EXISTS(SELECT 1 FROM " + table + " WHERE tenant_id=:tenant AND id=:workspace)"
                    ),
                    {
                        "tenant": tenant_id,
                        "workspace": workspace_id if domain == "documents" else UUID(workspace_id),
                    },
                )
                if type(found) is not bool:
                    raise RuntimeError("Native workspace observation is unavailable")
                return found

    async def overview(self, *, tenant_id, workspace_id, domain, actor):
        native = "canon" if domain == "documents" else "structured"
        with native_scope(native, tenant_id, workspace_id, actor):
            async with infrastructure_unit(self.source(domain)) as session:
                if domain == "documents":
                    params = {"tenant": tenant_id, "workspace": workspace_id}
                    active = await session.scalar(
                        text(
                            "SELECT active_embedding_set_id FROM canon_workspaces WHERE tenant_id"
                            "=:tenant AND id=:workspace"
                        ),
                        params,
                    )
                    count = await session.scalar(
                        text(
                            "SELECT count(*) FROM canon_chunks WHERE tenant_id=:tenant AND worksp"
                            "ace_id=:workspace"
                        ),
                        params,
                    )
                else:
                    params = {"tenant": tenant_id, "workspace": UUID(workspace_id)}
                    exists = await session.scalar(
                        text("SELECT to_regclass('public.flyquery_embedding_sets')")
                    )
                    active = (
                        await session.scalar(
                            text(
                                "SELECT id FROM flyquery_embedding_sets WHERE tenant_id=:tenant A"
                                "ND workspace_id=:workspace AND status='active'"
                            ),
                            params,
                        )
                        if exists
                        else None
                    )
                    count = await session.scalar(
                        text(
                            "SELECT count(*) FROM flyquery_schema_objects WHERE tenant_id=:tenant"
                            " AND workspace_id=:workspace AND is_active=true"
                        ),
                        params,
                    )
                return {"active_native_id": active, "chunk_count": count or 0}

    async def create(self, record, *, actor, endpoint):
        native = "canon" if record.domain == "documents" else "structured"
        with native_scope(native, record.tenant_id, record.native_workspace_id, actor):
            if record.domain == "documents":
                from flycanon.core.services.embeddings.embedding_sets import EmbeddingSetService

                service = self.domains._resolve(EmbeddingSetService)
                rows = await service.list_for(
                    tenant_id=record.tenant_id, workspace_id=record.native_workspace_id
                )
                if not any(row.id == record.native_id for row in rows):
                    await service.create(
                        tenant_id=record.tenant_id,
                        workspace_id=record.native_workspace_id,
                        provider=record.provider_kind,
                        model=record.model_id,
                        dimensions=record.dimensions,
                        created_by=actor,
                        set_id=record.native_id,
                        endpoint=endpoint,
                        status="queued",
                        note="Created by a durable authorized knowledge index job",
                    )
                from flycanon.models.entities.embedding_set import config_fingerprint

                expected = config_fingerprint(
                    provider=record.provider_kind,
                    model=record.model_id,
                    dimensions=record.dimensions,
                    endpoint=endpoint,
                    api_version="",
                )
                indexed = next(
                    (
                        value
                        for value in await service.list_for(
                            tenant_id=record.tenant_id, workspace_id=record.native_workspace_id
                        )
                        if value.id == record.native_id
                    ),
                    None,
                )
                if indexed is None or (
                    indexed.provider,
                    indexed.model,
                    indexed.dimensions,
                    indexed.config_fingerprint,
                ) != (record.provider_kind, record.model_id, record.dimensions, expected):
                    raise ValueError("The existing native document target has different immutable provenance")
                return expected
            async with infrastructure_unit(self.source(record.domain)) as session:
                await session.execute(
                    text("""
                    INSERT INTO flyquery_embedding_sets
                      (id,tenant_id,workspace_id,provider,model,dimensions,config_fingerprint,status,created_by)
                    VALUES(:id,:tenant,:workspace,:provider,:model,:dimensions,:fingerprint,'queued',:actor)
                    ON CONFLICT(id) DO NOTHING
                """),
                    {
                        "id": record.native_id,
                        "tenant": record.tenant_id,
                        "workspace": UUID(record.native_workspace_id),
                        "provider": record.provider_kind,
                        "model": record.model_id,
                        "dimensions": record.dimensions,
                        "fingerprint": record.embedding_fingerprint,
                        "actor": actor,
                    },
                )
            return record.embedding_fingerprint

    async def transition_initial(self, record, status, *, actor) -> bool:
        if record.domain not in {"documents", "structured"} or status not in {"building", "ready"}:
            raise ValueError("Only initial knowledge build states may be projected")
        documents = record.domain == "documents"
        table = "public.canon_embedding_sets" if documents else "public.flyquery_embedding_sets"
        with native_scope(
            "canon" if documents else "structured", record.tenant_id, record.native_workspace_id, actor
        ):
            async with infrastructure_unit(self.source(record.domain)) as session:
                transitioned = await session.scalar(
                    text(f"""
                    UPDATE {table}
                    SET status=CASE WHEN status='ready' THEN status ELSE :status END,
                        ready_at=CASE WHEN :status='ready' THEN COALESCE(ready_at,now()) ELSE ready_at END
                    WHERE id=:id AND tenant_id=:tenant AND workspace_id=:workspace
                      AND provider=:provider AND model=:model AND dimensions=:dimensions
                      AND config_fingerprint=:fingerprint AND created_by=:actor
                      AND activated_at IS NULL AND retired_at IS NULL
                      AND (status IN ('building','ready')
                        OR (status='queued' AND (:status='building' OR :structured_ready)))
                    RETURNING status
                    """),
                    {
                        "status": status,
                        "actor": actor,
                        "structured_ready": not documents and status == "ready",
                        "id": record.native_id,
                        "tenant": record.tenant_id,
                        "workspace": record.native_workspace_id
                        if documents
                        else UUID(record.native_workspace_id),
                        "provider": record.provider_kind,
                        "model": record.model_id,
                        "dimensions": record.dimensions,
                        "fingerprint": record.cursor.get("native_config_fingerprint"),
                    },
                )
                return transitioned is not None

    async def provision_document(self, record):
        try:
            control = self.datasources.get("canon_admin")
        except KeyError:
            return False
        async with infrastructure_unit(control) as session:
            function = await session.scalar(
                text("SELECT to_regprocedure('public.koinon_provision_document_index(text,text,text)')::oid")
            )
            if not function or not await session.scalar(
                text("SELECT has_function_privilege(current_user,CAST(:function AS oid),'EXECUTE')"),
                {"function": function},
            ):
                return False
            params = {
                "tenant": record.tenant_id,
                "workspace": record.native_workspace_id,
                "set_id": record.native_id,
                "index_id": record.id,
                "dimensions": record.dimensions,
                "fingerprint": record.embedding_fingerprint,
                "actor": record.updated_by,
                "provider": record.provider_kind,
                "model": record.model_id,
                "native_fingerprint": record.cursor.get("native_config_fingerprint"),
            }
            await session.execute(
                text(
                    "SELECT set_config('app.tenant_id',:tenant,true),set_config('app.workspace_id"
                    "',:workspace,true)"
                ),
                params,
            )
            await session.execute(text("SET LOCAL lock_timeout='3s'"))
            await session.execute(text("SET LOCAL statement_timeout='30s'"))
            await session.execute(
                text("""
                INSERT INTO public.canon_index_provisions
                  (set_id,tenant_id,workspace_id,index_id,dimensions,embedding_fingerprint,provider,model,native_fingerprint,actor)
                VALUES(:set_id,:tenant,:workspace,:index_id,:dimensions,:fingerprint,:provider,:model,:native_fingerprint,:actor)
                ON CONFLICT(set_id) DO NOTHING
            """),
                params,
            )
            approved = (
                (
                    await session.execute(
                        text("""
                SELECT index_id,dimensions,embedding_fingerprint FROM public.canon_index_provisions
                WHERE set_id=:set_id AND tenant_id=:tenant AND workspace_id=:workspace
            """),
                        params,
                    )
                )
                .mappings()
                .one_or_none()
            )
            if approved is None or (
                approved["index_id"],
                approved["dimensions"],
                approved["embedding_fingerprint"],
            ) != (record.id, record.dimensions, record.embedding_fingerprint):
                raise ValueError("The native provisioning registration does not match this immutable target")
            await session.scalar(
                text("SELECT public.koinon_provision_document_index(:tenant,:workspace,:set_id)"), params
            )
            return True

    async def set_state(self, record, status):
        if status not in {"queued", "building", "awaiting_index", "ready", "failed", "cancelled"}:
            raise ValueError("Only lifecycle build states may be projected to a native target")
        table = "canon_embedding_sets" if record.domain == "documents" else "flyquery_embedding_sets"
        async with infrastructure_unit(self.source(record.domain)) as session:
            await session.execute(
                text(
                    "UPDATE "
                    + table
                    + " SET status=:status "
                    + (",ready_at=now() " if status == "ready" else "")
                    + "WHERE id=:id AND tenant_id=:tenant AND workspace_id=:workspace AND status<>'active'"
                ),
                {
                    "status": status,
                    "id": record.native_id,
                    "tenant": record.tenant_id,
                    "workspace": record.native_workspace_id
                    if record.domain == "documents"
                    else UUID(record.native_workspace_id),
                },
            )

    async def coverage(self, record):
        async with infrastructure_unit(self.source(record.domain)):
            if record.domain == "documents":
                from flycanon.models.repositories import ChunkRepository

                counts = await self.domains._resolve(ChunkRepository).coverage_counts(
                    tenant_id=record.tenant_id,
                    workspace_id=record.native_workspace_id,
                    set_id=record.native_id,
                )
            else:
                from flyquery.models.repositories.embedding_set_repository import EmbeddingSetRepository

                counts = await EmbeddingSetRepository(self.source(record.domain).sessionmaker).counts(
                    tenant_id=record.tenant_id,
                    workspace_id=record.native_workspace_id,
                    set_id=record.native_id,
                )
            return {**counts, "complete": counts["chunk_count"] == counts["vector_count"]}

    async def step(self, record, *, embedder, validate_write):
        domain = record.domain
        with native_scope(
            "canon" if domain == "documents" else "structured",
            record.tenant_id,
            record.native_workspace_id,
            record.updated_by,
        ):
            if domain == "documents":
                from flycanon.core.services.retrieval.corpus_factory import CorpusContext

                corpus = self.domains._resolve(CorpusContext)
                if corpus.backend != "pgvector":
                    raise ServiceUnavailableException(
                        "Versioned document index management requires the native pgvector backend",
                        code="KNOWLEDGE_INDEX_BACKEND_UNSUPPORTED",
                    )
                await corpus.initialise()
            async with infrastructure_unit(self.source(domain)) as session:
                await self.set_state(record, "building")
                if domain == "documents":
                    from flycanon.config import CanonSettings
                    from flycanon.core.services.embeddings.embedding_service import EmbeddingRegistry
                    from flycanon.core.services.embeddings.embedding_sets import (
                        EmbeddingSetBinding,
                        EmbeddingSetService,
                    )
                    from flycanon.core.services.embeddings.reindex_service import ReindexService
                    from flycanon.core.services.retrieval.corpus_factory import CorpusContext
                    from flycanon.models.repositories import ChunkRepository, IngestJobRepository

                    domains = self.domains
                    corpus = domains._resolve(CorpusContext)
                    chunks = domains._resolve(ChunkRepository)
                    binding = EmbeddingSetBinding(
                        record.native_id, record.provider_kind, record.model_id, record.dimensions
                    )
                    service = ReindexService(
                        chunks=chunks,
                        jobs=domains._resolve(IngestJobRepository),
                        sets=domains._resolve(EmbeddingSetService),
                        registry=domains._resolve(EmbeddingRegistry),
                        vector_store=corpus.vector_store,
                        dense_backend=corpus.dense_backend,
                        settings=domains._resolve(CanonSettings),
                    )
                    result = await service.step(
                        tenant_id=record.tenant_id,
                        workspace_id=record.native_workspace_id,
                        binding=binding,
                        batch_size=record.batch_size,
                        validate_write=validate_write,
                    )
                    result.update(
                        await chunks.coverage_counts(
                            tenant_id=record.tenant_id,
                            workspace_id=record.native_workspace_id,
                            set_id=record.native_id,
                        )
                    )
                    indexed = False
                else:
                    from flyquery.core.services.retrieval.versioned_index import VersionedIndexService
                    from flyquery.models.repositories.embedding_set_repository import EmbeddingSetRepository

                    repository = EmbeddingSetRepository(self.source(domain).sessionmaker)
                    result = await VersionedIndexService(repository).step(
                        tenant_id=record.tenant_id,
                        workspace_id=record.native_workspace_id,
                        set_id=record.native_id,
                        embedder=embedder,
                        dimensions=record.dimensions,
                        model=record.model_id,
                        batch_size=record.batch_size,
                        validate_write=validate_write,
                    )
                    indexed = await ann_qualified(
                        session, domain=domain, set_id=record.native_id, dimensions=record.dimensions
                    )
            if result["complete"]:
                await validate_write()
                # Commit the native batch before owner-side DDL takes its table lock.
                if domain == "documents":
                    indexed = await self.provision_document(record)
                async with infrastructure_unit(self.source(domain)):
                    result.update(await self.coverage(record))
                    await self.set_state(
                        record,
                        "ready"
                        if result["complete"] and indexed
                        else "awaiting_index"
                        if result["complete"]
                        else "building",
                    )
            return {**result, "indexed": indexed}

    async def get_native(
        self, *, tenant_id, native_workspace_id, catalog_workspace_id, domain, actor, identifier
    ):
        if domain not in {"documents", "structured"}:
            raise ValueError("Select one knowledge domain")
        native = "canon" if domain == "documents" else "structured"
        native_id = (
            "legacy-inline"
            if domain == "structured"
            and identifier == index_id(tenant_id, catalog_workspace_id, domain, "legacy-inline")
            else None
        )
        if native_id is None:
            with native_scope(native, tenant_id, native_workspace_id, actor):
                async with infrastructure_unit(self.source(domain)) as session:
                    table = "canon_embedding_sets" if domain == "documents" else "flyquery_embedding_sets"
                    if not await session.scalar(
                        text("SELECT to_regclass(:table)"), {"table": "public." + table}
                    ):
                        return None
                    native_id = await session.scalar(
                        text(
                            "SELECT id FROM "
                            + table
                            + " WHERE tenant_id=:tenant AND workspace_id=:workspace "
                            "AND encode(sha256(convert_to(:tenant||chr(31)||:canonical||chr(31)||"
                            ":domain||chr(31)||id,'UTF8')),'hex')=:identifier LIMIT 1"
                        ),
                        {
                            "tenant": tenant_id,
                            "workspace": native_workspace_id
                            if native == "canon"
                            else UUID(native_workspace_id),
                            "canonical": catalog_workspace_id,
                            "domain": domain,
                            "identifier": identifier,
                        },
                    )
        if native_id is None:
            return None
        page = await self.discover(
            tenant_id=tenant_id,
            native_workspace_id=native_workspace_id,
            catalog_workspace_id=catalog_workspace_id,
            domain=domain,
            actor=actor,
            limit=1,
            offset=0,
            native_id=native_id,
        )
        return page["items"][0] if page["items"] else None

    async def activate(self, record, *, previous_native_id, restore=False):
        from pyfly.kernel import ConflictException

        from koinon.knowledge.indexes.locks import lock_key

        native = "canon" if record.domain == "documents" else "structured"
        params = {
            "tenant": record.tenant_id,
            "workspace": record.native_workspace_id
            if native == "canon"
            else UUID(record.native_workspace_id),
            "id": record.native_id,
        }
        with native_scope(native, record.tenant_id, record.native_workspace_id, record.updated_by):
            async with infrastructure_unit(self.source(record.domain)) as session:
                await session.execute(
                    text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"),
                    {"key": lock_key(native, record.tenant_id, record.native_workspace_id)},
                )
                current = (
                    await self.overview(
                        tenant_id=record.tenant_id,
                        workspace_id=record.native_workspace_id,
                        domain=record.domain,
                        actor=record.updated_by,
                    )
                )["active_native_id"]
                if current not in {previous_native_id, record.native_id}:
                    raise ConflictException("The native serving index changed", code="INDEX_ACTIVE_CONFLICT")
                if restore:
                    if native == "canon":
                        from flycanon.core.services.embeddings.embedding_sets import EmbeddingSetService
                        from flycanon.models.repositories.embedding_set_repository import (
                            EmbeddingSetRepository,
                        )

                        domains = self.domains
                        if previous_native_id:
                            await domains._resolve(EmbeddingSetService).activate(
                                tenant_id=record.tenant_id,
                                workspace_id=record.native_workspace_id,
                                set_id=previous_native_id,
                            )
                        else:
                            await domains._resolve(EmbeddingSetRepository).point_workspace_at(
                                tenant_id=record.tenant_id,
                                workspace_id=record.native_workspace_id,
                                set_id=None,
                            )
                            await domains._resolve(EmbeddingSetRepository).set_status(
                                tenant_id=record.tenant_id,
                                workspace_id=record.native_workspace_id,
                                set_id=record.native_id,
                                status="ready",
                            )
                    else:
                        await session.execute(
                            text(
                                "UPDATE flyquery_embedding_sets SET status='retired',retired_at=n"
                                "ow() WHERE tenant_id=:tenant AND workspace_id=:workspace AND sta"
                                "tus='active'"
                            ),
                            params,
                        )
                        if previous_native_id:
                            await session.execute(
                                text(
                                    "UPDATE flyquery_embedding_sets SET status='active',activated"
                                    "_at=now() WHERE id=:previous AND tenant_id=:tenant AND works"
                                    "pace_id=:workspace"
                                ),
                                {**params, "previous": previous_native_id},
                            )
                    return
                table = "canon_embedding_sets" if native == "canon" else "flyquery_embedding_sets"
                target = (
                    (
                        await session.execute(
                            text(
                                "SELECT provider,model,dimensions,status FROM "
                                + table
                                + " WHERE id=:id AND tenant_id=:tenant AND workspace_id=:workspace"
                            ),
                            params,
                        )
                    )
                    .mappings()
                    .one_or_none()
                )
                if (
                    target is None
                    or (target["provider"], target["model"], target["dimensions"])
                    != (record.provider_kind, record.model_id, record.dimensions)
                    or target["status"] not in {"ready", "active", "retired"}
                ):
                    raise ConflictException(
                        "The native target is not a qualified compatible set", code="INDEX_STATE_CONFLICT"
                    )
                coverage = await self.coverage(record)
                if not coverage["complete"]:
                    raise ConflictException(
                        "Source content changed; resume this ready target before activation",
                        code="INDEX_COVERAGE_STALE",
                    )
                indexed = await ann_qualified(
                    session, domain=record.domain, set_id=record.native_id, dimensions=record.dimensions
                )
                if not indexed:
                    raise ConflictException(
                        "The target ANN index requires qualification", code="INDEX_NOT_INDEXED"
                    )
                if native == "canon":
                    from flycanon.core.services.embeddings.embedding_sets import EmbeddingSetService

                    await self.domains._resolve(EmbeddingSetService).activate(
                        tenant_id=record.tenant_id,
                        workspace_id=record.native_workspace_id,
                        set_id=record.native_id,
                    )
                else:
                    await session.execute(
                        text(
                            "UPDATE flyquery_embedding_sets SET status='retired',retired_at=now()"
                            " WHERE tenant_id=:tenant AND workspace_id=:workspace AND status='act"
                            "ive' AND id<>:id"
                        ),
                        params,
                    )
                    await session.execute(
                        text(
                            "UPDATE flyquery_embedding_sets SET status='active',activated_at=now("
                            ") WHERE id=:id AND tenant_id=:tenant AND workspace_id=:workspace"
                        ),
                        params,
                    )

    async def project_state(self, record, status):
        with native_scope(
            "canon" if record.domain == "documents" else "structured",
            record.tenant_id,
            record.native_workspace_id,
            record.updated_by,
        ):
            await self.set_state(record, status)
