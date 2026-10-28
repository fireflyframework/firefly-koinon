# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Private file authority shares current chat/catalog rules without a service dependency cycle."""

from pyfly.container import service
from pyfly.kernel import ConflictException
from pyfly.security.context_holder import SecurityContextHolder

from koinon.assistants.repositories import ChatThreadRepository
from koinon.assistants.scope import KnowledgeScopePolicy
from koinon.catalog.errors import AccessDenied
from koinon.knowledge.service import KnowledgeFacade


@service(name="knowledge.attachments.authority")
class AttachmentAuthority:
    def __init__(
        self, threads: ChatThreadRepository, scopes: KnowledgeScopePolicy, knowledge: KnowledgeFacade
    ):
        self.threads, self.scopes, self.knowledge = threads, scopes, knowledge

    async def thread(self, subject: str, tenant_id: str, thread_id: str, *, active=False):
        context = SecurityContextHolder.get_context()
        actor = context.user_id if context is not None else None
        if context is not None and context.attributes.get("iss") and context.attributes.get("sub"):
            if context.user_id != context.attributes["sub"]:
                raise AccessDenied("Private attachment actor is unavailable", code="ATTACHMENT_UNAVAILABLE")
            actor = context.attributes["iss"] + "|" + context.attributes["sub"]
        if context is not None and actor != subject:
            raise AccessDenied("Private attachment actor is unavailable", code="ATTACHMENT_UNAVAILABLE")
        row = await self.threads.find_by_id(thread_id)
        if row is None or row.tenant_id != tenant_id or row.subject != subject:
            raise AccessDenied(
                "Private attachment conversation is unavailable", code="ATTACHMENT_UNAVAILABLE"
            )
        await self.scopes.validate_scope(subject, tenant_id, row.scope)
        if active:
            if row.archived_at is not None:
                raise ConflictException(
                    "Restore this conversation before using or adding attachments",
                    code="ATTACHMENT_THREAD_ARCHIVED",
                )
            identifiers = [
                row.scope[key]
                for key in ("workspace_id", "project_id", "collection_id")
                if row.scope.get(key)
            ]
            identifiers.extend(row.scope.get("asset_ids") or [])
            for identifier in dict.fromkeys(identifiers):
                await self.knowledge._chain(subject, tenant_id, identifier)
        return row
