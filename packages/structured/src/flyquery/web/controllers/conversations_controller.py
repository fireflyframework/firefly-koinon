# Copyright 2024-2026 Firefly Software Foundation
# Modifications Copyright 2026 Firefly Software Foundation
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

"""Conversations REST controller.

``/api/v1/conversations`` — CRUD + turn dispatch for drill-down conversations.

Path conventions:
* ``POST /api/v1/conversations``           -- create (201)
* ``GET  /api/v1/conversations``           -- list (newest first)
* ``GET  /api/v1/conversations/{id}``      -- fetch with turns
* ``POST /api/v1/conversations/{id}/turn`` -- ask next NL question (drill-down)
"""

from __future__ import annotations

import uuid

from pyfly.container import rest_controller
from pyfly.web import Body, PathVar, QueryParam, Valid, get_mapping, post_mapping, request_mapping
from starlette.requests import Request

from flyquery.core.services.query.conversation_service import ConversationService
from flyquery.core.services.query.runtime import StructuredQueryRuntimeFactory
from flyquery.interfaces.conversations import (
    ConversationCreate,
    ConversationRead,
    ConversationTurnRequest,
    TurnRead,
)
from flyquery.interfaces.pagination import Paginated
from flyquery.interfaces.query import AnswerResponse
from flyquery.web.conventions import ResourceNotFound, tenant_context_from_request

_DEFAULT_SCOPES: set[str] = {"flyquery.query:read"}


def _parse_workspace_id(s: str) -> uuid.UUID:
    """Parse workspace ID string to UUID, re-using the internal helper."""
    from flyquery.web.conventions import InvalidRequest

    try:
        return uuid.UUID(str(s))
    except (ValueError, AttributeError) as exc:
        raise InvalidRequest(f"workspace_id {s!r} is not a valid UUID") from exc


@rest_controller(name="structured.ConversationsController")
@request_mapping("/api/v1/conversations")
class ConversationsController:
    """Conversation CRUD and turn dispatch through managed application services."""

    def __init__(
        self,
        runtime_factory: StructuredQueryRuntimeFactory,
        conversation_service: ConversationService,
    ) -> None:
        self._runtime_factory = runtime_factory
        self._conversation_service = conversation_service

    # ------------------------------------------------------------------
    # POST /api/v1/conversations  (create)
    # ------------------------------------------------------------------

    @post_mapping("", status_code=201)
    async def create(
        self,
        http_request: Request,
        body: Valid[Body[ConversationCreate]],
    ) -> ConversationRead:
        """Create a new conversation.

        :param http_request: Starlette request (tenant context headers)
        :param body: optional title
        :return: the new ConversationRead (no turns yet)
        """
        ctx = tenant_context_from_request(http_request)
        workspace_id = _parse_workspace_id(ctx.workspace_id)
        row = await self._conversation_service.create(
            ctx.tenant_id,
            workspace_id,
            title=body.title,
            actor=ctx.actor or "user",
        )
        return ConversationRead.model_validate({**row, "turns": []})

    # ------------------------------------------------------------------
    # GET /api/v1/conversations  (list)
    # ------------------------------------------------------------------

    @get_mapping("")
    async def list_conversations(
        self,
        http_request: Request,
        limit: QueryParam[int] = 100,
        offset: QueryParam[int] = 0,
    ) -> Paginated[ConversationRead]:
        """List conversations for the caller's workspace, newest first.

        Service does not currently return a total; ``has_more`` is
        inferred from page size (``len(items) >= limit`` -> assume
        there may be more).
        """
        ctx = tenant_context_from_request(http_request)
        workspace_id = _parse_workspace_id(ctx.workspace_id)
        rows = await self._conversation_service.list(ctx.tenant_id, workspace_id)
        items = [ConversationRead.model_validate({**r, "turns": []}) for r in rows]
        sliced = items[offset : offset + limit]
        return Paginated.of(sliced, total=len(items), limit=limit, offset=offset)

    # ------------------------------------------------------------------
    # GET /api/v1/conversations/{conversation_id}  (fetch with turns)
    # ------------------------------------------------------------------

    @get_mapping("/{conversation_id}")
    async def read(self, conversation_id: PathVar[uuid.UUID]) -> ConversationRead:
        """Fetch a conversation with all its turns.

        :param conversation_id: conversation UUID
        :return: ConversationRead including turns list
        :raises ResourceNotFound: when conversation does not exist
        """
        row = await self._conversation_service.get_with_turns(conversation_id)
        if row is None:
            raise ResourceNotFound(f"conversation {conversation_id!r} not found")
        turns = [TurnRead.model_validate(t) for t in row.get("turns", [])]
        return ConversationRead.model_validate({**row, "turns": [t.model_dump(mode="json") for t in turns]})

    # ------------------------------------------------------------------
    # POST /api/v1/conversations/{conversation_id}/turn  (drill-down)
    # ------------------------------------------------------------------

    @post_mapping("/{conversation_id}/turn")
    async def post_turn(
        self,
        http_request: Request,
        conversation_id: PathVar[uuid.UUID],
        body: Valid[Body[ConversationTurnRequest]],
    ) -> AnswerResponse:
        """Ask a follow-up question inside an existing conversation.

        Loads the prior turn's ``executed_sql + table_qnames + snapshot_pins``
        and passes them into the query pipeline as drill-down context.

        :param http_request: Starlette request
        :param conversation_id: conversation UUID
        :param body: dataset_id + question
        :return: AnswerResponse from the full pipeline
        """
        ctx = tenant_context_from_request(http_request)
        workspace_id = _parse_workspace_id(ctx.workspace_id)

        # Verify the conversation exists before paying pipeline cost.
        conv = await self._conversation_service.get_with_turns(conversation_id)
        if conv is None:
            raise ResourceNotFound(f"conversation {conversation_id!r} not found")

        async with self._runtime_factory.unit(with_conversation=True) as runtime:
            svc = runtime.pipeline
            result = await svc.answer(
                tenant_id=ctx.tenant_id,
                workspace_id=workspace_id,
                dataset_id=body.dataset_id,
                question=body.question,
                scopes=_DEFAULT_SCOPES,
                conversation_id=conversation_id,
            )

        return AnswerResponse(
            query_id=result.query_id,
            sql=result.sql,
            execution_status=result.execution_status,
            preview=result.preview,
            row_count=result.row_count,
            truncated=result.truncated,
            elapsed_ms=result.elapsed_ms,
            chart_hint=result.chart_hint,
            explanation=result.explanation,
            clarification=result.clarification,
            grounded_summary=result.grounded_summary,
        )
