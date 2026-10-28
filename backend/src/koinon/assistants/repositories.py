# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0

from pyfly.container import repository
from pyfly.data.relational.sqlalchemy import Repository
from sqlalchemy import and_, func, or_, select

from koinon.assistants.entities import (
    AgentConfiguration,
    ChatEvent,
    ChatMessage,
    ChatRun,
    ChatThread,
    Provider,
    ToolResult,
)


@repository(name="assistants.providers")
class ProviderRepository(Repository[Provider, str]):
    """Encrypted provider settings."""


@repository(name="assistants.agents")
class AgentRepository(Repository[AgentConfiguration, str]):
    """Versioned agent definitions."""


@repository(name="assistants.threads")
class ChatThreadRepository(Repository[ChatThread, str]):
    """Private conversations."""


@repository(name="assistants.messages")
class ChatMessageRepository(Repository[ChatMessage, str]):
    """Durable visible conversation history."""

    async def snapshot_messages(self, thread_id: str, message_ids: list[str]):
        return (
            await self._require_session().execute(
                select(ChatMessage, ChatRun)
                .outerjoin(
                    ChatRun,
                    or_(ChatRun.message_id == ChatMessage.id, ChatRun.user_message_id == ChatMessage.id),
                )
                .where(ChatMessage.thread_id == thread_id, ChatMessage.id.in_(message_ids))
                .order_by(ChatMessage.created_at, ChatMessage.id)
            )
        ).all()

    async def private_context_origin(self, thread_id: str):
        return await self._require_session().scalar(
            select(func.min(ChatMessage.created_at))
            .join(ChatRun, ChatRun.user_message_id == ChatMessage.id)
            .join(ToolResult, ToolResult.run_id == ChatRun.id)
            .where(ChatMessage.thread_id == thread_id, ToolResult.kind == "attachment")
        )

    async def find_thread_messages(self, thread_id, *, before=None, limit=100):
        statement = (
            select(ChatMessage, ChatRun.id, ChatRun.sequence)
            .outerjoin(ChatRun, ChatRun.message_id == ChatMessage.id)
            .where(ChatMessage.thread_id == thread_id)
        )
        if before is not None:
            timestamp, message_id = before
            statement = statement.where(
                or_(
                    ChatMessage.created_at < timestamp,
                    and_(ChatMessage.created_at == timestamp, ChatMessage.id < message_id),
                )
            )
        return (
            await self._require_session().execute(
                statement.order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc()).limit(limit)
            )
        ).all()


@repository(name="assistants.runs")
class ChatRunRepository(Repository[ChatRun, str]):
    """Recoverable generation queue."""

    async def recent_title_runs(self, thread_id: str):
        return list(
            (
                await self._require_session().scalars(
                    select(ChatRun)
                    .where(ChatRun.thread_id == thread_id, ChatRun.status.in_(["completed", "running"]))
                    .order_by(ChatRun.created_at.desc(), ChatRun.id.desc())
                    .limit(2)
                )
            ).all()
        )

    async def count_active_for_subject(self, tenant_id: str, subject: str) -> int:
        statement = (
            select(func.count(ChatRun.id))
            .join(ChatThread, ChatThread.id == ChatRun.thread_id)
            .where(
                ChatRun.tenant_id == tenant_id,
                ChatThread.subject == subject,
                ChatRun.status.in_(["queued", "running"]),
            )
        )
        return int(await self._require_session().scalar(statement) or 0)


@repository(name="assistants.events")
class ChatEventRepository(Repository[ChatEvent, str]):
    """Ordered replayable stream events."""

    async def latest_reset(self, run_id: str) -> int | None:
        return await self._require_session().scalar(
            select(func.max(ChatEvent.sequence)).where(
                ChatEvent.run_id == run_id, ChatEvent.type == "message_reset"
            )
        )

    def _latest_activity(self, run_ids: list[str]):
        reset = (
            select(ChatEvent.run_id.label("reset_run"), func.max(ChatEvent.sequence).label("reset_sequence"))
            .where(ChatEvent.run_id.in_(run_ids), ChatEvent.type == "message_reset")
            .group_by(ChatEvent.run_id)
            .cte("activity_resets")
        )
        call_id = ChatEvent.data["tool_activity"]["call_id"].as_string()
        partition = (ChatEvent.run_id, call_id)
        calls = (
            select(
                ChatEvent.run_id.label("run_id"),
                ChatEvent.data.label("data"),
                call_id.label("call_id"),
                func.min(ChatEvent.sequence).over(partition_by=partition).label("first_sequence"),
                func.row_number()
                .over(partition_by=partition, order_by=ChatEvent.sequence.desc())
                .label("transition"),
            )
            .outerjoin(reset, ChatEvent.run_id == reset.c.reset_run)
            .where(
                ChatEvent.run_id.in_(run_ids),
                ChatEvent.type == "tool_activity",
                call_id.is_not(None),
                ChatEvent.sequence > func.coalesce(reset.c.reset_sequence, 0),
            )
            .cte("activity_calls")
        )
        return select(calls).where(calls.c.transition == 1).cte("latest_activity")

    @staticmethod
    def _activity_data(data):
        from koinon.assistants.tool_activity import ToolActivity

        return ToolActivity.model_validate(data["tool_activity"]).model_dump(exclude_none=True)

    async def activity_page(self, run_id: str, *, page: int, page_size: int):
        latest = self._latest_activity([run_id])
        session = self._require_session()
        total = await session.scalar(select(func.count()).select_from(latest)) or 0
        values = await session.scalars(
            select(latest.c.data)
            .order_by(latest.c.first_sequence, latest.c.call_id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return {
            "items": [self._activity_data(value) for value in values],
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": (total + page_size - 1) // page_size,
        }

    async def activity_previews(self, run_ids: list[str], *, limit: int = 5):
        if not run_ids:
            return {}
        latest = self._latest_activity(run_ids)
        previews = select(
            latest.c.run_id,
            latest.c.data,
            func.count().over(partition_by=latest.c.run_id).label("total"),
            func.row_number()
            .over(partition_by=latest.c.run_id, order_by=(latest.c.first_sequence, latest.c.call_id))
            .label("preview_position"),
        ).cte("activity_previews")
        rows = await self._require_session().execute(
            select(previews)
            .where(previews.c.preview_position <= limit)
            .order_by(previews.c.run_id, previews.c.preview_position)
        )
        result = {run_id: {"items": [], "total": 0} for run_id in run_ids}
        for row in rows:
            result[row.run_id]["items"].append(self._activity_data(row.data))
            result[row.run_id]["total"] = row.total
        return result

    async def find_after(self, run_id: str, sequence: int):
        return list(
            (
                await self._require_session().scalars(
                    select(ChatEvent)
                    .where(ChatEvent.run_id == run_id, ChatEvent.sequence > sequence)
                    .order_by(ChatEvent.sequence)
                    .limit(500)
                )
            ).all()
        )


@repository(name="assistants.tool_results")
class ToolResultRepository(Repository[ToolResult, str]):
    """Authorized evidence referenced by typed OpenUI components."""
