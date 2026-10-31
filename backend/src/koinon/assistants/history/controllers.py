# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from pyfly.container import rest_controller
from pyfly.web import (
    Body,
    PathVar,
    QueryParam,
    Valid,
    delete_mapping,
    get_mapping,
    patch_mapping,
    post_mapping,
    request_mapping,
)
from starlette.requests import Request

from koinon.assistants.history.dtos import FolderCreate, FolderPatch, ThreadPatch, TitleRequest
from koinon.assistants.history.service import ChatHistoryService
from koinon.assistants.title_service import TitleService
from koinon.security.identity import identity_from_request


@rest_controller(name="assistants.history.controller")
@request_mapping("/api/v1/tenants/{tenant_id}/chat")
class ChatHistoryController:
    def __init__(self, history: ChatHistoryService, titles: TitleService):
        self.history, self.titles = history, titles

    @get_mapping("/folders")
    async def folders(
        self,
        tenant_id: PathVar[str],
        request: Request,
        q: QueryParam[str] = "",
        page: QueryParam[int] = 1,
        page_size: QueryParam[int] = 25,
        parent_id: QueryParam[str | None] = None,
        root_only: QueryParam[bool] = False,
        workspace_id: QueryParam[str | None] = None,
        sort: QueryParam[str] = "name",
        order: QueryParam[str] = "asc",
    ) -> dict:
        return await self.history.folder_page(
            identity_from_request(request).subject,
            tenant_id,
            q=q,
            page=page,
            page_size=page_size,
            parent_id=parent_id,
            root_only=root_only,
            workspace_id=workspace_id,
            sort=sort,
            order=order,
        )

    @post_mapping("/folders", status_code=201)
    async def create_folder(
        self, tenant_id: PathVar[str], request: Request, body: Valid[Body[FolderCreate]]
    ) -> dict:
        return await self.history.create_folder(
            identity_from_request(request).subject,
            tenant_id,
            body.model_dump(exclude_unset=True, exclude_none=True),
        )

    @get_mapping("/folders/{folder_id}")
    async def folder(self, tenant_id: PathVar[str], folder_id: PathVar[str], request: Request) -> dict:
        return await self.history.get_folder(identity_from_request(request).subject, tenant_id, folder_id)

    @patch_mapping("/folders/{folder_id}")
    async def patch_folder(
        self,
        tenant_id: PathVar[str],
        folder_id: PathVar[str],
        request: Request,
        body: Valid[Body[FolderPatch]],
    ) -> dict:
        return await self.history.patch_folder(
            identity_from_request(request).subject, tenant_id, folder_id, body.model_dump(exclude_unset=True)
        )

    @delete_mapping("/folders/{folder_id}", status_code=204)
    async def delete_folder(
        self,
        tenant_id: PathVar[str],
        folder_id: PathVar[str],
        request: Request,
        expected_revision: QueryParam[int],
    ):
        await self.history.delete_folder(
            identity_from_request(request).subject, tenant_id, folder_id, expected_revision=expected_revision
        )

    @get_mapping("/threads/{thread_id}")
    async def thread(self, tenant_id: PathVar[str], thread_id: PathVar[str], request: Request) -> dict:
        return await self.history.get_thread(identity_from_request(request).subject, tenant_id, thread_id)

    @patch_mapping("/threads/{thread_id}")
    async def patch_thread(
        self,
        tenant_id: PathVar[str],
        thread_id: PathVar[str],
        request: Request,
        body: Valid[Body[ThreadPatch]],
    ) -> dict:
        return await self.history.patch_thread(
            identity_from_request(request).subject, tenant_id, thread_id, body.model_dump(exclude_unset=True)
        )

    @post_mapping("/threads/{thread_id}/title-suggestion")
    async def title_suggestion(
        self,
        tenant_id: PathVar[str],
        thread_id: PathVar[str],
        request: Request,
        body: Valid[Body[TitleRequest]],
    ) -> dict:
        return (
            await self.titles.propose(
                identity_from_request(request).subject,
                tenant_id,
                thread_id,
                body.agent_id,
                expected_revision=body.expected_revision,
            )
        ).model_dump()

    @delete_mapping("/threads/{thread_id}", status_code=204)
    async def delete_thread(
        self,
        tenant_id: PathVar[str],
        thread_id: PathVar[str],
        request: Request,
        expected_revision: QueryParam[int],
    ):
        await self.history.delete_thread(
            identity_from_request(request).subject,
            tenant_id,
            thread_id,
            expected_revision=expected_revision,
        )
