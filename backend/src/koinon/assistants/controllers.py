# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import asyncio

from pyfly.container import rest_controller
from pyfly.web import (
    Body,
    PathVar,
    QueryParam,
    Valid,
    get_mapping,
    post_mapping,
    request_mapping,
)
from pyfly.web.sse import SseEvent
from pyfly.web.sse.adapters.starlette import make_sse_response
from starlette.requests import Request
from starlette.responses import JSONResponse, StreamingResponse

from koinon.assistants.dtos import RunInput, ThreadInput
from koinon.assistants.history.service import ChatHistoryService
from koinon.assistants.service import AssistantService
from koinon.catalog.errors import AccessDenied
from koinon.security.identity import identity_from_request


@rest_controller(name="assistants.controller")
@request_mapping("/api/v1/tenants/{tenant_id}")
class AssistantController:
    def __init__(self, assistants: AssistantService, history: ChatHistoryService):
        self.assistants, self.history = assistants, history

    @get_mapping("/chat/threads")
    async def threads(
        self,
        tenant_id: PathVar[str],
        request: Request,
        q: QueryParam[str] = "",
        page: QueryParam[int] = 1,
        page_size: QueryParam[int] = 25,
        sort: QueryParam[str] = "updated_at",
        order: QueryParam[str] = "desc",
        folder_id: QueryParam[str | None] = None,
        unfiled: QueryParam[bool] = False,
        project_id: QueryParam[str | None] = None,
        workspace_id: QueryParam[str | None] = None,
        status: QueryParam[str] = "active",
    ) -> dict:
        return await self.history.thread_page(
            identity_from_request(request).subject,
            tenant_id,
            q=q,
            page=page,
            page_size=page_size,
            sort=sort,
            order=order,
            folder_id=folder_id,
            unfiled=unfiled,
            project_id=project_id,
            workspace_id=workspace_id,
            status=status,
        )

    @post_mapping("/chat/threads", status_code=201)
    async def thread_create(
        self, tenant_id: PathVar[str], body: Valid[Body[ThreadInput]], request: Request
    ) -> dict:
        return await self.history.create_thread(
            identity_from_request(request).subject,
            tenant_id,
            body.model_dump(exclude_unset=True, exclude_none=True),
        )

    @get_mapping("/chat/threads/{thread_id}/messages")
    async def messages(
        self,
        tenant_id: PathVar[str],
        thread_id: PathVar[str],
        request: Request,
        before: QueryParam[str | None] = None,
        limit: QueryParam[int] = 50,
    ) -> dict:
        return await self.assistants.message_page(
            identity_from_request(request).subject, tenant_id, thread_id, before=before, limit=limit
        )

    @post_mapping("/chat/threads/{thread_id}/runs", status_code=202)
    async def submit(
        self, tenant_id: PathVar[str], thread_id: PathVar[str], body: Valid[Body[RunInput]], request: Request
    ) -> dict:
        return await self.assistants.submit(
            identity_from_request(request).subject,
            tenant_id,
            thread_id,
            body.model_dump(exclude_unset=True, exclude_none=True),
        )

    @post_mapping("/chat/runs/{run_id}/cancel")
    async def cancel(self, tenant_id: PathVar[str], run_id: PathVar[str], request: Request) -> dict:
        return await self.assistants.cancel(identity_from_request(request).subject, tenant_id, run_id)

    @post_mapping("/chat/runs/{run_id}/retry", status_code=202)
    async def retry(self, tenant_id: PathVar[str], run_id: PathVar[str], request: Request) -> dict:
        return await self.assistants.retry(identity_from_request(request).subject, tenant_id, run_id)

    @get_mapping("/chat/runs/{run_id}/events")
    async def events(
        self, tenant_id: PathVar[str], run_id: PathVar[str], request: Request
    ) -> StreamingResponse:
        subject = identity_from_request(request).subject
        cursor = request.headers.get("Last-Event-ID", "0")

        async def authorized_source():
            initial = await self.assistants.run_events(subject, tenant_id, run_id, cursor)

            async def stream():
                pending, after = initial, cursor
                while not await request.is_disconnected():
                    try:
                        if pending is None:
                            pending = await self.assistants.run_events(subject, tenant_id, run_id, after)
                        for event in pending:
                            # Recheck buffered events when demand resumes after a slow client.
                            await self.assistants.owned_run(subject, tenant_id, run_id)
                            after = event["id"]
                            reset = await self.assistants.events.latest_reset(run_id)
                            if reset is not None and int(after) < reset:
                                continue
                            yield SseEvent(data=event["data"], id=after, event=event["type"])
                        run = await self.assistants.owned_run(subject, tenant_id, run_id)
                        if run.status in {"completed", "failed", "cancelled"} and int(after) >= run.sequence:
                            return
                        pending = None
                        await asyncio.sleep(0.5)
                    except AccessDenied:
                        yield SseEvent(
                            event="failed",
                            data={
                                "status": "failed",
                                "code": "ACCESS_DENIED",
                                "message": "Your access has changed. Reopen the conversation.",
                            },
                        )
                        return

            return stream()

        return await make_sse_response(
            authorized_source(),
            heartbeat_interval=7.5,
            max_event_bytes=1_048_576,
            headers={
                "Cache-Control": "no-store",
                "X-Accel-Buffering": "no",
                "X-Content-Type-Options": "nosniff",
            },
        )

    @get_mapping("/chat/runs/{run_id}/results/{result_id}")
    async def result(
        self, tenant_id: PathVar[str], run_id: PathVar[str], result_id: PathVar[str], request: Request
    ) -> dict:
        return await self.assistants.result(
            identity_from_request(request).subject, tenant_id, run_id, result_id
        )

    @get_mapping("/chat/runs/{run_id}/activity")
    async def activities(
        self,
        tenant_id: PathVar[str],
        run_id: PathVar[str],
        request: Request,
        page: QueryParam[int] = 1,
        page_size: QueryParam[int] = 25,
    ) -> dict:
        return await self.assistants.activity_page(
            identity_from_request(request).subject, tenant_id, run_id, page=page, page_size=page_size
        )

    @get_mapping("/chat/runs/{run_id}/audit")
    async def audit(self, tenant_id: PathVar[str], run_id: PathVar[str], request: Request) -> JSONResponse:
        from koinon.assistants.audit import AnswerAudits

        return JSONResponse(
            await request.app.state.context.get_bean(AnswerAudits).get(
                identity_from_request(request).subject, tenant_id, run_id
            ),
            headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
        )
