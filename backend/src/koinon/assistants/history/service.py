# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Private conversation organization with current knowledge authorization and revisions."""

from pyfly.container import service
from pyfly.data.relational.sqlalchemy import transactional
from pyfly.kernel import ConflictException, InvalidRequestException

from koinon.assistants.entities import ChatThread
from koinon.assistants.history.dtos import one_line
from koinon.assistants.history.entities import ChatFolder
from koinon.assistants.history.mappers import folder_dto
from koinon.assistants.history.repositories import ChatFolderRepository
from koinon.assistants.history.settings import ChatHistorySettings
from koinon.assistants.lifecycle import identifier, timestamp
from koinon.assistants.mappers import thread_dto
from koinon.assistants.service import AssistantService
from koinon.catalog.errors import AccessDenied
from koinon.web.pagination import sql_page


@service(name="assistants.history")
class ChatHistoryService:
    def __init__(
        self, assistants: AssistantService, folders: ChatFolderRepository, settings: ChatHistorySettings
    ):
        self.assistants, self.folders, self.settings = assistants, folders, settings

    async def folder(self, subject: str, tenant_id: str, folder_id: str) -> ChatFolder:
        row = await self.folders.find_by_id(folder_id)
        if row is None or row.tenant_id != tenant_id or row.subject != subject:
            raise AccessDenied("Conversation folder is unavailable", code="ACCESS_DENIED")
        await self.assistants.validate_scope(subject, tenant_id, row.scope)
        return row

    async def _describe_folder(self, subject, tenant_id, row):
        count = 0
        for thread in await self.assistants.threads.find_all(
            subject=subject, tenant_id=tenant_id, folder_id=row.id
        ):
            if thread.archived_at is not None or thread.deleted_at is not None:
                continue
            try:
                await self.assistants.validate_scope(subject, tenant_id, thread.scope)
            except AccessDenied:
                continue
            count += 1
        return folder_dto(row, conversation_count=count)

    @transactional(read_only=True)
    async def get_folder(self, subject, tenant_id, folder_id):
        return await self._describe_folder(
            subject, tenant_id, await self.folder(subject, tenant_id, folder_id)
        )

    @staticmethod
    def check_revision(row, expected_revision):
        if type(expected_revision) is not int or expected_revision < 1:
            raise InvalidRequestException("Choose a valid revision", code="INVALID_REVISION")
        if row.revision != expected_revision:
            raise ConflictException(
                "This conversation or folder changed. Refresh and try again.", code="STALE_CONVERSATION"
            )

    async def within(self, subject, tenant_id, scope, limit):
        effective = await self.assistants.validate_scope(subject, tenant_id, scope, limit)
        if effective != scope:
            raise AccessDenied("The conversation exceeds this folder's knowledge scope", code="SCOPE_DENIED")

    def validate_tree(self, rows):
        parents = {row.id: row.parent_id for row in rows}
        for node in parents:
            visited = set()
            while node is not None:
                if node in visited:
                    raise ConflictException("A folder cannot contain itself", code="FOLDER_CYCLE")
                visited.add(node)
                if len(visited) > self.settings.max_folder_depth:
                    raise ConflictException("Choose a shallower folder", code="FOLDER_DEPTH_LIMIT")
                node = parents.get(node)

    @transactional(read_only=True)
    async def folder_page(
        self,
        subject,
        tenant_id,
        *,
        q="",
        page=1,
        page_size=25,
        parent_id=None,
        root_only=False,
        workspace_id=None,
        sort="name",
        order="asc",
    ):
        if root_only and parent_id is not None:
            raise InvalidRequestException("Choose a parent folder or root folders", code="INVALID_PAGE")
        requested = {"workspace_id": workspace_id} if workspace_id else None
        if requested is not None:
            await self.assistants.validate_scope(subject, tenant_id, requested)
        visible = []
        for row in await self.folders.find_all(subject=subject, tenant_id=tenant_id):
            try:
                await self.assistants.validate_scope(subject, tenant_id, row.scope)
            except AccessDenied:
                continue
            visible.append(row.id)
        if not visible and requested is None:
            await self.assistants.catalog.authorize(subject, tenant_id, "chat:use")
        predicates = [ChatFolder.id.in_(visible)]
        if root_only:
            predicates.append(ChatFolder.parent_id.is_(None))
        if workspace_id:
            predicates.append(ChatFolder.scope["workspace_id"].as_string() == workspace_id)
        if parent_id is not None:
            await self.folder(subject, tenant_id, parent_id)
            predicates.append(ChatFolder.parent_id == parent_id)
        result = await sql_page(
            ChatFolder,
            predicates,
            q=q,
            page=page,
            page_size=page_size,
            search=("name",),
            sort=sort,
            order=order,
            sorts=("name", "created_at", "updated_at"),
        )
        counts = {}
        for thread in await self.assistants.threads.find_all(subject=subject, tenant_id=tenant_id):
            if (
                thread.folder_id not in visible
                or thread.archived_at is not None
                or thread.deleted_at is not None
            ):
                continue
            try:
                await self.assistants.validate_scope(subject, tenant_id, thread.scope)
            except AccessDenied:
                continue
            counts[thread.folder_id] = counts.get(thread.folder_id, 0) + 1
        return {
            **result,
            "items": [folder_dto(row, conversation_count=counts.get(row.id, 0)) for row in result["items"]],
        }

    @transactional
    async def create_folder(self, subject, tenant_id, values):
        await self.assistants.catalog._lock_tenant(tenant_id)
        parent = (
            await self.folder(subject, tenant_id, values["parent_id"]) if values.get("parent_id") else None
        )
        scope = await self.assistants.validate_scope(
            subject,
            tenant_id,
            values.get("scope", parent.scope if parent else {}),
            parent.scope if parent else None,
        )
        rows = await self.folders.find_all(subject=subject, tenant_id=tenant_id)
        if len(rows) >= self.settings.max_folders:
            raise ConflictException("Your conversation folder limit has been reached", code="FOLDER_LIMIT")
        row = ChatFolder(
            id=identifier(),
            tenant_id=tenant_id,
            subject=subject,
            name=one_line(values["name"]),
            parent_id=parent.id if parent else None,
            scope=scope,
            memory_enabled=values.get("memory_enabled", False),
        )
        self.validate_tree([*rows, row])
        return folder_dto(await self.folders.save(row))

    @transactional
    async def patch_folder(self, subject, tenant_id, folder_id, values):
        await self.assistants.catalog._lock_tenant(tenant_id)
        row = await self.folder(subject, tenant_id, folder_id)
        self.check_revision(row, values["expected_revision"])
        if "parent_id" in values:
            parent = (
                await self.folder(subject, tenant_id, values["parent_id"]) if values["parent_id"] else None
            )
            if parent:
                await self.within(subject, tenant_id, row.scope, parent.scope)
            row.parent_id = parent.id if parent else None
            self.validate_tree(await self.folders.find_all(subject=subject, tenant_id=tenant_id))
        if "name" in values:
            row.name = one_line(values["name"])
        if "memory_enabled" in values:
            row.memory_enabled = values["memory_enabled"]
        row.revision += 1
        row.updated_at = timestamp()
        return await self._describe_folder(subject, tenant_id, await self.folders.save(row))

    @transactional
    async def delete_folder(self, subject, tenant_id, folder_id, *, expected_revision):
        await self.assistants.catalog._lock_tenant(tenant_id)
        row = await self.folder(subject, tenant_id, folder_id)
        self.check_revision(row, expected_revision)
        for child in await self.folders.find_all(parent_id=row.id):
            await self.folder(subject, tenant_id, child.id)
            child.parent_id, child.updated_at = row.parent_id, timestamp()
            child.revision += 1
            await self.folders.save(child)
        for thread in await self.assistants.threads.find_all(folder_id=row.id):
            if thread.deleted_at is not None:
                continue
            await self.assistants.thread(subject, tenant_id, thread.id)
            thread.folder_id, thread.updated_at = None, timestamp()
            thread.revision += 1
            await self.assistants.threads.save(thread)
        await self.folders.delete(row)

    @transactional
    async def create_thread(self, subject, tenant_id, values):
        await self.assistants.catalog._lock_tenant(tenant_id)
        folder = (
            await self.folder(subject, tenant_id, values["folder_id"]) if values.get("folder_id") else None
        )
        if folder:
            values = {**values, "scope": values.get("scope", folder.scope)}
            await self.within(subject, tenant_id, values["scope"], folder.scope)
        result = await self.assistants.create_thread(subject, tenant_id, values)
        row = await self.assistants.thread(subject, tenant_id, result["id"])
        row.folder_id = folder.id if folder else None
        return thread_dto(await self.assistants.threads.save(row))

    @transactional(read_only=True)
    async def thread_page(
        self,
        subject,
        tenant_id,
        *,
        q="",
        page=1,
        page_size=25,
        sort="updated_at",
        order="desc",
        folder_id=None,
        unfiled=False,
        project_id=None,
        workspace_id=None,
        status="active",
    ):
        if status not in {"active", "archived", "all"} or (folder_id and unfiled):
            raise InvalidRequestException("Choose valid conversation filters", code="INVALID_PAGE")
        requested = {
            key: value
            for key, value in {"workspace_id": workspace_id, "project_id": project_id}.items()
            if value
        }
        visible = [
            row["id"]
            for row in await self.assistants.list_threads(subject, tenant_id, scope=requested or None)
        ]
        predicates = [ChatThread.id.in_(visible)]
        if workspace_id:
            predicates.append(ChatThread.scope["workspace_id"].as_string() == workspace_id)
        if folder_id:
            await self.folder(subject, tenant_id, folder_id)
            predicates.append(ChatThread.folder_id == folder_id)
        if unfiled:
            predicates.append(ChatThread.folder_id.is_(None))
        if project_id:
            predicates.append(ChatThread.scope["project_id"].as_string() == project_id)
        if status != "all":
            predicates.append(
                ChatThread.archived_at.is_(None)
                if status == "active"
                else ChatThread.archived_at.is_not(None)
            )
        result = await sql_page(
            ChatThread,
            predicates,
            q=q,
            page=page,
            page_size=page_size,
            search=("title",),
            sort=sort,
            order=order,
            sorts=("title", "created_at", "updated_at"),
        )
        return {**result, "items": [thread_dto(row) for row in result["items"]]}

    @transactional(read_only=True)
    async def get_thread(self, subject, tenant_id, thread_id):
        return thread_dto(await self.assistants.thread(subject, tenant_id, thread_id))

    @transactional
    async def delete_thread(self, subject, tenant_id, thread_id, *, expected_revision):
        await self.assistants.catalog._lock_tenant(tenant_id)
        row = await self.assistants.thread(subject, tenant_id, thread_id, lock=True)
        self.check_revision(row, expected_revision)
        if any(
            run.status in {"queued", "running"}
            for run in await self.assistants.runs.find_all(thread_id=row.id)
        ):
            raise ConflictException(
                "Wait for or cancel the current answer before deleting", code="THREAD_BUSY"
            )
        row.deleted_at = row.updated_at = timestamp()
        row.revision += 1
        await self.assistants.threads.save(row)

    @transactional
    async def patch_thread(self, subject, tenant_id, thread_id, values):
        await self.assistants.catalog._lock_tenant(tenant_id)
        row = await self.assistants.thread(subject, tenant_id, thread_id, lock=True)
        self.check_revision(row, values["expected_revision"])
        if "folder_id" in values:
            folder = (
                await self.folder(subject, tenant_id, values["folder_id"]) if values["folder_id"] else None
            )
            if folder:
                await self.within(subject, tenant_id, row.scope, folder.scope)
            row.folder_id = folder.id if folder else None
        if "archived" in values:
            if values["archived"] and any(
                run.status in {"queued", "running"}
                for run in await self.assistants.runs.find_all(thread_id=row.id)
            ):
                raise ConflictException(
                    "Wait for or cancel the current answer before archiving", code="THREAD_BUSY"
                )
            row.archived_at = timestamp() if values["archived"] else None
        if "title" in values:
            row.title, row.title_source = one_line(values["title"]), "manual"
        row.revision += 1
        row.updated_at = timestamp()
        return thread_dto(await self.assistants.threads.save(row))

    @transactional
    async def apply_generated_title(self, subject, tenant_id, thread_id, title, *, expected_revision) -> bool:
        await self.assistants.catalog._lock_tenant(tenant_id)
        row = await self.assistants.thread(subject, tenant_id, thread_id, lock=True)
        if row.title_source != "default" or row.revision != expected_revision:
            return False
        value = one_line(title)
        if len(value) > 120:
            raise InvalidRequestException("Choose a title up to 120 characters", code="INVALID_THREAD")
        row.title, row.title_source = value, "ai"
        row.revision += 1
        row.updated_at = timestamp()
        await self.assistants.threads.save(row)
        return True
