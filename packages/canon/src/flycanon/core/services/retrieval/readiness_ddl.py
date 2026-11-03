# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Make supported owner ANN maintenance participate in product readiness fencing."""

from typing import Any

from pyfly.agentic.exceptions import VectorStoreError
from pyfly.agentic.vectorstores.scoped import parse_scope_namespace


async def fence_index_ddl(connection: Any, *, set_id: str, namespace: str | None) -> None:
    installed = await connection.fetchval(
        "SELECT to_regprocedure('public.koinon_fence_document_index(text,text,text)') IS NOT NULL"
    )
    if not installed:
        return
    if namespace is None:
        raise VectorStoreError("Document index maintenance requires its exact tenant and workspace namespace")
    tenant, workspace = parse_scope_namespace(namespace)
    await connection.execute(
        "SELECT set_config('app.tenant_id',$1,true),set_config('app.workspace_id',$2,true)",
        tenant,
        workspace,
    )
    await connection.execute("SELECT public.koinon_fence_document_index($1,$2,$3)", tenant, workspace, set_id)
