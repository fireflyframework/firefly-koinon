# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Durable index intent and revision guards; queued work is never reported ready."""

from hashlib import sha256
from json import dumps

from pydantic import ValidationError
from pyfly.container import service
from pyfly.data.relational.sqlalchemy import LockMode, transactional
from pyfly.kernel import ConflictException, DuplicateKeyException, InvalidRequestException
from pyfly.security.context_holder import SecurityContextHolder

from koinon.catalog.errors import AccessDenied
from koinon.jobs.service import JobService
from koinon.knowledge.connections.service import embedding_fingerprint
from koinon.knowledge.indexes.adapters import index_id
from koinon.knowledge.indexes.dtos import IndexCreateInput, IndexPlanInput
from koinon.knowledge.indexes.entities import KnowledgeIndex, timestamp
from koinon.knowledge.indexes.mappers import index_dto
from koinon.knowledge.indexes.repositories import KnowledgeIndexRepository
from koinon.knowledge.indexes.service import KnowledgeIndexService


@service(name="knowledge.index_lifecycle")
class IndexLifecycleService:
    def __init__(self, reader: KnowledgeIndexService, records: KnowledgeIndexRepository, jobs: JobService):
        self.reader, self.records, self.jobs = reader, records, jobs

    @transactional
    async def create(self, subject, tenant_id, values, idempotency_key):
        try:
            data = IndexCreateInput.model_validate(values)
        except ValidationError as error:
            raise InvalidRequestException(
                "Provide valid index creation fields", code="INVALID_INDEX_PLAN"
            ) from error
        workspace = await self.reader.authority(subject, tenant_id, data.workspace_id, write=True)
        await self.reader.connections.authority(subject, tenant_id, workspace.id)
        fields = data.model_dump()
        digest = sha256(
            dumps([tenant_id, data.workspace_id, data.domain, idempotency_key]).encode()
        ).hexdigest()
        native_id = ("es-" if data.domain == "documents" else "fs-") + digest[:32]
        identifier = index_id(tenant_id, data.workspace_id, data.domain, native_id)
        job = await self.jobs.submit(
            tenant_id,
            data.workspace_id,
            "knowledge.index",
            {"index_id": identifier, "subject": subject, "request": fields},
            idempotency_key,
        )
        existing = await self.records.find_all(id=identifier, tenant_id=tenant_id)
        if existing:
            await self.reader.native_binding(subject, tenant_id, workspace, data.domain, write=True)
            return {"index": index_dto(existing[0]), "job_id": job.id}
        plan = await self.reader.plan(
            subject, tenant_id, {key: fields[key] for key in IndexPlanInput.model_fields}
        )
        if (data.expected_active_id, data.expected_connection_revision) != (
            plan["active_index_id"],
            plan["expected_connection_revision"],
        ):
            raise ConflictException(
                "Reload active index and embedding assignment", code="INDEX_REVISION_CONFLICT"
            )
        binding = await self.reader.native_binding(
            subject, tenant_id, workspace, data.domain, write=True, create=True
        )
        provider = await self.reader.planner.provider(tenant_id, data.provider_id, data.model_id)
        context = SecurityContextHolder.get_context()
        slot = sha256(dumps([tenant_id, data.domain, binding.native_workspace_id]).encode()).hexdigest()
        row = KnowledgeIndex(
            id=identifier,
            tenant_id=tenant_id,
            workspace_id=data.workspace_id,
            native_workspace_id=binding.native_workspace_id,
            native_id=native_id,
            domain=data.domain,
            provider_id=provider.id,
            provider_kind=provider.kind,
            provider_revision=provider.revision,
            model_id=data.model_id,
            dimensions=plan["dimensions"],
            storage_dimensions=plan["storage_dimensions"],
            embedding_fingerprint=embedding_fingerprint(
                provider, data.model_id, plan["dimensions"], plan["storage_dimensions"]
            ),
            build_slot=slot,
            job_id=job.id,
            created_by=subject,
            updated_by=subject,
            access_token_id=context.attributes.get("koinon_token_id") if context else None,
            batch_size=data.batch_size,
            chunk_count=plan["chunk_count"],
            status="queued",
        )
        try:
            row = await self.records.save(row)
        except DuplicateKeyException as error:
            raise ConflictException(
                "A rebuild already owns this native workspace", code="INDEX_BUILD_CONFLICT"
            ) from error
        fingerprint = await self.reader.adapter.create(row, actor=subject, endpoint=provider.base_url)
        row.cursor = {"native_config_fingerprint": fingerprint}
        await self.records.save(row)
        await self.reader.facade.catalog._audit(
            subject, tenant_id, "knowledge.index.queued", row.id, {"job_id": job.id}
        )
        return {"index": index_dto(row), "job_id": job.id}

    async def scoped(self, subject, tenant_id, identifier, *, write=False, lock=False):
        rows = await self.records.find_all(id=identifier, tenant_id=tenant_id)
        if not rows:
            raise AccessDenied("Index is unavailable in this organization", code="ACCESS_DENIED")
        row = await self.records.find_by_id(identifier, lock=LockMode.PESSIMISTIC_WRITE) if lock else rows[0]
        if row is None or row.tenant_id != tenant_id:
            raise AccessDenied("Index is unavailable", code="ACCESS_DENIED")
        workspace = await self.reader.authority(subject, tenant_id, row.workspace_id, write=write)
        await self.reader.native_binding(subject, tenant_id, workspace, row.domain, write=write)
        return row

    async def get(self, subject, tenant_id, identifier):
        row = await self.scoped(subject, tenant_id, identifier)
        try:
            await self.reader.connections.authority(subject, tenant_id, row.workspace_id)
            management = True
        except AccessDenied:
            management = False
        value = index_dto(row, management=management)
        actual = await self.reader.adapter.get_native(
            tenant_id=tenant_id,
            native_workspace_id=row.native_workspace_id,
            catalog_workspace_id=row.workspace_id,
            domain=row.domain,
            actor=subject,
            identifier=row.id,
        )
        if actual:
            value["native_status"] = actual["status"]
            for key in ("chunk_count", "vector_count", "indexed", "qualification"):
                value[key] = actual[key]
            value["active"] = row.status == "active" and actual["active"]
        else:
            value["qualification"], value["active"] = "native_target_unavailable", False
        return value

    @transactional
    async def cancel(self, subject, tenant_id, identifier, expected_revision):
        row = await self.scoped(subject, tenant_id, identifier, write=True)
        await self.jobs._locked(tenant_id, row.job_id)
        row = await self.records.find_by_id(identifier, lock=LockMode.PESSIMISTIC_WRITE)
        if row.revision != expected_revision:
            raise ConflictException("Reload the index revision", code="INDEX_REVISION_CONFLICT")
        if row.status not in {"queued", "building", "awaiting_index"}:
            raise ConflictException("This index is not cancellable", code="INDEX_STATE_CONFLICT")
        await self.jobs.cancel(tenant_id, row.job_id)
        row.status, row.build_slot = "cancelled", None
        row.revision += 1
        row.updated_by, row.updated_at = subject, timestamp()
        await self.records.save(row)
        await self.reader.adapter.project_state(row, "cancelled")
        await self.reader.facade.catalog._audit(subject, tenant_id, "knowledge.index.cancelled", row.id)
        return index_dto(row)

    @transactional
    async def resume(self, subject, tenant_id, identifier, expected_revision, idempotency_key):
        row = await self.scoped(subject, tenant_id, identifier, write=True, lock=True)
        payload = {"index_id": row.id, "subject": subject, "resume_revision": expected_revision}
        previous = await self.jobs.repository.find_all(tenant_id=tenant_id, idempotency_key=idempotency_key)
        if previous:
            replay = await self.jobs.submit(
                tenant_id, row.workspace_id, "knowledge.index", payload, idempotency_key
            )
            if replay.id != row.job_id:
                raise ConflictException("A later request superseded this job", code="INDEX_REVISION_CONFLICT")
            return {"index": index_dto(row), "job_id": replay.id}
        if type(expected_revision) is not int or row.revision != expected_revision:
            raise ConflictException("Reload the index revision", code="INDEX_REVISION_CONFLICT")
        if row.status not in {"failed", "cancelled", "ready", "retired"}:
            raise ConflictException("Resume only a nonactive unfinished target", code="INDEX_STATE_CONFLICT")
        provider = await self.reader.planner.provider(tenant_id, row.provider_id, row.model_id)
        if row.embedding_fingerprint != embedding_fingerprint(
            provider, row.model_id, row.dimensions, row.storage_dimensions
        ):
            raise ConflictException(
                "The embedding connection changed; build a reviewed new version",
                code="KNOWLEDGE_EMBEDDING_REINDEX_REQUIRED",
            )
        overview = await self.reader.adapter.overview(
            tenant_id=tenant_id, workspace_id=row.native_workspace_id, domain=row.domain, actor=subject
        )
        if overview["active_native_id"] == row.native_id:
            raise ConflictException(
                "An active version must be rebuilt into a separate target", code="INDEX_STATE_CONFLICT"
            )
        job = await self.jobs.submit(
            tenant_id,
            row.workspace_id,
            "knowledge.index",
            payload,
            idempotency_key,
        )
        row.job_id, row.status = job.id, "queued"
        row.provider_revision = provider.revision
        row.build_slot = sha256(dumps([tenant_id, row.domain, row.native_workspace_id]).encode()).hexdigest()
        row.revision += 1
        row.updated_by, row.updated_at = subject, timestamp()
        context = SecurityContextHolder.get_context()
        row.access_token_id = context.attributes.get("koinon_token_id") if context else None
        row.error_code, row.error = None, None
        try:
            await self.records.save(row)
        except DuplicateKeyException as error:
            raise ConflictException(
                "Another rebuild owns this workspace", code="INDEX_BUILD_CONFLICT"
            ) from error
        await self.reader.adapter.project_state(row, "queued")
        await self.reader.facade.catalog._audit(
            subject, tenant_id, "knowledge.index.resumed", row.id, {"job_id": job.id}
        )
        return {"index": index_dto(row), "job_id": job.id}
