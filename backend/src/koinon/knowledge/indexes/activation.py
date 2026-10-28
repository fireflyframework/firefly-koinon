# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Recoverable native-pointer and role-assignment switching across named sources."""

from hashlib import sha256
from json import dumps

from pydantic import ValidationError
from pyfly.container import service
from pyfly.data.relational.sqlalchemy import transactional
from pyfly.kernel import ConflictException, DuplicateKeyException, InvalidRequestException

from koinon.knowledge.connections.service import embedding_fingerprint
from koinon.knowledge.indexes.adapters import index_id
from koinon.knowledge.indexes.assignments import IndexAssignments
from koinon.knowledge.indexes.dtos import IndexActivateInput
from koinon.knowledge.indexes.entities import timestamp
from koinon.knowledge.indexes.lifecycle import IndexLifecycleService
from koinon.knowledge.indexes.mappers import index_dto


@service(name="knowledge.index_activation")
class IndexActivation:
    def __init__(self, lifecycle: IndexLifecycleService, assignments: IndexAssignments):
        self.lifecycle, self.assignments = lifecycle, assignments

    async def activate(self, subject, tenant_id, identifier, values):
        try:
            request = IndexActivateInput.model_validate(values).model_dump()
        except ValidationError as error:
            raise InvalidRequestException(
                "Provide valid activation revisions and recovery action", code="INVALID_INDEX_ACTIVATION"
            ) from error
        row = await self.begin(subject, tenant_id, identifier, request)
        if row.status == "active":
            return index_dto(row)
        if request["recovery"] == "restore_previous":
            await self.switch(subject, tenant_id, identifier, request, restore=True)
            return await self.restored(subject, tenant_id, identifier, request)
        try:
            await self.switch(subject, tenant_id, identifier, request)
        except ConflictException as error:
            if error.code in {"INDEX_ACTIVE_CONFLICT", "INDEX_COVERAGE_STALE", "INDEX_NOT_INDEXED"}:
                await self.abort_before_switch(subject, tenant_id, identifier, request)
            raise
        return await self.finish(subject, tenant_id, identifier, request)

    async def aliases(self, row):
        values = await self.lifecycle.reader.facade.bindings.find_all(
            tenant_id=row.tenant_id,
            domain="canon" if row.domain == "documents" else "structured",
            entity_kind="workspace",
            native_id=row.native_workspace_id,
        )
        return sorted({row.workspace_id, *(value.catalog_id for value in values)})

    async def provider(self, row):
        provider = await self.lifecycle.reader.planner.provider(row.tenant_id, row.provider_id, row.model_id)
        if (
            embedding_fingerprint(provider, row.model_id, row.dimensions, row.storage_dimensions)
            != row.embedding_fingerprint
        ):
            raise ConflictException(
                "The embedding endpoint/model changed; build a reviewed replacement",
                code="KNOWLEDGE_EMBEDDING_REINDEX_REQUIRED",
            )
        return provider

    @transactional
    async def begin(self, subject, tenant_id, identifier, request):
        row = await self.lifecycle.scoped(subject, tenant_id, identifier, write=True, lock=True)
        if row.status == "active" and row.transition.get("request") == request:
            return row
        if row.revision != request["expected_revision"]:
            raise ConflictException("Reload the current index revision", code="INDEX_REVISION_CONFLICT")
        recovering = row.status == "activating" and request["recovery"] is not None
        if row.status not in {"ready", "retired"} and not recovering:
            raise ConflictException(
                "Activate a qualified ready/retired version or explicitly recover its transition",
                code="INDEX_STATE_CONFLICT",
            )
        if request["recovery"] is not None and not recovering:
            raise ConflictException(
                "Recovery applies only to an unfinished activation", code="INDEX_STATE_CONFLICT"
            )
        if request["recovery"] != "restore_previous":
            await self.provider(row)
        overview = await self.lifecycle.reader.adapter.overview(
            tenant_id=tenant_id, workspace_id=row.native_workspace_id, domain=row.domain, actor=subject
        )
        current = (
            index_id(tenant_id, row.workspace_id, row.domain, overview["active_native_id"])
            if overview["active_native_id"]
            else None
        )
        if current != request["expected_active_id"]:
            raise ConflictException(
                "The native active index changed; reload the plan", code="INDEX_ACTIVE_CONFLICT"
            )
        snapshot = await self.assignments.snapshot(subject, tenant_id, await self.aliases(row), row.domain)
        selected = snapshot[row.workspace_id]
        if (selected["revision"] if selected else None) != request["expected_connection_revision"]:
            raise ConflictException(
                "Reload the selected embedding assignment", code="INDEX_CONNECTION_CONFLICT"
            )
        previous = row.transition.get("previous_native_id") if recovering else overview["active_native_id"]
        previous_status = row.transition.get("target_previous_status", "ready") if recovering else row.status
        if not recovering:
            row.previous_binding = snapshot
        row.transition = {
            "request": request,
            "previous_native_id": previous,
            "roles": snapshot,
            "target_previous_status": previous_status,
        }
        row.status, row.updated_by, row.updated_at = "activating", subject, timestamp()
        row.build_slot = sha256(dumps([tenant_id, row.domain, row.native_workspace_id]).encode()).hexdigest()
        row.revision += 1
        try:
            await self.lifecycle.records.save(row)
        except DuplicateKeyException as error:
            raise ConflictException(
                "Another build or activation owns this workspace", code="INDEX_BUILD_CONFLICT"
            ) from error
        await self.lifecycle.reader.facade.catalog._audit(
            subject, tenant_id, "knowledge.index.activating", row.id
        )
        return row

    async def pending(self, subject, tenant_id, identifier, request, *, require_provider=True):
        row = await self.lifecycle.scoped(subject, tenant_id, identifier, write=True, lock=True)
        if row.status != "activating" or row.transition.get("request") != request or not row.build_slot:
            raise ConflictException(
                "This activation no longer owns the transition", code="INDEX_STATE_CONFLICT"
            )
        if require_provider:
            await self.provider(row)
        return row

    @transactional
    async def switch(self, subject, tenant_id, identifier, request, restore=False):
        row = await self.pending(subject, tenant_id, identifier, request, require_provider=not restore)
        await self.lifecycle.reader.adapter.activate(
            row, previous_native_id=row.transition["previous_native_id"], restore=restore
        )

    @transactional
    async def finish(self, subject, tenant_id, identifier, request):
        row = await self.pending(subject, tenant_id, identifier, request)
        overview = await self.lifecycle.reader.adapter.overview(
            tenant_id=tenant_id, workspace_id=row.native_workspace_id, domain=row.domain, actor=subject
        )
        if overview["active_native_id"] != row.native_id:
            raise ConflictException(
                "Native activation is incomplete; explicitly recover this transition",
                code="INDEX_ACTIVE_CONFLICT",
            )
        actual = await self.lifecycle.reader.adapter.get_native(
            tenant_id=tenant_id,
            native_workspace_id=row.native_workspace_id,
            catalog_workspace_id=row.workspace_id,
            domain=row.domain,
            actor=subject,
            identifier=row.id,
        )
        if not actual or not actual["indexed"] or actual["chunk_count"] != actual["vector_count"]:
            raise ConflictException(
                "Native activation coverage changed; explicitly recover this transition",
                code="INDEX_COVERAGE_STALE",
            )
        row.chunk_count, row.vector_count = actual["chunk_count"], actual["vector_count"]
        row.indexed, row.qualification = actual["indexed"], actual["qualification"]
        await self.assignments.bind(subject, row, row.transition["roles"])
        others = await self.lifecycle.records.find_all(
            tenant_id=tenant_id,
            domain=row.domain,
            native_workspace_id=row.native_workspace_id,
            status="active",
        )
        for old in others:
            if old.id != row.id:
                old.status, old.active_slot, old.retired_at = "retired", None, timestamp()
                old.revision += 1
                await self.lifecycle.records.save(old)
        row.status, row.active_slot, row.build_slot = "active", row.build_slot, None
        row.activated_at, row.updated_at = timestamp(), timestamp()
        row.revision += 1
        await self.lifecycle.records.save(row)
        await self.lifecycle.reader.facade.catalog._audit(
            subject, tenant_id, "knowledge.index.activated", row.id
        )
        return index_dto(row)

    @transactional
    async def restored(self, subject, tenant_id, identifier, request):
        row = await self.pending(subject, tenant_id, identifier, request, require_provider=False)
        actual = await self.lifecycle.reader.adapter.get_native(
            tenant_id=tenant_id,
            native_workspace_id=row.native_workspace_id,
            catalog_workspace_id=row.workspace_id,
            domain=row.domain,
            actor=subject,
            identifier=row.id,
        )
        row.status = actual["status"] if actual and actual["status"] in {"ready", "retired"} else "ready"
        row.build_slot = None
        if actual:
            row.chunk_count, row.vector_count, row.qualification = (
                actual["chunk_count"],
                actual["vector_count"],
                actual["qualification"],
            )
        row.error_code, row.error = None, None
        row.revision += 1
        await self.lifecycle.records.save(row)
        await self.lifecycle.reader.facade.catalog._audit(
            subject, tenant_id, "knowledge.index.restored_previous", row.id
        )
        return index_dto(row)

    @transactional
    async def abort_before_switch(self, subject, tenant_id, identifier, request):
        row = await self.pending(subject, tenant_id, identifier, request)
        overview = await self.lifecycle.reader.adapter.overview(
            tenant_id=tenant_id, workspace_id=row.native_workspace_id, domain=row.domain, actor=subject
        )
        if overview["active_native_id"] != row.native_id:
            previous = row.transition.get("target_previous_status", "ready")
            row.status, row.build_slot = previous if previous in {"ready", "retired"} else "ready", None
            row.revision += 1
            await self.lifecycle.records.save(row)
