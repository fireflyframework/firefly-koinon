# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime

from pyfly.container import repository
from pyfly.data.relational.sqlalchemy import Repository
from sqlalchemy import delete, update

from koinon.mcp_auth.entities import McpAuthorization


@repository(name="mcp.oauth.repository")
class McpAuthorizationRepository(Repository[McpAuthorization, str]):
    async def transition(self, identifier: str, subject: str, before: str, **values) -> bool:
        result = await self._require_session().execute(
            update(McpAuthorization)
            .where(
                McpAuthorization.id == identifier,
                McpAuthorization.subject == subject,
                McpAuthorization.status == before,
                McpAuthorization.expires_at > datetime.now(UTC),
            )
            .values(**values)
            .returning(McpAuthorization.id),
        )
        return result.scalar_one_or_none() is not None

    async def purge_expired(self):
        await self._require_session().execute(
            delete(McpAuthorization).where(McpAuthorization.expires_at <= datetime.now(UTC)),
        )
