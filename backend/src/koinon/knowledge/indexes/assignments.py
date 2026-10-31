# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Only qualified lifecycle activation may change an existing embedding space."""

from hashlib import sha256
from json import dumps

from pyfly.container import service
from pyfly.data.relational.sqlalchemy import LockMode, transactional
from pyfly.kernel import ConflictException

from koinon.knowledge.connections.entities import KnowledgeConnection, timestamp
from koinon.knowledge.connections.service import KnowledgeConnectionService


@service(name="knowledge.index_assignments")
class IndexAssignments:
    def __init__(self, connections: KnowledgeConnectionService):
        self.connections = connections

    async def snapshot(self, subject, tenant_id, workspace_ids, domain):
        result = {}
        for workspace_id in sorted(workspace_ids):
            await self.connections.authority(subject, tenant_id, workspace_id)
            row = await self.connections.selected(tenant_id, workspace_id, domain, domain + ".embedding")
            if row is not None:
                row = await self.connections.scoped(tenant_id, row.id, lock=True)
            result[workspace_id] = (
                None
                if row is None
                else {
                    key: getattr(row, key)
                    for key in (
                        "id",
                        "revision",
                        "workspace_id",
                        "mode",
                        "provider_id",
                        "model_id",
                        "dimensions",
                        "storage_dimensions",
                        "space_id",
                        "embedding_fingerprint",
                        "enabled",
                    )
                }
            )
        return result

    @transactional
    async def bind(self, subject, row, expected):
        await self.connections.connections.lock_tenant(row.tenant_id)
        current = await self.snapshot(subject, row.tenant_id, expected, row.domain)
        if current != expected:
            raise ConflictException(
                "An embedding assignment changed during activation; review recovery",
                code="INDEX_CONNECTION_CONFLICT",
            )
        for workspace_id in sorted(expected):
            role = row.domain + ".embedding"
            found = await self.connections.connections.find_all(
                tenant_id=row.tenant_id, workspace_id=workspace_id, domain=row.domain, role=role
            )
            previous = (
                await self.connections.connections.find_by_id(found[0].id, lock=LockMode.PESSIMISTIC_WRITE)
                if found
                else None
            )
            value = previous or KnowledgeConnection(
                id=sha256(dumps((row.tenant_id, workspace_id, row.domain, role)).encode()).hexdigest(),
                tenant_id=row.tenant_id,
                workspace_id=workspace_id,
                scope_key=workspace_id,
                domain=row.domain,
                role=role,
                created_by=subject,
                updated_by=subject,
            )
            value.mode, value.provider_id, value.model_id = "provider", row.provider_id, row.model_id
            value.model_options, value.enabled = {}, True
            value.dimensions, value.storage_dimensions = row.dimensions, row.storage_dimensions
            value.space_id, value.embedding_fingerprint = row.native_id, row.embedding_fingerprint
            value.revision = previous.revision + 1 if previous else 1
            value.updated_by, value.updated_at = subject, timestamp()
            await self.connections.connections.save(value)
            await self.connections.catalog._audit(
                subject,
                row.tenant_id,
                "knowledge.connection.saved",
                value.id,
                {
                    "role": role,
                    "revision": value.revision,
                    "space_id": value.space_id,
                    "embedding_fingerprint": value.embedding_fingerprint,
                    "index_id": row.id,
                },
            )
