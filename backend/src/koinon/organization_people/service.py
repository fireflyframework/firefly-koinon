# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime
from typing import NoReturn
from uuid import uuid4

from pyfly.container import service
from pyfly.data.relational.sqlalchemy import Propagation, transactional
from pyfly.data.transaction import current_unit_of_work
from pyfly.kernel import ConflictException, InvalidRequestException

from koinon.catalog.errors import AccessDenied
from koinon.catalog.service import CatalogService
from koinon.corporate_profiles.mappers import decorate_person
from koinon.corporate_profiles.projector import CorporateProfileProjector
from koinon.corporate_profiles.repositories import CorporateProfileRepository
from koinon.organization_people.dtos import (
    OrganizationDirectorySettings,
    OrganizationDirectorySettingsInput,
    OrganizationPersonCreate,
    OrganizationPersonPage,
    OrganizationPersonPatch,
    OrganizationProfileMappingInput,
    OrganizationUnitInput,
    OrganizationUnitPage,
    OrganizationUnitPatch,
)
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
from koinon.organization_people.mappers import person_view, unit_view
from koinon.organization_people.repositories import (
    OrganizationDirectorySettingRepository,
    OrganizationPersonRepository,
    OrganizationProfileMappingRepository,
    OrganizationUnitRepository,
)
from koinon.profiles.service import ProfileService, profile_id


def denied() -> NoReturn:
    raise AccessDenied("Organization information is unavailable in this context", code="ACCESS_DENIED")


def conflict(message="Organization information changed. Reload before saving.") -> NoReturn:
    raise ConflictException(message, code="ORGANIZATION_CONFLICT")


def bounds(page=1, page_size=25, **values):
    if (
        type(page) is not int
        or type(page_size) is not int
        or not 1 <= page <= 100000
        or not 1 <= page_size <= 50
    ):
        raise InvalidRequestException("Choose a supported directory page", code="INVALID_DIRECTORY")
    for key, value in values.items():
        if value is not None and (
            not isinstance(value, str)
            or len(value) > (160 if key == "job_title" else 80)
            or any(ord(char) < 32 for char in value)
        ):
            raise InvalidRequestException("Choose supported directory filters", code="INVALID_DIRECTORY")


@service(name="organization_people.service")
class OrganizationPeopleService:
    def __init__(
        self,
        catalog: CatalogService,
        profiles: ProfileService,
        people: OrganizationPersonRepository,
        units: OrganizationUnitRepository,
        settings: OrganizationDirectorySettingRepository,
        mappings: OrganizationProfileMappingRepository,
        presentation: CorporateProfileProjector | None = None,
        corporate_profiles: CorporateProfileRepository | None = None,
    ):
        self.presentation = presentation
        self.corporate_profiles = corporate_profiles
        (
            self.catalog,
            self.profiles,
            self.people,
            self.unit_repository,
            self.setting_repository,
            self.mappings,
        ) = catalog, profiles, people, units, settings, mappings

    async def _membership(self, actor, tenant_id, workspace_id=None):
        await self.catalog._validate_workspace(tenant_id, workspace_id)
        grant = await self.catalog.restriction.grant(actor) if self.catalog.restriction else None
        if grant is not None and (
            grant.tenant_id != tenant_id
            or grant.asset_ids is not None
            or grant.workspace_ids is not None
            and workspace_id not in grant.workspace_ids
        ):
            denied()
        if not await self.people.member(
            self.catalog.effective_membership_rows(), tenant_id, actor, workspace_id
        ):
            denied()
        return grant

    async def _scope(self, actor, tenant_id, workspace_id=None):
        await self._membership(actor, tenant_id, workspace_id)
        if "members:write" in await self.catalog.permissions(actor, tenant_id):
            return workspace_id
        setting = await self.setting_repository.find_by_id(tenant_id)
        if setting is None or setting.visibility != "shared_workspaces" or workspace_id is None:
            denied()
        await self.catalog.authorize(actor, tenant_id, "catalog:read", workspace_id)
        return workspace_id

    async def _write(self, actor, tenant_id):
        await self.catalog.authorize(actor, tenant_id, "members:write")
        await self.catalog._lock_tenant(tenant_id)
        await self.catalog.authorize(actor, tenant_id, "members:write")

    async def _member(self, tenant_id, subject, workspace_id=None):
        if not await self.people.member(
            self.catalog.effective_membership_rows(), tenant_id, subject, workspace_id
        ):
            denied()

    async def _person(self, tenant_id, identifier) -> Person:
        row = await self.people.scoped(tenant_id, identifier)
        if row is None:
            denied()
        return row

    async def _unit(self, tenant_id, identifier) -> Unit:
        row = await self.unit_repository.scoped(tenant_id, identifier)
        if row is None:
            denied()
        return row

    async def _verify_output(self, actor, tenant_id, workspace_id, rows, manager_rows):
        await self._scope(actor, tenant_id, workspace_id)
        wanted = {subject for subject, _, _ in rows} | {row.subject for row, _ in manager_rows.values()}
        if wanted:
            members = self.catalog.effective_membership_rows()
            current = await self.people.visible_subjects(members, tenant_id, wanted, workspace_id)
            if not wanted <= current:
                denied()

    @transactional(propagation=Propagation.REQUIRES_NEW, read_only=True)
    async def _fresh_output(self, actor, tenant_id, workspace_id, rows, managers, total, filters):
        # Re-enter native Data so an earlier read snapshot cannot retain revoked visibility.
        await self._verify_output(actor, tenant_id, workspace_id, rows, managers)
        current, current_total = await self.people.page(
            self.catalog.effective_membership_rows(), tenant_id, workspace_id, **filters
        )

        def keys(values):
            return [(subject, row.id if row else None) for subject, row, _ in values]

        if current_total != total or keys(current) != keys(rows):
            denied()

    @transactional(propagation=Propagation.REQUIRES_NEW, read_only=True)
    async def _fresh_self_output(self, actor, tenant_id, workspace_id, managers):
        await self._membership(actor, tenant_id, workspace_id)
        if managers:
            await self._scope(actor, tenant_id, workspace_id)
            for manager, _ in managers.values():
                await self._member(tenant_id, manager.subject, workspace_id)

    @transactional(propagation=Propagation.REQUIRES_NEW, read_only=True)
    async def _fresh_avatar_scope(self, actor, tenant_id, workspace_id, subject):
        await self._scope(actor, tenant_id, workspace_id)
        await self._member(tenant_id, subject, workspace_id)

    @transactional(propagation=Propagation.REQUIRES_NEW, read_only=True)
    async def _fresh_units(self, actor, tenant_id, workspace_id, rows, total, filters):
        scope = await self._scope(actor, tenant_id, workspace_id)
        latest, latest_total = await self.unit_repository.page(
            tenant_id, self.catalog.effective_membership_rows(), scope, **filters
        )
        if latest_total != total or [(row.id, bool(children)) for row, children in latest] != [
            (row.id, bool(children)) for row, children in rows
        ]:
            denied()

    @transactional(propagation=Propagation.REQUIRES_NEW, read_only=True)
    async def _fresh_mapping_scope(self, actor, tenant_id, provider_id):
        await self.catalog.authorize(actor, tenant_id, "identity:manage")
        if await self.mappings.provider(tenant_id, provider_id) is None:
            denied()

    async def _page(self, actor, tenant_id, workspace_id=None, **filters):
        workspace_id = await self._scope(actor, tenant_id, workspace_id)
        members = self.catalog.effective_membership_rows()
        rows, total = await self.people.page(members, tenant_id, workspace_id, **filters)
        units, managers, providers = await self.people.summaries(tenant_id, rows, members, workspace_id)
        unit = current_unit_of_work("primary")
        if unit is not None and unit.read_only:
            await self._fresh_output(actor, tenant_id, workspace_id, rows, managers, total, filters)
        else:
            await self._verify_output(actor, tenant_id, workspace_id, rows, managers)
        items = [
            person_view(subject, row, profile, tenant_id, workspace_id, units, managers, providers)
            for subject, row, profile in rows
        ]
        if self.presentation is not None:
            query, page_query = self.people.presentation_queries(members, tenant_id, workspace_id, **filters)
            wanted = {subject for subject, _, _ in rows} | {row.subject for row, _ in managers.values()}
            projected = await self.presentation.batch(
                actor,
                tenant_id,
                wanted,
                workspace_id,
                count_query=query if unit is not None and unit.read_only else None,
                expected_total=total,
                people=([row for _, row, _ in rows if row] + [row for row, _ in managers.values()])
                if unit is not None and unit.read_only
                else (),
                units=list(units.values()) if unit is not None and unit.read_only else (),
                unassigned=[subject for subject, row, _ in rows if row is None]
                if unit is not None and unit.read_only
                else (),
                page_query=page_query if unit is not None and unit.read_only else None,
                page_subjects=[subject for subject, _, _ in rows],
            )
            items = [
                decorate_person(
                    value,
                    subject,
                    projected,
                    tenant_id,
                    workspace_id,
                    managers[row.manager_id][0].subject if row and row.manager_id in managers else None,
                )
                for value, (subject, row, _) in zip(items, rows, strict=True)
            ]
        size = filters.get("page_size", 25)
        return OrganizationPersonPage(
            items=items,
            total=total,
            page=filters.get("page", 1),
            page_size=size,
            pages=(total + size - 1) // size,
        )

    @transactional(read_only=True)
    async def page(
        self,
        actor,
        tenant_id,
        *,
        workspace_id=None,
        q="",
        job_title="",
        unit_id=None,
        department_id=None,
        manager_id=None,
        unassigned=False,
        page=1,
        page_size=25,
    ):
        bounds(
            page,
            page_size,
            q=q,
            job_title=job_title,
            unit_id=unit_id,
            department_id=department_id,
            manager_id=manager_id,
        )
        if type(unassigned) is not bool:
            raise InvalidRequestException("Choose supported directory filters", code="INVALID_DIRECTORY")
        scope = await self._scope(actor, tenant_id, workspace_id)
        if manager_id is not None:
            await self._view(actor, tenant_id, manager_id, workspace_id)
        for unit in (unit_id, department_id):
            if unit is not None and not await self.unit_repository.visible(
                tenant_id, unit, self.catalog.effective_membership_rows(), scope
            ):
                denied()

        return await self._page(
            actor,
            tenant_id,
            workspace_id,
            q=q,
            job_title=job_title,
            unit_id=unit_id,
            department_id=department_id,
            manager_id=manager_id,
            unassigned=unassigned,
            page=page,
            page_size=page_size,
        )

    async def _view(self, actor, tenant_id, identifier, workspace_id=None):
        result = await self._page(actor, tenant_id, workspace_id, identifier=identifier, page_size=1)
        if not result.items:
            denied()
        return result.items[0]

    @transactional(read_only=True)
    async def get(self, actor, tenant_id, identifier, *, workspace_id=None):
        return await self._view(actor, tenant_id, identifier, workspace_id)

    @transactional(read_only=True)
    async def self(self, actor, tenant_id, *, workspace_id=None):
        grant = await self._membership(actor, tenant_id, workspace_id)
        if grant is not None and not {"profile:read", "profile:write"}.intersection(grant.scopes):
            denied()
        members = self.catalog.effective_membership_rows()
        rows, _ = await self.people.page(members, tenant_id, workspace_id, subject=actor, page_size=1)
        if not rows:
            denied()
        units, managers, providers = await self.people.summaries(tenant_id, rows, members, workspace_id)
        # Self reads do not turn administrative-only visibility into access to colleagues.
        if "members:write" not in await self.catalog.permissions(actor, tenant_id):
            setting = await self.setting_repository.find_by_id(tenant_id)
            if setting is None or setting.visibility != "shared_workspaces" or workspace_id is None:
                managers = {}
        await self._membership(actor, tenant_id, workspace_id)
        await self._member(tenant_id, actor, workspace_id)
        for manager, _ in managers.values():
            await self._member(tenant_id, manager.subject, workspace_id)
        await self._fresh_self_output(actor, tenant_id, workspace_id, managers)
        subject, row, profile = rows[0]
        value = person_view(subject, row, profile, tenant_id, workspace_id, units, managers, providers)
        if self.presentation is not None:
            wanted = {actor} | {item.subject for item, _ in managers.values()}
            projected = await self.presentation.batch(
                actor,
                tenant_id,
                wanted,
                workspace_id,
                own=True,
                people=[row] if row else (),
                units=list(units.values()),
                unassigned=[actor] if row is None else (),
            )
            return decorate_person(
                value,
                actor,
                projected,
                tenant_id,
                workspace_id,
                managers[row.manager_id][0].subject if row and row.manager_id in managers else None,
            )
        return value

    @transactional(read_only=True)
    async def avatar(self, actor, tenant_id, identifier, *, workspace_id=None):
        await self._membership(actor, tenant_id, workspace_id)
        row = await self.people.scoped(tenant_id, identifier)
        profile = await self.profiles.profiles.find_by_id(identifier) if row is None else None
        subject = row.subject if row else profile.subject if profile else None
        if subject is None:
            denied()
        if subject != actor:
            await self._scope(actor, tenant_id, workspace_id)
        if self.presentation is not None:
            projected = await self.presentation.batch(
                actor, tenant_id, {subject}, workspace_id, own=subject == actor
            )
            content = projected[subject].avatar
            if not content:
                from pyfly.kernel import ResourceNotFoundException

                raise ResourceNotFoundException("Avatar is unavailable", code="AVATAR_NOT_FOUND")
            return content
        await self._member(tenant_id, subject, workspace_id)
        content = await self.profiles.avatar(subject)
        await self._fresh_avatar_scope(actor, tenant_id, workspace_id, subject)
        return content

    @transactional(read_only=True)
    async def reports(self, actor, tenant_id, identifier, *, workspace_id=None, page=1, page_size=25):
        bounds(page, page_size)
        await self._view(actor, tenant_id, identifier, workspace_id)
        return await self._page(
            actor, tenant_id, workspace_id, manager_id=identifier, page=page, page_size=page_size
        )

    async def _links(self, tenant_id, row, unit_id, manager_id):
        if unit_id is not None:
            await self._unit(tenant_id, unit_id)
        current = manager_id
        seen = {row.id}
        for _ in range(32):
            if current is None:
                depth = await self.people.subtree_depth(tenant_id, row.id)
                if len(seen) - 1 + depth > 32:
                    conflict("Reporting lines exceed the supported depth")
                return
            if current in seen:
                conflict("Reporting lines cannot contain a cycle")
            seen.add(current)
            manager = await self._person(tenant_id, current)
            await self._member(tenant_id, manager.subject)
            current = manager.manager_id
        conflict("Reporting lines exceed the supported depth")

    async def _saved(self, actor, tenant_id, row, action):
        await self.people.save(row)
        await self.catalog.authorize(actor, tenant_id, "members:write")
        await self._member(tenant_id, row.subject)
        await self.catalog._audit(actor, tenant_id, action, row.id, {"revision": row.revision})
        return await self._view(actor, tenant_id, row.id)

    @transactional
    async def create(self, actor, tenant_id, body: OrganizationPersonCreate):
        await self._write(actor, tenant_id)
        subject = body.subject
        if body.profile_id is not None:
            profile = await self.profiles.profiles.find_by_id(body.profile_id)
            if profile is None:
                denied()
            subject = profile.subject
        if subject is None:
            denied()
        try:
            profile_id(subject)
        except (ValueError, TypeError):
            denied()
        await self._member(tenant_id, subject)
        if await self.people.by_subject(tenant_id, subject):
            conflict("Organization information already exists for this person")
        row = Person(
            id=str(uuid4()),
            tenant_id=tenant_id,
            subject=subject,
            job_title=body.job_title,
            unit_id=body.unit_id,
            manager_id=body.manager_id,
            revision=1,
            managed_fields=[],
            pending_manager=False,
            observation_status="not_observed",
            updated_by=actor,
        )
        await self._links(tenant_id, row, row.unit_id, row.manager_id)
        return await self._saved(actor, tenant_id, row, "organization.person.created")

    @transactional
    async def update(self, actor, tenant_id, identifier, body: OrganizationPersonPatch):
        await self._write(actor, tenant_id)
        row = await self._person(tenant_id, identifier)
        await self._member(tenant_id, row.subject)
        if row.revision != body.expected_revision:
            conflict()
        changes = body.model_dump(
            exclude_unset=True, exclude={"expected_revision", "manage_locally", "managed_provider_id"}
        )
        if row.provider_id:
            from koinon.corporate_profiles.policy import position_fields

            current_mapping = await self.mappings.scoped(tenant_id, row.provider_id)
            if current_mapping and current_mapping.profile_sync_json is not None:
                row.managed_fields = position_fields(current_mapping)
        if set(changes).intersection(row.managed_fields) and not body.manage_locally:
            conflict("This information is managed by the identity provider")
        if body.manage_locally:
            row.provider_id, row.external_subject, row.managed_fields = None, None, []
            row.observed_at, row.observation_status = None, "not_observed"
        if body.managed_provider_id is not None:
            await self.catalog.authorize(actor, tenant_id, "identity:manage")
            provider = await self.mappings.provider(tenant_id, body.managed_provider_id)
            mapping = await self.mappings.scoped(tenant_id, body.managed_provider_id)
            if provider is None or provider.status != "active" or mapping is None or not mapping.enabled:
                denied()
            from koinon.corporate_profiles.policy import position_fields

            managed = position_fields(mapping)
            if not managed and mapping.profile_sync_json is None:
                conflict("Configure organizational profile fields before choosing this provider")
            if set(changes).intersection(managed):
                conflict("Save source ownership separately from managed values")
            row.provider_id, row.external_subject, row.managed_fields = provider.id, None, managed
            row.observed_at, row.observation_status = None, "unavailable"
        await self._links(
            tenant_id, row, changes.get("unit_id", row.unit_id), changes.get("manager_id", row.manager_id)
        )
        for key, value in changes.items():
            setattr(row, key, value)
        if "manager_id" in changes:
            row.pending_manager = False
        row.revision += 1
        row.updated_by, row.updated_at = actor, datetime.now(UTC)
        return await self._saved(actor, tenant_id, row, "organization.person.updated")

    async def _unit_parent(self, tenant_id, identifier, parent_id):
        current = parent_id
        seen = {identifier}
        for _ in range(32):
            if current is None:
                depth = await self.unit_repository.subtree_depth(tenant_id, identifier)
                if len(seen) - 1 + depth > 32:
                    conflict("Organization units exceed the supported depth")
                return
            if current in seen:
                conflict("Organization units cannot contain a cycle")
            seen.add(current)
            current = (await self._unit(tenant_id, current)).parent_id
        conflict("Organization units exceed the supported depth")

    @transactional(read_only=True)
    async def units(self, actor, tenant_id, *, workspace_id=None, parent_id=None, q="", page=1, page_size=25):
        bounds(page, page_size, q=q, parent_id=parent_id)
        scope = await self._scope(actor, tenant_id, workspace_id)
        if parent_id is not None and not await self.unit_repository.visible(
            tenant_id, parent_id, self.catalog.effective_membership_rows(), scope
        ):
            denied()
        rows, total = await self.unit_repository.page(
            tenant_id,
            self.catalog.effective_membership_rows(),
            scope,
            parent_id=parent_id,
            q=q,
            page=page,
            page_size=page_size,
        )
        await self._fresh_units(
            actor,
            tenant_id,
            workspace_id,
            rows,
            total,
            {"parent_id": parent_id, "q": q, "page": page, "page_size": page_size},
        )
        return OrganizationUnitPage(
            items=[unit_view(row, children) for row, children in rows],
            total=total,
            page=page,
            page_size=page_size,
            pages=(total + page_size - 1) // page_size,
        )

    @transactional
    async def create_unit(self, actor, tenant_id, body: OrganizationUnitInput):
        await self._write(actor, tenant_id)
        if body.provider_id:
            await self.catalog.authorize(actor, tenant_id, "identity:manage")
            if await self.mappings.provider(tenant_id, body.provider_id) is None:
                denied()
        row = Unit(
            id=str(uuid4()),
            tenant_id=tenant_id,
            name=body.name,
            kind=body.kind,
            parent_id=body.parent_id,
            provider_id=body.provider_id,
            external_key=body.external_key,
            revision=1,
            updated_by=actor,
        )
        await self._unit_parent(tenant_id, row.id, row.parent_id)
        row = await self.unit_repository.save(row)
        await self.catalog.authorize(actor, tenant_id, "members:write")
        await self.catalog._audit(actor, tenant_id, "organization.unit.created", row.id, {"revision": 1})
        return unit_view(row)

    @transactional
    async def update_unit(self, actor, tenant_id, identifier, body: OrganizationUnitPatch):
        await self._write(actor, tenant_id)
        row = await self._unit(tenant_id, identifier)
        if row.revision != body.expected_revision:
            conflict()
        changes = body.model_dump(exclude_unset=True, exclude={"expected_revision"})
        await self._unit_parent(tenant_id, row.id, changes.get("parent_id", row.parent_id))
        for key, value in changes.items():
            setattr(row, key, value)
        row.revision += 1
        row.updated_by, row.updated_at = actor, datetime.now(UTC)
        row = await self.unit_repository.save(row)
        await self.catalog.authorize(actor, tenant_id, "members:write")
        await self.catalog._audit(
            actor, tenant_id, "organization.unit.updated", row.id, {"revision": row.revision}
        )
        return unit_view(row)

    @transactional
    async def delete_unit(self, actor, tenant_id, identifier, expected_revision):
        await self._write(actor, tenant_id)
        row = await self._unit(tenant_id, identifier)
        if type(expected_revision) is not int or row.revision != expected_revision:
            conflict()
        if await self.unit_repository.occupied(tenant_id, identifier):
            conflict("Reassign people and child units before removing this unit")
        await self.unit_repository.delete(row)
        await self.catalog.authorize(actor, tenant_id, "members:write")
        await self.catalog._audit(actor, tenant_id, "organization.unit.deleted", identifier)

    @transactional(read_only=True)
    async def settings(self, actor, tenant_id):
        await self._membership(actor, tenant_id)
        row = await self.setting_repository.find_by_id(tenant_id)
        await self._fresh_self_output(actor, tenant_id, None, {})
        return OrganizationDirectorySettings(
            tenant_id=tenant_id,
            visibility=row.visibility if row else "administrators",
            revision=row.revision if row else 0,
        )

    @transactional
    async def update_settings(self, actor, tenant_id, body: OrganizationDirectorySettingsInput):
        await self._write(actor, tenant_id)
        row = await self.setting_repository.find_by_id(tenant_id)
        if (row.revision if row else 0) != body.expected_revision:
            conflict()
        row = row or Setting(tenant_id=tenant_id, updated_by=actor)
        row.visibility, row.revision, row.updated_by = body.visibility, body.expected_revision + 1, actor
        row.updated_at = datetime.now(UTC)
        await self.setting_repository.save(row)
        await self.catalog.authorize(actor, tenant_id, "members:write")
        await self.catalog._audit(
            actor, tenant_id, "organization.directory.updated", tenant_id, {"revision": row.revision}
        )
        return OrganizationDirectorySettings(
            tenant_id=tenant_id, visibility=row.visibility, revision=row.revision
        )

    @transactional(read_only=True)
    async def mapping(self, actor, tenant_id, provider_id):
        await self.catalog.authorize(actor, tenant_id, "identity:manage")
        provider = await self.mappings.provider(tenant_id, provider_id)
        if provider is None:
            denied()
        row = await self.mappings.scoped(tenant_id, provider_id)
        await self._fresh_mapping_scope(actor, tenant_id, provider_id)
        from koinon.corporate_profiles.policy import mapping_view

        return mapping_view(tenant_id, provider_id, row, provider)

    @transactional
    async def update_mapping(self, actor, tenant_id, provider_id, body: OrganizationProfileMappingInput):
        await self.catalog.authorize(actor, tenant_id, "identity:manage")
        await self.catalog._lock_tenant(tenant_id)
        await self.catalog.authorize(actor, tenant_id, "identity:manage")
        provider = await self.mappings.provider(tenant_id, provider_id)
        if provider is None:
            denied()
        row = await self.mappings.scoped(tenant_id, provider_id)
        if (row.revision if row else 0) != body.expected_revision:
            conflict()
        row = row or Mapping(tenant_id=tenant_id, provider_id=provider_id, updated_by=actor)
        row.revision, row.enabled, row.fields_json = (
            body.expected_revision + 1,
            body.enabled,
            body.fields.model_dump(),
        )
        row.updated_at, row.updated_by = datetime.now(UTC), actor
        if "profile_sync" in body.model_fields_set:
            row.profile_sync_json = (
                body.profile_sync.model_dump(mode="json") if body.profile_sync is not None else None
            )
        await self.mappings.save(row)

        if self.corporate_profiles is not None:
            await self.corporate_profiles.queue_provider(tenant_id, provider_id)

        await self.catalog.authorize(actor, tenant_id, "identity:manage")
        await self.catalog._audit(
            actor, tenant_id, "organization.profile_mapping.updated", provider_id, {"revision": row.revision}
        )
        await self.catalog.authorize(actor, tenant_id, "identity:manage")
        from koinon.corporate_profiles.policy import mapping_view

        return mapping_view(tenant_id, provider_id, row, provider)

    @transactional
    async def observe_login(self, context, *, observed_at=None):
        from koinon.organization_people.claims import observe_login

        await observe_login(self, context, observed_at=observed_at)
