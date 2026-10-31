# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Fixed generation lookup and stored-query back references on the native primary store."""

from pyfly.container import repository
from pyfly.data.relational.sqlalchemy import Repository, transactional
from pyfly.data.transaction import Propagation
from sqlalchemy import Text, case, cast, exists, func, or_, select

from koinon.assistants.entities import ChatRun, ChatThread, ToolResult
from koinon.assistants.memory.entities import ChatMemoryManifest
from koinon.assistants.memory.projections import MemoryCurrentResult
from koinon.assistants.memory.repositories import authority_bytes, payload_bytes
from koinon.catalog.errors import AccessDenied

MAX_EGRESS_BYTES = 32 * 1024 * 1024


@repository(name="assistants.memory_egress_repository")
class MemoryEgressRepository(Repository[ChatMemoryManifest, str]):
    @transactional(
        datasource="primary", propagation=Propagation.REQUIRES_NEW, read_only=True, read_from_primary=True
    )
    async def result_ids(self, run_ids):
        rows = tuple(
            (
                await self._require_session().execute(
                    select(
                        ToolResult.id,
                        ToolResult.run_id,
                        ToolResult.kind,
                        ToolResult.payload["generation_id"].as_string(),
                    )
                    .where(ToolResult.run_id.in_(run_ids))
                    .limit(2001)
                )
            ).all()
        )
        if len(rows) > 2000:
            raise AccessDenied("Select fewer conversation results", code="MEMORY_SCOPE_TOO_WIDE")
        return rows

    @transactional(
        datasource="primary", propagation=Propagation.REQUIRES_NEW, read_only=True, read_from_primary=True
    )
    async def manifests(self, generation_ids):
        session = self._require_session()
        size = (
            select(
                func.coalesce(
                    func.sum(
                        authority_bytes(session.get_bind().dialect.name, ChatMemoryManifest.manifest_json)
                    ),
                    0,
                )
            )
            .where(ChatMemoryManifest.generation_id.in_(generation_ids))
            .scalar_subquery()
        )
        columns = tuple(
            case((size <= MAX_EGRESS_BYTES, column), else_=None).label(column.name)
            if column.name == "manifest_json"
            else column
            for column in ChatMemoryManifest.__table__.columns
        )
        rows = tuple(
            (
                await session.execute(
                    select(*columns).where(ChatMemoryManifest.generation_id.in_(generation_ids)).limit(201)
                )
            )
            .mappings()
            .all()
        )
        if len(rows) > 200 or any(row["manifest_json"] is None for row in rows):
            raise AccessDenied("Select fewer conversation generations", code="MEMORY_SCOPE_TOO_WIDE")
        return tuple(ChatMemoryManifest(**dict(row)) for row in rows)

    @transactional(
        datasource="primary", propagation=Propagation.REQUIRES_NEW, read_only=True, read_from_primary=True
    )
    async def unbound_memory(self, subject, tenant_id, thread_id, message_ids):
        return bool(
            await self._require_session().scalar(
                select(
                    exists(
                        select(ChatMemoryManifest.id)
                        .join(ChatRun, ChatRun.id == ChatMemoryManifest.run_id)
                        .join(ChatThread, ChatThread.id == ChatRun.thread_id)
                        .where(
                            ChatThread.id == thread_id,
                            ChatThread.subject == subject,
                            ChatThread.tenant_id == tenant_id,
                            ChatRun.message_id.in_(message_ids),
                        )
                    )
                )
            )
        )

    @transactional(
        datasource="primary", propagation=Propagation.REQUIRES_NEW, read_only=True, read_from_primary=True
    )
    async def query_results(self, tenant_id, query_id):
        # Native query UUIDs also occur in observed source manifests when a tool fails
        # after execution. Include observations and historical generations.
        matches = (
            select(ToolResult.id)
            .join(ChatRun, ChatRun.id == ToolResult.run_id)
            .where(
                ChatRun.tenant_id == tenant_id,
                or_(
                    ToolResult.payload["data"]["query_id"].as_string() == query_id,
                    cast(ToolResult.payload, Text).contains(query_id, autoescape=True),
                ),
            )
        )
        size = (
            select(func.coalesce(func.sum(payload_bytes(self._require_session().get_bind().dialect.name)), 0))
            .where(ToolResult.id.in_(matches))
            .scalar_subquery()
        )
        rows = tuple(
            (
                await self._require_session().execute(
                    select(
                        ToolResult.id,
                        ToolResult.run_id,
                        ToolResult.kind,
                        ToolResult.created_at,
                        case((size <= MAX_EGRESS_BYTES, ToolResult.payload), else_=None),
                        ChatThread.subject,
                    )
                    .join(ChatRun, ChatRun.id == ToolResult.run_id)
                    .join(ChatThread, ChatThread.id == ChatRun.thread_id)
                    .where(
                        ChatRun.tenant_id == tenant_id,
                        or_(
                            ToolResult.payload["data"]["query_id"].as_string() == query_id,
                            cast(ToolResult.payload, Text).contains(query_id, autoescape=True),
                        ),
                    )
                    .limit(201)
                )
            ).all()
        )
        if len(rows) > 200 or any(row[4] is None for row in rows):
            raise AccessDenied("This result has too many conversation origins", code="MEMORY_SCOPE_TOO_WIDE")
        return tuple((MemoryCurrentResult(row[0], row[1], row[2], row[4], row[3]), row[5]) for row in rows)

    @transactional(
        datasource="primary", propagation=Propagation.REQUIRES_NEW, read_only=True, read_from_primary=True
    )
    async def fixed(self, subject, tenant_id, run_ids, result_ids):
        headers = tuple(
            (
                await self._require_session().execute(
                    select(ChatRun, ChatThread)
                    .join(ChatThread, ChatThread.id == ChatRun.thread_id)
                    .where(
                        ChatRun.id.in_(run_ids),
                        ChatRun.tenant_id == tenant_id,
                        ChatThread.tenant_id == tenant_id,
                        ChatThread.subject == subject,
                        ChatThread.deleted_at.is_(None),
                    )
                    .limit(201)
                )
            ).all()
        )
        size = (
            select(func.coalesce(func.sum(payload_bytes(self._require_session().get_bind().dialect.name)), 0))
            .where(ToolResult.id.in_(result_ids))
            .scalar_subquery()
        )
        results = tuple(
            (
                await self._require_session().scalars(
                    select(ToolResult)
                    .where(ToolResult.id.in_(result_ids), size <= MAX_EGRESS_BYTES)
                    .limit(2001)
                )
            ).all()
        )
        return headers, results
