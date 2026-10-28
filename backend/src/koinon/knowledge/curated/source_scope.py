# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Keep authorized document reads and their locks in the destination transaction."""

from contextlib import asynccontextmanager

from pyfly.data.transaction import current_unit_of_work
from sqlalchemy import text

from koinon.catalog.errors import AccessDenied


@asynccontextmanager
async def document_source_scope(tenant_id, workspace_id, *, authorize=None):
    unit = current_unit_of_work("canon")
    if unit is None or unit.resource.get_bind().dialect.name != "postgresql":
        yield
        return
    # The same guard serializes all operations on the native session. Hold it
    # across the full scoped read, including nested repository calls and restore.
    async with unit.guard:
        session = unit.resource
        with session.no_autoflush:
            tenant, workspace = (
                await session.execute(
                    text(
                        "SELECT current_setting('app.tenant_id',true), "
                        "current_setting('app.workspace_id',true)"
                    )
                )
            ).one()
            if tenant != tenant_id:
                raise AccessDenied(
                    "Source tenant differs from the native transaction", code="EVIDENCE_UNAVAILABLE"
                )
            if workspace != workspace_id:
                if authorize is None:
                    raise AccessDenied(
                        "Cross-workspace source admission is required", code="EVIDENCE_UNAVAILABLE"
                    )
                await authorize()
            try:
                await session.execute(
                    text("SELECT set_config('app.workspace_id',:workspace,true)"),
                    {"workspace": workspace_id},
                )
                yield
            finally:
                try:
                    await session.execute(
                        text("SELECT set_config('app.workspace_id',:workspace,true)"),
                        {"workspace": workspace or ""},
                    )
                except BaseException as error:
                    # A failed/cancelled restore must never permit a destination
                    # write to commit under the source workspace.
                    unit.set_rollback_only(error)
                    raise
