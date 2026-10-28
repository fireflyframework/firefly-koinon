# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from pyfly.container import repository
from pyfly.data.relational.sqlalchemy import Repository
from sqlalchemy import select

from koinon.profiles.entities import Profile


@repository(name="profiles.repository")
class ProfileRepository(Repository[Profile, str]):
    """Primary native Data profile records keyed independently from identity claims."""

    async def author_rows(self, subjects: set[str]) -> list[Profile]:
        return list(
            (
                await self._require_session().scalars(select(Profile).where(Profile.subject.in_(subjects)))
            ).all()
        )
