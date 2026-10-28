# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime, timedelta

from pyfly.container import repository
from pyfly.data.relational.sqlalchemy import Repository
from sqlalchemy import func, or_, select, update

from koinon.authorized_applications.entities import AuthorizedApplication


@repository(name="authorized_applications.repository")
class AuthorizedApplicationRepository(Repository[AuthorizedApplication, str]):
    async def active_count(self, subject: str) -> int:
        return int(
            await self._require_session().scalar(
                select(func.count())
                .select_from(AuthorizedApplication)
                .where(
                    AuthorizedApplication.subject == subject,
                    AuthorizedApplication.revoked_at.is_(None),
                    AuthorizedApplication.expires_at > datetime.now(UTC),
                )
            )
            or 0
        )

    async def touch(self, identifier: str):
        now = datetime.now(UTC)
        await self._require_session().execute(
            update(AuthorizedApplication)
            .where(
                AuthorizedApplication.id == identifier,
                AuthorizedApplication.revoked_at.is_(None),
                or_(
                    AuthorizedApplication.last_used_at.is_(None),
                    AuthorizedApplication.last_used_at < now - timedelta(minutes=5),
                ),
            )
            .values(last_used_at=now)
        )
