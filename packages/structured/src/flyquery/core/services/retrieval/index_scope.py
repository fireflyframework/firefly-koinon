# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from uuid import UUID

from pyfly.kernel import ServiceUnavailableException
from sqlalchemy import text

from flyquery.web.conventions.context import current_tenant_context


def index_lock_key(tenant_id, workspace_id):
    return f"knowledge-index:structured:{tenant_id}:{workspace_id}"


async def guard_publication(session, binding):
    if binding is None:
        return
    context = current_tenant_context()
    if context is None:
        raise ValueError("A native scope is required before publishing an embedding")
    await session.execute(
        text("SELECT pg_advisory_xact_lock_shared(hashtextextended(:key,0))"),
        {"key": index_lock_key(context.tenant_id, context.workspace_id)},
    )
    exists = await session.scalar(text("SELECT to_regclass('public.flyquery_embedding_sets')"))
    active = (
        await session.scalar(
            text(
                "SELECT id FROM flyquery_embedding_sets WHERE tenant_id=:tenant AND workspace_id=:workspace AND status='active'"
            ),
            {"tenant": context.tenant_id, "workspace": UUID(context.workspace_id)},
        )
        if exists
        else None
    )
    if active != (binding.space_id if binding.versioned else None):
        raise ServiceUnavailableException(
            "The active embedding space changed during this operation; retry with the selected current connection",
            code="INDEX_ACTIVE_CHANGED",
        )
