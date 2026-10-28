# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pyfly.kernel import ConflictException
from test_index_persistence import index_rows as index_rows

from koinon.assistants.entities import ChatThread
from koinon.assistants.repositories import ChatThreadRepository
from koinon.assistants.scope import KnowledgeScopePolicy
from koinon.catalog.entities import Membership
from koinon.catalog.errors import AccessDenied
from koinon.catalog.repositories import CatalogRepository, MembershipRepository, TenantRepository
from koinon.catalog.service import CatalogService
from koinon.knowledge.attachments.authority import AttachmentAuthority
from koinon.knowledge.repositories import DomainBindingRepository
from koinon.knowledge.service import KnowledgeFacade, KnowledgeSettings


async def prepared():
    members = MembershipRepository()
    for subject, role in (("issuer|owner", "viewer"), ("issuer|administrator", "admin")):
        await members.save(Membership(id=subject, subject=subject, tenant_id="tenant", role=role))
    threads = ChatThreadRepository()
    await threads.save(
        ChatThread(
            id="private-thread",
            tenant_id="tenant",
            subject="issuer|owner",
            title="Private",
            scope={"workspace_id": "workspace"},
        )
    )
    catalog = CatalogService(TenantRepository(), members, CatalogRepository())
    scopes = KnowledgeScopePolicy(catalog)
    knowledge = KnowledgeFacade(catalog, DomainBindingRepository(), SimpleNamespace(), KnowledgeSettings())
    return AttachmentAuthority(threads, scopes, knowledge), members, threads


async def test_same_tenant_administrator_and_foreign_tenant_cannot_read_owner_files(index_rows):
    authority, _, _ = await prepared()
    authority.scopes.validate_scope = AsyncMock(
        side_effect=AssertionError("Foreign ownership must fail first")
    )
    for subject, tenant in (("issuer|administrator", "tenant"), ("issuer|owner", "foreign")):
        with pytest.raises(AccessDenied):
            await authority.thread(subject, tenant, "private-thread")
    authority.scopes.validate_scope.assert_not_awaited()


async def test_owner_requires_current_tenant_membership_after_upload(index_rows):
    authority, members, _ = await prepared()
    assert (await authority.thread("issuer|owner", "tenant", "private-thread")).id == "private-thread"
    membership = await members.find_by_id("issuer|owner")
    membership.active = False
    await members.save(membership)
    with pytest.raises(AccessDenied):
        await authority.thread("issuer|owner", "tenant", "private-thread")


async def test_verified_bearer_principal_is_compared_as_canonical_issuer_subject(index_rows):
    from pyfly.security.context import SecurityContext
    from pyfly.security.context_holder import SecurityContextHolder

    authority, _, _ = await prepared()
    with SecurityContextHolder.using(
        SecurityContext(user_id="owner", attributes={"iss": "issuer", "sub": "owner"})
    ):
        assert await authority.thread("issuer|owner", "tenant", "private-thread")


async def test_archived_conversation_permits_owner_history_but_blocks_new_use(index_rows):
    authority, _, threads = await prepared()
    thread = await threads.find_by_id("private-thread")
    thread.archived_at = datetime.now(UTC)
    await threads.save(thread)
    assert await authority.thread("issuer|owner", "tenant", thread.id)
    with pytest.raises(ConflictException):
        await authority.thread("issuer|owner", "tenant", thread.id, active=True)


async def test_archived_selected_knowledge_ancestor_blocks_attachment_model_use(index_rows):
    authority, _, _ = await prepared()
    workspace = await authority.knowledge.catalog.catalog_repository.find_by_id("workspace")
    workspace.status = "archived"
    await authority.knowledge.catalog.catalog_repository.save(workspace)
    assert await authority.thread("issuer|owner", "tenant", "private-thread")
    with pytest.raises(AccessDenied):
        await authority.thread("issuer|owner", "tenant", "private-thread", active=True)
