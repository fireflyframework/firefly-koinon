# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Actual native read origin observed on the caller's managed session."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from koinon.knowledge.capture_dtos import NativeDatabaseContext


async def database_context(session: AsyncSession) -> NativeDatabaseContext:
    engine = session.get_bind().dialect.name
    identity = (
        (
            await session.execute(
                text(
                    "SELECT current_database() AS database, current_catalog AS catalog, "
                    "current_schema() AS schema"
                )
            )
        )
        .mappings()
        .one()
        if engine == "postgresql"
        else {}
    )
    return NativeDatabaseContext(
        engine, identity.get("database"), identity.get("catalog"), identity.get("schema")
    )
