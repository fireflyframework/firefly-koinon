# Copyright 2024-2026 Firefly Software Foundation
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

"""ConversationService — CRUD over flyquery_conversations + flyquery_conversation_turns."""

from __future__ import annotations

import uuid
from typing import Any

from pyfly.container import service

from flyquery.core.services.query.conversation_repository import ConversationRepository


@service(name="structured.ConversationService")
class ConversationService:
    """Business logic layer over :class:`ConversationRepository`.

    Exposes create / list / get / last_turn / append_turn operations for
    the conversation drill-down pipeline. All methods operate on plain
    ``dict`` rows; Pydantic conversion is the caller's responsibility.

    :param repo: injected conversation repository
    """

    def __init__(self, repo: ConversationRepository) -> None:
        self._repo = repo

    async def create(
        self,
        tenant_id: str,
        workspace_id: uuid.UUID,
        *,
        title: str | None = None,
        actor: str = "user",
    ) -> dict[str, Any]:
        """Create a new conversation.

        :param tenant_id: tenant identifier
        :param workspace_id: workspace UUID
        :param title: optional human-readable title
        :param actor: actor who initiated the conversation
        :return: conversation dict with all persisted fields
        """
        return await self._repo.create_conversation(
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            title=title,
            actor=actor,
        )

    async def list(
        self,
        tenant_id: str,
        workspace_id: uuid.UUID,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Return conversations for the workspace, newest first.

        :param tenant_id: tenant identifier
        :param workspace_id: workspace UUID
        :param limit: max conversations to return
        :return: list of conversation dicts (no turns)
        """
        return await self._repo.list_conversations(tenant_id, workspace_id, limit=limit)

    async def get_with_turns(self, conversation_id: uuid.UUID) -> dict[str, Any] | None:
        """Fetch a conversation together with all its turns.

        Returns ``None`` when the conversation does not exist.

        :param conversation_id: conversation UUID
        :return: conversation dict with a ``turns`` list, or None
        """
        row = await self._repo.get_conversation(conversation_id)
        if row is None:
            return None
        turns = await self._repo.get_turns(conversation_id)
        return {**row, "turns": turns}

    async def last_turn(self, conversation_id: uuid.UUID) -> dict[str, Any] | None:
        """Return the most recent turn in a conversation, or None.

        Used by QueryService to load drill-down context (prior SQL + table refs).

        :param conversation_id: conversation UUID
        :return: most recent turn dict, or None if the conversation has no turns
        """
        return await self._repo.get_last_turn(conversation_id)

    async def append_turn(
        self,
        *,
        conversation_id: uuid.UUID,
        tenant_id: str,
        workspace_id: uuid.UUID,
        question: str,
        executed_sql: str | None,
        summary: str | None,
        table_qnames_json: list[str],
        snapshot_pins_json: dict[str, str],
        elapsed_ms: int | None = None,
        query_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        """Append a new turn to an existing conversation.

        :param conversation_id: parent conversation UUID
        :param tenant_id: tenant identifier
        :param workspace_id: workspace UUID
        :param question: NL question for this turn
        :param executed_sql: SQL that was executed (None on failure)
        :param summary: NL explanation produced by ExplainerAgent (None on failure)
        :param table_qnames_json: qualified table names referenced by executed_sql
        :param snapshot_pins_json: {table_id: snapshot_id} pins for reproducibility
        :param elapsed_ms: total elapsed time for this turn in milliseconds
        :return: the newly inserted turn dict
        """
        return await self._repo.append_turn(
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            conversation_id=conversation_id,
            question=question,
            executed_sql=executed_sql,
            summary=summary,
            table_qnames_json=table_qnames_json,
            snapshot_pins_json=snapshot_pins_json,
            elapsed_ms=elapsed_ms,
            **({"query_id": query_id} if query_id is not None else {}),
        )


class ProductConversation:
    """Load only one authorized, unchanged turn for a product operation."""

    def __init__(self, sessions, service):
        self._sessions, self._service = sessions, service

    async def last_turn(self, conversation_id):
        from pyfly.data.transaction import infrastructure_unit
        from pyfly.kernel import ServiceUnavailableException
        from sqlalchemy import text

        from flyquery.core.services.query import provenance

        scope = provenance.current()
        if scope is None:
            raise ServiceUnavailableException(
                "Conversation authority is unavailable", code="EVIDENCE_UNAVAILABLE"
            )
        parameters = {"id": conversation_id, "tenant": scope.tenant_id, "ws": uuid.UUID(scope.workspace_id)}
        async with infrastructure_unit(self._sessions, read_only=True) as session:
            parent = await session.scalar(
                text(
                    "SELECT id FROM flyquery_conversations WHERE id=:id AND tenant_id=:tenant AND workspace_id=:ws"
                ),
                parameters,
            )
            if parent is None:
                raise ServiceUnavailableException(
                    "Conversation scope is unavailable", code="EVIDENCE_UNAVAILABLE"
                )
            row = (
                (
                    await session.execute(
                        text(
                            "SELECT id,citations_json->>'query_id' AS query_id,snapshot_pins_json AS snapshot_pins,"
                            "md5(to_jsonb(t)::text) AS revision FROM flyquery_conversation_turns t "
                            "WHERE conversation_id=:id AND tenant_id=:tenant AND workspace_id=:ws "
                            "ORDER BY turn_index DESC LIMIT 1"
                        ),
                        parameters,
                    )
                )
                .mappings()
                .one_or_none()
            )
            identity = dict(row) if row is not None else None
        if identity is None:
            return None
        selected = await provenance.admit_rows("turn", (identity,))
        if not selected:
            raise ServiceUnavailableException(
                "Conversation source authority is unavailable", code="EVIDENCE_UNAVAILABLE"
            )
        async with infrastructure_unit(self._sessions, read_only=True) as session:
            row = (
                (
                    await session.execute(
                        text(
                            "SELECT * FROM flyquery_conversation_turns t WHERE id=:id AND tenant_id=:tenant "
                            "AND workspace_id=:ws AND md5(to_jsonb(t)::text)=:revision"
                        ),
                        {**parameters, "id": identity["id"], "revision": identity["revision"]},
                    )
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise ServiceUnavailableException("Conversation changed", code="EVIDENCE_UNAVAILABLE")
            return dict(row)

    async def append_turn(self, **fields):
        return await self._service.append_turn(**fields)
