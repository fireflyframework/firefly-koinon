# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from pyfly.container import repository
from pyfly.data.relational.sqlalchemy import Repository
from sqlalchemy import and_, exists, func, literal, or_, select
from sqlalchemy.orm import aliased

from koinon.corporate_identity.entities import CorporateProvider
from koinon.organization_people.entities import (
    OrganizationDirectorySettingRecord as Setting,
)
from koinon.organization_people.entities import (
    OrganizationPersonRecord as Person,
)
from koinon.organization_people.entities import (
    OrganizationProfileMappingRecord as Mapping,
)
from koinon.organization_people.entities import (
    OrganizationUnitRecord as Unit,
)
from koinon.profiles.entities import Profile


def subjects(members, tenant_id, workspace_id):
    query = select(members.c.subject).where(members.c.tenant_id == tenant_id, members.c.active.is_(True))
    if workspace_id is not None:
        query = query.where(or_(members.c.workspace_id.is_(None), members.c.workspace_id == workspace_id))
    return query.distinct()


def unit_paths(tenant_id, seeds):
    paths = (
        select(Unit.id, Unit.parent_id, literal(0).label("depth"))
        .where(Unit.tenant_id == tenant_id, Unit.id.in_(seeds))
        .cte("organization_visible_ancestors", recursive=True)
    )
    parent = aliased(Unit)
    return paths.union_all(
        select(parent.id, parent.parent_id, paths.c.depth + 1)
        .join(paths, parent.id == paths.c.parent_id)
        .where(parent.tenant_id == tenant_id, paths.c.depth < 31)
    )


@repository(name="organization_people.people_repository")
class OrganizationPersonRepository(Repository[Person, str]):
    async def scoped(self, tenant_id, identifier):
        return await self._require_session().scalar(
            select(Person)
            .where(Person.tenant_id == tenant_id, Person.id == identifier)
            .execution_options(populate_existing=True)
        )

    async def by_subject(self, tenant_id, subject):
        return await self._require_session().scalar(
            select(Person).where(Person.tenant_id == tenant_id, Person.subject == subject)
        )

    async def member(self, members, tenant_id, subject, workspace_id=None):
        return bool(
            await self._require_session().scalar(
                select(exists(subjects(members, tenant_id, workspace_id).where(members.c.subject == subject)))
            )
        )

    async def page(
        self,
        members,
        tenant_id,
        workspace_id=None,
        *,
        q="",
        job_title="",
        unit_id=None,
        department_id=None,
        manager_id=None,
        unassigned=False,
        page=1,
        page_size=25,
        identifier=None,
        subject=None,
    ):
        visible = subjects(members, tenant_id, workspace_id).subquery("visible_people")
        query = (
            select(visible.c.subject, Person, Profile)
            .select_from(visible)
            .outerjoin(Person, and_(Person.subject == visible.c.subject, Person.tenant_id == tenant_id))
            .outerjoin(Profile, Profile.subject == visible.c.subject)
        )
        if q:
            pattern = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
            query = query.where(
                or_(
                    Profile.display_name.ilike(pattern, escape="\\"),
                    Person.job_title.ilike(pattern, escape="\\"),
                )
            )
        if job_title:
            query = query.where(Person.job_title == job_title)
        if unit_id is not None:
            query = query.where(Person.unit_id == unit_id)
        if department_id is not None:
            descendants = (
                select(Unit.id, literal(0).label("depth"))
                .where(Unit.tenant_id == tenant_id, Unit.id == department_id)
                .cte("organization_department_children", recursive=True)
            )
            child = aliased(Unit)
            descendants = descendants.union_all(
                select(child.id, descendants.c.depth + 1)
                .join(descendants, child.parent_id == descendants.c.id)
                .where(child.tenant_id == tenant_id, descendants.c.depth < 31)
            )
            query = query.where(Person.unit_id.in_(select(descendants.c.id)))
        if manager_id is not None:
            query = query.where(Person.manager_id == manager_id)
        if unassigned:
            query = query.where(Person.id.is_(None))
        if identifier is not None:
            query = query.where(Person.id == identifier)
        if subject is not None:
            query = query.where(visible.c.subject == subject)
        session = self._require_session()
        total = int(await session.scalar(select(func.count()).select_from(query.subquery())) or 0)
        rows = (
            await session.execute(
                query.order_by(func.lower(func.coalesce(Profile.display_name, "")), visible.c.subject)
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
        return rows, total

    async def summaries(self, tenant_id, rows, members, workspace_id):
        session = self._require_session()
        seeds = {row.unit_id for _, row, _ in rows if row and row.unit_id}
        units = []
        if seeds:
            paths = unit_paths(tenant_id, seeds)
            units = list(
                (
                    await session.scalars(
                        select(Unit).where(Unit.tenant_id == tenant_id, Unit.id.in_(select(paths.c.id)))
                    )
                ).all()
            )
        manager_ids = {row.manager_id for _, row, _ in rows if row and row.manager_id}
        managers = []
        if manager_ids:
            managers = (
                await session.execute(
                    select(Person, Profile)
                    .outerjoin(Profile, Profile.subject == Person.subject)
                    .where(
                        Person.tenant_id == tenant_id,
                        Person.id.in_(manager_ids),
                        Person.subject.in_(subjects(members, tenant_id, workspace_id)),
                    )
                )
            ).all()
        provider_ids = {row.provider_id for _, row, _ in rows if row and row.provider_id}
        providers = (
            list(
                (
                    await session.scalars(
                        select(CorporateProvider).where(
                            CorporateProvider.tenant_id == tenant_id, CorporateProvider.id.in_(provider_ids)
                        )
                    )
                ).all()
            )
            if provider_ids
            else []
        )
        return (
            {row.id: row for row in units},
            {row.id: (row, profile) for row, profile in managers},
            {row.id: row for row in providers},
        )


@repository(name="organization_people.units_repository")
class OrganizationUnitRepository(Repository[Unit, str]):
    async def scoped(self, tenant_id, identifier):
        return await self._require_session().scalar(
            select(Unit)
            .where(Unit.tenant_id == tenant_id, Unit.id == identifier)
            .execution_options(populate_existing=True)
        )

    async def page(self, tenant_id, members, workspace_id, *, parent_id=None, q="", page=1, page_size=25):
        query = select(Unit).where(Unit.tenant_id == tenant_id, Unit.parent_id == parent_id)
        visible_ids = None
        if workspace_id is not None:
            seeds = select(Person.unit_id).where(
                Person.tenant_id == tenant_id, Person.subject.in_(subjects(members, tenant_id, workspace_id))
            )
            paths = unit_paths(tenant_id, seeds)
            visible_ids = select(paths.c.id)
            query = query.where(Unit.id.in_(visible_ids))
        if q:
            pattern = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
            query = query.where(Unit.name.ilike(pattern, escape="\\"))
        child = aliased(Unit)
        children = select(child.id).where(child.tenant_id == tenant_id, child.parent_id == Unit.id)
        if visible_ids is not None:
            children = children.where(child.id.in_(visible_ids))
        session = self._require_session()
        total = int(await session.scalar(select(func.count()).select_from(query.subquery())) or 0)
        rows = (
            await session.execute(
                query.add_columns(exists(children))
                .order_by(func.lower(Unit.name), Unit.id)
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
        return rows, total

    async def visible(self, tenant_id, identifier, members, workspace_id):
        query = select(Unit.id).where(Unit.tenant_id == tenant_id, Unit.id == identifier)
        if workspace_id is not None:
            seeds = select(Person.unit_id).where(
                Person.tenant_id == tenant_id, Person.subject.in_(subjects(members, tenant_id, workspace_id))
            )
            paths = unit_paths(tenant_id, seeds)
            query = query.where(Unit.id.in_(select(paths.c.id)))
        return await self._require_session().scalar(query) is not None

    async def occupied(self, tenant_id, identifier):
        session = self._require_session()
        return bool(
            await session.scalar(
                select(
                    exists(select(Unit.id).where(Unit.tenant_id == tenant_id, Unit.parent_id == identifier))
                )
            )
        ) or bool(
            await session.scalar(
                select(
                    exists(
                        select(Person.id).where(Person.tenant_id == tenant_id, Person.unit_id == identifier)
                    )
                )
            )
        )


@repository(name="organization_people.settings_repository")
class OrganizationDirectorySettingRepository(Repository[Setting, str]):
    pass


@repository(name="organization_people.mapping_repository")
class OrganizationProfileMappingRepository(Repository[Mapping, str]):
    async def scoped(self, tenant_id, provider_id):
        return await self._require_session().scalar(
            select(Mapping)
            .where(Mapping.tenant_id == tenant_id, Mapping.provider_id == provider_id)
            .execution_options(populate_existing=True)
        )

    async def provider(self, tenant_id, provider_id):
        return await self._require_session().scalar(
            select(CorporateProvider)
            .where(CorporateProvider.tenant_id == tenant_id, CorporateProvider.id == provider_id)
            .execution_options(populate_existing=True)
        )

    async def active(self, issuer, alias):
        return (
            await self._require_session().execute(
                select(Mapping, CorporateProvider)
                .join(
                    CorporateProvider,
                    and_(
                        CorporateProvider.tenant_id == Mapping.tenant_id,
                        CorporateProvider.id == Mapping.provider_id,
                    ),
                )
                .where(
                    Mapping.enabled.is_(True),
                    CorporateProvider.status == "active",
                    CorporateProvider.canonical_issuer == issuer,
                    CorporateProvider.broker_alias == alias,
                )
                .limit(101)
            )
        ).all()


async def subtree_depth(session, model, tenant_id, identifier, parent_field):
    tree = (
        select(model.id, literal(1).label("depth"))
        .where(model.tenant_id == tenant_id, model.id == identifier)
        .cte("organization_subtree_depth", recursive=True)
    )
    child = aliased(model)
    tree = tree.union_all(
        select(child.id, tree.c.depth + 1)
        .join(tree, getattr(child, parent_field) == tree.c.id)
        .where(child.tenant_id == tenant_id, tree.c.depth <= 32)
    )
    return int(await session.scalar(select(func.max(tree.c.depth))) or 1)
