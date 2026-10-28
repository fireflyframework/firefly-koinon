# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Named native datasource injection and trusted background scope."""

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Annotated
from uuid import uuid4

from pyfly.container import Qualifier
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from flyquery.web.conventions.context import TenantContext, current_tenant_context, set_tenant_context


@dataclass(frozen=True)
class StructuredSessionBinding:
    sessionmaker: async_sessionmaker[AsyncSession]


StructuredSessions = Annotated[
    StructuredSessionBinding | async_sessionmaker[AsyncSession], Qualifier("structured.sessions")
]
StructuredAdminSessions = Annotated[
    StructuredSessionBinding | async_sessionmaker[AsyncSession], Qualifier("structured.admin_sessions")
]


def unwrap_sessions(
    value: StructuredSessionBinding | async_sessionmaker[AsyncSession],
) -> async_sessionmaker[AsyncSession]:
    return value.sessionmaker if isinstance(value, StructuredSessionBinding) else value


class TenantGucCustomizer:
    def __init__(self, datasource_name: str):
        self.datasources = frozenset({datasource_name})

    async def after_begin(self, connection, datasource) -> None:
        context = current_tenant_context()
        if context is not None and datasource.url.get_backend_name() == "postgresql":
            await connection.execute(
                text("SELECT set_config('app.tenant_id', :tenant, true)"), {"tenant": context.tenant_id}
            )
            await connection.execute(
                text("SELECT set_config('app.workspace_id', :workspace, true)"),
                {"workspace": context.workspace_id},
            )


@contextmanager
def workspace_scope(tenant_id: str, workspace_id: str, actor: str = "system:structured-worker"):
    context = TenantContext(
        tenant_id=tenant_id, workspace_id=str(workspace_id), actor=actor, correlation_id=str(uuid4())
    )
    token = set_tenant_context(context)
    try:
        yield context
    finally:
        token.var.reset(token.token)
