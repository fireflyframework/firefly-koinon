# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""One fresh native query binds presentation to current authority and page facts."""

from datetime import UTC, datetime

from pyfly.container import repository
from pyfly.data.relational.sqlalchemy import Repository
from sqlalchemy import and_, case, exists, func, literal, or_, select
from sqlalchemy.orm import aliased

from koinon.corporate_identity.entities import CorporateProvider
from koinon.corporate_profiles.entities import CorporateProfileSnapshot as Snapshot
from koinon.corporate_profiles.entities import OrganizationPresentationPreference as Preference
from koinon.corporate_profiles.read_models import PresentationRead, PresentationRecord
from koinon.organization_people.entities import OrganizationDirectorySettingRecord as Setting
from koinon.organization_people.entities import OrganizationPersonRecord as Person
from koinon.organization_people.entities import OrganizationProfileMappingRecord as Mapping
from koinon.organization_people.entities import OrganizationUnitRecord as Unit
from koinon.organization_people.repositories import subjects
from koinon.profiles.entities import Profile
from koinon.tokens.entities import PersonalToken


@repository(name="corporate_profiles.presentation_repository")
class CorporatePresentationRepository(Repository[Snapshot, str]):
    async def read(self, request: PresentationRead, members) -> list[PresentationRecord]:
        actor, tenant_id, wanted, workspace_id = (
            request.actor,
            request.tenant_id,
            request.wanted,
            request.workspace_id,
        )
        own, authors = request.own, request.authors
        count_query, expected_total = request.count_query, request.expected_total
        page_query, page_subjects = request.page_query, request.page_subjects
        people, units, unassigned = request.people, request.units, request.unassigned
        token_id = request.token_id
        actor_rows = subjects(members, tenant_id, workspace_id).where(members.c.subject == actor)
        if authors:
            actor_rows = select(members.c.subject).where(
                members.c.tenant_id == tenant_id,
                members.c.subject == actor,
                members.c.active.is_(True),
                members.c.role.in_(request.author_roles),
            )
            if workspace_id is not None:
                actor_rows = actor_rows.where(
                    or_(members.c.workspace_id.is_(None), members.c.workspace_id == workspace_id)
                )
        actor_member = exists(actor_rows)
        admin = exists(
            select(members.c.subject).where(
                members.c.tenant_id == tenant_id,
                members.c.subject == actor,
                members.c.active.is_(True),
                members.c.workspace_id.is_(None),
                members.c.role == "admin",
            )
        )
        sharing = exists(
            select(Setting.tenant_id).where(
                Setting.tenant_id == tenant_id, Setting.visibility == "shared_workspaces"
            )
        )
        access = (
            actor_member
            if own or authors
            else or_(admin, and_(literal(workspace_id is not None), sharing, actor_member))
        )
        checks = [access]
        if count_query is not None:
            checks.append(
                select(func.count()).select_from(count_query.order_by(None).subquery()).scalar_subquery()
                == expected_total
            )
        if page_query is not None:
            selected = page_query.subquery("presentation_selected_page")
            checks.append(
                select(func.count())
                .select_from(selected)
                .where(selected.c.subject.in_(page_subjects))
                .scalar_subquery()
                == len(page_subjects)
            )
        if unassigned:
            checks.append(
                ~exists(
                    select(Person.id).where(Person.tenant_id == tenant_id, Person.subject.in_(unassigned))
                )
            )
        assigned = {row.id: row.revision for row in people if row is not None}
        if assigned:
            checks.append(
                select(func.count())
                .select_from(Person)
                .where(
                    Person.tenant_id == tenant_id,
                    Person.id.in_(assigned),
                    Person.revision == case(assigned, value=Person.id),
                )
                .scalar_subquery()
                == len(assigned)
            )
        revisions = {row.id: row.revision for row in units}
        if revisions:
            checks.append(
                select(func.count())
                .select_from(Unit)
                .where(
                    Unit.tenant_id == tenant_id,
                    Unit.id.in_(revisions),
                    Unit.revision == case(revisions, value=Unit.id),
                )
                .scalar_subquery()
                == len(revisions)
            )
        if token_id:
            checks.append(
                exists(
                    select(PersonalToken.id).where(
                        PersonalToken.id == token_id,
                        PersonalToken.subject == actor,
                        PersonalToken.tenant_id == tenant_id,
                        PersonalToken.revoked_at.is_(None),
                        PersonalToken.expires_at > datetime.now(UTC),
                    )
                )
            )
        policy_mapping, policy_provider = aliased(Mapping), aliased(CorporateProvider)
        applicable = (
            select(policy_mapping.tenant_id)
            .join(
                policy_provider,
                and_(
                    policy_provider.id == policy_mapping.provider_id,
                    policy_provider.tenant_id == policy_mapping.tenant_id,
                ),
            )
            .where(
                policy_mapping.tenant_id == tenant_id,
                policy_mapping.enabled.is_(True),
                policy_mapping.profile_sync_json.is_not(None),
                func.substr(Snapshot.subject, 1, func.length(policy_provider.canonical_issuer) + 1)
                == policy_provider.canonical_issuer + "|",
            )
        )
        active_policy = exists(applicable)
        allowed = func.coalesce(
            policy_mapping.profile_sync_json["allow_personal_overrides"].as_boolean(), True
        )
        name_required = exists(
            applicable.where(
                policy_mapping.profile_sync_json["name_source"].as_string() == "directory",
            )
        )
        avatar_required = exists(
            applicable.where(
                policy_mapping.profile_sync_json["avatar_source"].as_string() == "directory",
            )
        )
        overrides_allowed = ~exists(applicable.where(allowed.is_(False)))
        if authors:
            visible = (
                select(Profile.subject)
                .where(Profile.subject.in_(wanted))
                .union(
                    select(Snapshot.subject).where(
                        Snapshot.tenant_id == tenant_id, Snapshot.subject.in_(wanted)
                    ),
                    select(Person.subject).where(Person.tenant_id == tenant_id, Person.subject.in_(wanted)),
                    select(members.c.subject).where(
                        members.c.tenant_id == tenant_id,
                        members.c.subject.in_(wanted),
                        members.c.active.is_(True),
                    ),
                )
                .subquery("admitted_authors")
            )
            anchor = select(literal(1).label("one")).subquery("presentation_authors_gate")
            source = anchor.outerjoin(visible, literal(True))
        else:
            visible = (
                subjects(members, tenant_id, workspace_id)
                .where(members.c.subject.in_(wanted))
                .subquery("presentation_people")
            )
            source = visible
        current_member = exists(
            select(members.c.subject).where(
                members.c.tenant_id == tenant_id,
                members.c.subject == visible.c.subject,
                members.c.active.is_(True),
            )
        )
        position = aliased(Person)
        provider_id = func.coalesce(Snapshot.provider_id, position.provider_id)
        query = (
            select(
                visible.c.subject,
                Profile,
                Snapshot,
                Preference,
                CorporateProvider,
                Mapping,
                PersonalToken,
                active_policy,
                name_required,
                avatar_required,
                overrides_allowed,
                current_member,
            )
            .select_from(source)
            .outerjoin(Profile, Profile.subject == visible.c.subject)
            .outerjoin(position, and_(position.tenant_id == tenant_id, position.subject == visible.c.subject))
            .outerjoin(Snapshot, and_(Snapshot.tenant_id == tenant_id, Snapshot.subject == visible.c.subject))
            .outerjoin(
                Preference, and_(Preference.tenant_id == tenant_id, Preference.subject == visible.c.subject)
            )
            .outerjoin(
                CorporateProvider,
                and_(CorporateProvider.tenant_id == tenant_id, CorporateProvider.id == provider_id),
            )
            .outerjoin(Mapping, and_(Mapping.tenant_id == tenant_id, Mapping.provider_id == provider_id))
            .outerjoin(PersonalToken, PersonalToken.id == token_id)
            .where(*checks)
        )
        if own:
            query = query.where(
                or_(
                    visible.c.subject == actor,
                    or_(admin, and_(literal(workspace_id is not None), sharing, actor_member)),
                )
            )
        session = self._require_session()
        if not wanted:
            anchor = select(literal(1).label("one")).subquery("presentation_gate")
            gate = (
                select(anchor.c.one, PersonalToken)
                .select_from(anchor)
                .outerjoin(PersonalToken, PersonalToken.id == token_id)
                .where(*checks)
            )
            row = (await session.execute(gate)).first()
            return (
                [
                    PresentationRecord(
                        None, None, None, None, None, None, row[1], False, False, False, True, True
                    )
                ]
                if row
                else []
            )
        rows = (await session.execute(query.execution_options(populate_existing=True))).all()
        return [PresentationRecord(*row) for row in rows]
