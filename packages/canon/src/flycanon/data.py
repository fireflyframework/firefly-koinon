# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Native transaction customization for document knowledge runtime scopes."""

from sqlalchemy import text

from flycanon.web.conventions.context import current_tenant_context


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
