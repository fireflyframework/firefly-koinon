# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Bounded native primary reads for personal context and immutable manifests."""

from pyfly.container import repository
from pyfly.data.relational.sqlalchemy import Repository, transactional
from pyfly.data.transaction import Propagation
from sqlalchemy import LargeBinary, Text, and_, cast, exists, func, or_, select
from sqlalchemy.orm import aliased

from koinon.assistants.entities import ChatEvent, ChatMessage, ChatRun, ChatThread, ToolResult
from koinon.assistants.history.entities import ChatFolder
from koinon.assistants.memory.entities import ChatMemoryManifest
from koinon.assistants.memory.projections import MemoryCandidate as MemoryCandidate
from koinon.assistants.memory.projections import MemoryCurrentEvidence, MemoryCurrentResult
from koinon.catalog.errors import AccessDenied
from koinon.organization_chat.entities import OrganizationChatSetting

MAX_RESULT_BYTES = 3 * 1024 * 1024


def value_bytes(dialect: str, value):
    text = cast(value, Text)
    return func.octet_length(text) if dialect == "postgresql" else func.length(cast(text, LargeBinary))


def authority_bytes(dialect: str, value):
    text = cast(value, Text)
    quoted = cast(func.to_json(text), Text) if dialect == "postgresql" else func.json_quote(text)
    return value_bytes(dialect, quoted)


def payload_bytes(dialect: str):
    return authority_bytes(dialect, ToolResult.payload)


@repository(name="assistants.memory_manifests")
class ChatMemoryRepository(Repository[ChatMemoryManifest, str]):
    @transactional(
        datasource="primary", propagation=Propagation.REQUIRED, read_only=True, read_from_primary=True
    )
    async def result_context(self, subject, tenant_id, run_id, result_id):
        return (
            await self._require_session().execute(
                select(ChatRun.scope, ChatRun.access_token_id, ChatThread.id, ToolResult)
                .join(ChatThread, ChatThread.id == ChatRun.thread_id)
                .join(ToolResult, ToolResult.run_id == ChatRun.id)
                .where(
                    ChatRun.id == run_id,
                    ToolResult.id == result_id,
                    ChatRun.tenant_id == tenant_id,
                    ChatThread.tenant_id == tenant_id,
                    ChatThread.subject == subject,
                    ChatThread.deleted_at.is_(None),
                )
                .execution_options(populate_existing=True)
            )
        ).one_or_none()

    @transactional(
        datasource="primary", propagation=Propagation.REQUIRED, read_only=True, read_from_primary=True
    )
    async def current_evidence(self, subject: str, tenant_id: str, run_ids: tuple[str, ...]):
        session = self._require_session()
        headers = (
            await session.execute(
                select(ChatRun.id, ChatRun.thread_id, ChatRun.scope, ChatRun.access_token_id)
                .join(ChatThread, ChatThread.id == ChatRun.thread_id)
                .where(
                    ChatRun.id.in_(run_ids),
                    ChatRun.tenant_id == tenant_id,
                    ChatThread.tenant_id == tenant_id,
                    ChatThread.subject == subject,
                    ChatThread.deleted_at.is_(None),
                )
                .limit(52)
            )
        ).all()
        if {item[0] for item in headers} != set(run_ids):
            raise AccessDenied("Conversation is unavailable", code="MEMORY_UNAVAILABLE")
        rows = (
            await session.execute(
                select(
                    ToolResult.id,
                    ToolResult.run_id,
                    ToolResult.kind,
                    ToolResult.created_at,
                    ToolResult.payload["asset_ids"],
                    ToolResult.payload["origin_token_id"].as_string(),
                    ToolResult.payload["generation_id"].as_string(),
                    ToolResult.payload["generation"]["start_sequence"].as_integer(),
                )
                .where(ToolResult.run_id.in_(run_ids))
                .limit(1025)
            )
        ).all()
        if len(rows) > 1024:
            raise AccessDenied("Request a smaller conversation page", code="MEMORY_PAGE_TOO_WIDE")
        results = tuple(
            MemoryCurrentResult(
                item[0],
                item[1],
                item[2],
                {
                    "asset_ids": item[4] or [],
                    "origin_token_id": item[5],
                    "generation_id": item[6],
                    "generation": {"start_sequence": item[7]},
                },
                item[3],
            )
            for item in rows
        )
        output = []
        for run_id, thread_id, scope, token in headers:
            assets = set(scope.get("asset_ids", []))
            assets.update(
                scope[key] for key in ("workspace_id", "project_id", "collection_id") if scope.get(key)
            )
            own = tuple(item for item in results if item.run_id == run_id)
            assets.update(key for item in own for key in item.payload["asset_ids"])
            if len(assets) > 512:
                raise AccessDenied("Request a smaller conversation page", code="MEMORY_PAGE_TOO_WIDE")
            output.append(
                MemoryCurrentEvidence(
                    run_id, thread_id, subject, tenant_id, scope, token, own, tuple(sorted(assets))
                )
            )
        return tuple(output)

    @transactional(
        datasource="primary", propagation=Propagation.REQUIRED, read_only=True, read_from_primary=True
    )
    async def result_window(self, run_id: str):
        session = self._require_session()
        count, size = (
            await session.execute(
                select(
                    func.count(), func.coalesce(func.sum(payload_bytes(session.get_bind().dialect.name)), 0)
                ).where(ToolResult.run_id == run_id)
            )
        ).one()
        if count > 128 or size > MAX_RESULT_BYTES:
            return None
        count_query = select(func.count()).where(ToolResult.run_id == run_id).scalar_subquery()
        size_query = (
            select(func.coalesce(func.sum(payload_bytes(session.get_bind().dialect.name)), 0))
            .where(ToolResult.run_id == run_id)
            .scalar_subquery()
        )
        rows = tuple(
            (
                await session.scalars(
                    select(ToolResult)
                    .where(ToolResult.run_id == run_id, count_query <= 128, size_query <= MAX_RESULT_BYTES)
                    .limit(129)
                )
            ).all()
        )
        return rows if len(rows) == count else None

    @transactional(
        datasource="primary", propagation=Propagation.REQUIRED, read_only=True, read_from_primary=True
    )
    async def pins_fit(self, identifiers: tuple[str, ...], *, message_ids: tuple[str, ...] = ()) -> bool:
        if len(identifiers) > 1024 or len(message_ids) > 256:
            return False
        session = self._require_session()
        count, size = (
            await session.execute(
                select(
                    func.count(), func.coalesce(func.sum(payload_bytes(session.get_bind().dialect.name)), 0)
                ).where(ToolResult.id.in_(identifiers))
            )
        ).one()
        message_count, message_size = (
            await session.execute(
                select(
                    func.count(),
                    func.coalesce(
                        func.sum(authority_bytes(session.get_bind().dialect.name, ChatMessage.text)), 0
                    ),
                ).where(ChatMessage.id.in_(message_ids))
            )
        ).one()
        return (
            count == len(identifiers)
            and message_count == len(message_ids)
            and size + message_size <= MAX_RESULT_BYTES
        )

    def _candidates(self, subject: str, tenant_id: str):
        user, answer, old = aliased(ChatMessage), aliased(ChatMessage), aliased(ChatRun)
        private = exists(
            select(ToolResult.id)
            .join(old, old.id == ToolResult.run_id)
            .where(old.thread_id == ChatThread.id, ToolResult.kind == "attachment")
        )
        return (
            select(
                ChatRun.id,
                ChatThread.id,
                ChatThread.folder_id,
                ChatRun.scope,
                ChatRun.created_at,
                user.id,
                user.text,
                answer.id,
                answer.text,
                answer.answer_policy,
                private,
                ChatThread.title,
                user.created_at,
            )
            .join(ChatThread, ChatThread.id == ChatRun.thread_id)
            .join(user, user.id == ChatRun.user_message_id)
            .join(answer, answer.id == ChatRun.message_id)
            .where(
                ChatRun.tenant_id == tenant_id,
                ChatThread.tenant_id == tenant_id,
                ChatThread.subject == subject,
                ChatThread.deleted_at.is_(None),
                ChatThread.archived_at.is_(None),
                ChatRun.status == "completed",
                user.status == "completed",
                answer.status == "completed",
                user.thread_id == ChatThread.id,
                answer.thread_id == ChatThread.id,
                user.role == "user",
                answer.role == "assistant",
            )
        )

    @transactional(
        datasource="primary", propagation=Propagation.REQUIRED, read_only=True, read_from_primary=True
    )
    async def candidates(self, subject, tenant_id, run, *, folder_id, project_enabled, limit):
        statement = self._candidates(subject, tenant_id).where(ChatRun.created_at < run.created_at)
        statement = statement.where(
            or_(
                ChatThread.id == run.thread_id,
                and_(
                    ChatThread.folder_id == folder_id,
                    ChatThread.id != run.thread_id,
                ),
            )
            if project_enabled
            else ChatThread.id == run.thread_id
        )
        rows = (
            await self._require_session().execute(
                statement.order_by(
                    (ChatThread.id == run.thread_id).desc(), ChatRun.created_at.desc(), ChatRun.id.desc()
                ).limit(min(80, limit))
            )
        ).all()
        return tuple(MemoryCandidate(*row) for row in rows)

    @transactional(
        datasource="primary", propagation=Propagation.REQUIRED, read_only=True, read_from_primary=True
    )
    async def selected(self, subject, tenant_id, run_ids: tuple[str, ...]):
        rows = (
            await self._require_session().execute(
                self._candidates(subject, tenant_id).where(ChatRun.id.in_(run_ids)).limit(129)
            )
        ).all()
        return tuple(MemoryCandidate(*row) for row in rows)

    @transactional(
        datasource="primary", propagation=Propagation.REQUIRED, read_only=True, read_from_primary=True
    )
    async def for_generation(self, generation_id: str):
        return await self._require_session().scalar(
            select(ChatMemoryManifest).where(ChatMemoryManifest.generation_id == generation_id)
        )

    @transactional(
        datasource="primary", propagation=Propagation.REQUIRED, read_only=True, read_from_primary=True
    )
    async def generation(self, run_id: str):
        reset = (
            select(func.max(ChatEvent.sequence))
            .where(
                ChatEvent.run_id == run_id,
                ChatEvent.type == "message_reset",
            )
            .scalar_subquery()
        )
        return await self._require_session().scalar(
            select(ToolResult)
            .where(
                ToolResult.run_id == run_id,
                ToolResult.kind == "generation",
                or_(
                    reset.is_(None), ToolResult.payload["generation"]["start_sequence"].as_integer() >= reset
                ),
            )
            .order_by(
                ToolResult.payload["generation"]["start_sequence"].as_integer().desc(),
                ToolResult.created_at.desc(),
                ToolResult.id.desc(),
            )
            .limit(1)
        )

    @transactional(datasource="primary", propagation=Propagation.REQUIRES_NEW)
    async def insert_manifest(self, value: ChatMemoryManifest):
        self._require_session().add(value)
        await self._require_session().flush()

    @transactional(
        datasource="primary", propagation=Propagation.REQUIRED, read_only=True, read_from_primary=True
    )
    async def context(self, subject: str, tenant_id: str, thread_id: str):
        return (
            await self._require_session().execute(
                select(ChatThread, ChatFolder, OrganizationChatSetting)
                .outerjoin(ChatFolder, ChatFolder.id == ChatThread.folder_id)
                .outerjoin(OrganizationChatSetting, OrganizationChatSetting.tenant_id == ChatThread.tenant_id)
                .where(
                    ChatThread.id == thread_id,
                    ChatThread.tenant_id == tenant_id,
                    ChatThread.subject == subject,
                )
            )
        ).one_or_none()

    @transactional(
        datasource="primary", propagation=Propagation.REQUIRED, read_only=True, read_from_primary=True
    )
    async def active_manifests(self, subject: str, tenant_id: str, run_ids: tuple[str, ...]):
        reset = (
            select(ChatEvent.run_id.label("run_id"), func.max(ChatEvent.sequence).label("sequence"))
            .where(ChatEvent.run_id.in_(run_ids), ChatEvent.type == "message_reset")
            .group_by(ChatEvent.run_id)
            .cte("memory_reset")
        )
        latest = (
            select(
                ToolResult.id.label("id"),
                ToolResult.run_id.label("run_id"),
                func.row_number()
                .over(
                    partition_by=ToolResult.run_id,
                    order_by=(
                        ToolResult.payload["generation"]["start_sequence"].as_integer().desc(),
                        ToolResult.created_at.desc(),
                        ToolResult.id.desc(),
                    ),
                )
                .label("position"),
            )
            .outerjoin(reset, reset.c.run_id == ToolResult.run_id)
            .where(
                ToolResult.run_id.in_(run_ids),
                ToolResult.kind == "generation",
                or_(
                    reset.c.sequence.is_(None),
                    ToolResult.payload["generation"]["start_sequence"].as_integer() >= reset.c.sequence,
                ),
            )
            .cte("memory_latest")
        )
        return tuple(
            (
                await self._require_session().execute(
                    select(ChatRun.id, ChatRun.status, ToolResult, ChatMemoryManifest)
                    .join(ChatThread, ChatThread.id == ChatRun.thread_id)
                    .outerjoin(latest, and_(latest.c.run_id == ChatRun.id, latest.c.position == 1))
                    .outerjoin(ToolResult, ToolResult.id == latest.c.id)
                    .outerjoin(ChatMemoryManifest, ChatMemoryManifest.generation_id == ToolResult.id)
                    .where(
                        ChatRun.id.in_(run_ids),
                        ChatRun.tenant_id == tenant_id,
                        ChatThread.tenant_id == tenant_id,
                        ChatThread.subject == subject,
                        ChatThread.deleted_at.is_(None),
                    )
                    .limit(52)
                )
            ).all()
        )

    @transactional(
        datasource="primary", propagation=Propagation.REQUIRED, read_only=True, read_from_primary=True
    )
    async def pinned_results(self, identifiers: tuple[str, ...]):
        session = self._require_session()
        size = (
            select(func.coalesce(func.sum(payload_bytes(session.get_bind().dialect.name)), 0))
            .where(ToolResult.id.in_(identifiers))
            .scalar_subquery()
        )
        return tuple(
            (
                await session.scalars(
                    select(ToolResult)
                    .where(ToolResult.id.in_(identifiers), size <= MAX_RESULT_BYTES)
                    .limit(1025)
                )
            ).all()
        )

    @transactional(
        datasource="primary", propagation=Propagation.REQUIRED, read_only=True, read_from_primary=True
    )
    async def availability(self, references, *, folder_id):
        identifiers = tuple(sorted({item.thread_id for item in references}))
        return tuple(
            (
                await self._require_session().execute(
                    select(ChatThread, ChatFolder)
                    .outerjoin(ChatFolder, ChatFolder.id == ChatThread.folder_id)
                    .where(ChatThread.id.in_(identifiers))
                    .limit(513)
                )
            ).all()
        )
