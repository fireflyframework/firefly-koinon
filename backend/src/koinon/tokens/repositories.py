# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime

from pyfly.container import repository
from pyfly.data.relational.sqlalchemy import Repository

from koinon.tokens.entities import PersonalToken


@repository(name="tokens.repository")
class PersonalTokenRepository(Repository[PersonalToken, str]):
    """Only a digest is retained; plaintext credentials are returned once."""

    async def touch(self, token_id: str):
        from datetime import timedelta

        from sqlalchemy import or_, update

        now = datetime.now(UTC)
        await self._require_session().execute(
            update(PersonalToken)
            .where(
                PersonalToken.id == token_id,
                or_(
                    PersonalToken.last_used_at.is_(None),
                    PersonalToken.last_used_at < now - timedelta(minutes=5),
                ),
            )
            .values(last_used_at=now)
        )
