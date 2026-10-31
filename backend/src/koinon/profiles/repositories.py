# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from pyfly.container import repository
from pyfly.data.relational.sqlalchemy import Repository
from sqlalchemy import or_, select

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

    async def people_rows(self, members, tenant_id, workspace_id, q, after, limit):
        members = members.c
        statement = (
            select(members.subject, Profile)
            .outerjoin(Profile, Profile.subject == members.subject)
            .where(members.tenant_id == tenant_id, members.active.is_(True))
            .distinct()
        )
        if workspace_id:
            statement = statement.where(
                or_(members.workspace_id.is_(None), members.workspace_id == workspace_id)
            )
        from koinon.corporate_profiles.expressions import presentation_joins
        from koinon.organization_people.entities import OrganizationPersonRecord

        statement = statement.outerjoin(
            OrganizationPersonRecord,
            (OrganizationPersonRecord.tenant_id == tenant_id)
            & (OrganizationPersonRecord.subject == members.subject),
        )
        statement, display_name = presentation_joins(statement, members.subject, tenant_id, Profile)
        if q:
            pattern = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
            statement = statement.where(
                or_(
                    display_name.ilike(pattern, escape="\\"),
                    members.subject.ilike(pattern, escape="\\"),
                )
            )
        if after:
            statement = statement.where(members.subject > after)
        return list(
            (
                await self._require_session().execute(statement.order_by(members.subject).limit(limit + 1))
            ).all()
        )
