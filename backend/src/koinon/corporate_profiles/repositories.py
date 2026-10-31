# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime, timedelta

from pyfly.container import repository
from pyfly.data.relational.sqlalchemy import Repository
from sqlalchemy import and_, exists, func, or_, select, update

from koinon.corporate_identity.entities import CorporateProvider
from koinon.corporate_profiles.contracts import BindingWrite, ProfileTicket
from koinon.corporate_profiles.entities import CorporateProfileSnapshot as Snapshot
from koinon.corporate_profiles.entities import OrganizationPresentationPreference as Preference
from koinon.organization_people.entities import OrganizationPersonRecord as Person
from koinon.organization_people.entities import OrganizationProfileMappingRecord as Mapping
from koinon.organization_people.entities import OrganizationUnitRecord as Unit
from koinon.organization_people.repositories import subjects
from koinon.tokens.entities import PersonalToken


@repository
class CorporateProfileRepository(Repository[Snapshot, str]):
    async def owner(self, tenant_id, subject, *, lock=False):
        statement = select(Snapshot).where(Snapshot.tenant_id == tenant_id, Snapshot.subject == subject)
        if lock:
            statement = statement.with_for_update()
        return await self._require_session().scalar(statement.execution_options(populate_existing=True))

    async def queue_provider(self, tenant_id, provider_id):
        await self._require_session().execute(
            update(Snapshot)
            .where(Snapshot.tenant_id == tenant_id, Snapshot.provider_id == provider_id)
            .values(next_due_at=datetime.now(UTC))
        )

    async def claim_due(self, worker_id, limit=25, lease_seconds=120):
        now = datetime.now(UTC)
        rows = (
            await self._require_session().scalars(
                select(Snapshot)
                .join(CorporateProvider, CorporateProvider.id == Snapshot.provider_id)
                .join(
                    Mapping,
                    (Mapping.tenant_id == Snapshot.tenant_id) & (Mapping.provider_id == Snapshot.provider_id),
                )
                .where(
                    CorporateProvider.status == "active",
                    Mapping.enabled.is_(True),
                    Mapping.profile_sync_json.is_not(None),
                    Snapshot.external_subject.is_not(None),
                    Snapshot.status != "conflict",
                    Snapshot.next_due_at <= now,
                    or_(Snapshot.lease_until.is_(None), Snapshot.lease_until <= now),
                )
                .order_by(Snapshot.next_due_at, Snapshot.id)
                .limit(limit)
                .with_for_update(skip_locked=True, of=Snapshot)
            )
        ).all()
        for row in rows:
            row.worker_id, row.lease_until = worker_id, now + timedelta(seconds=lease_seconds)
            row.lease_generation += 1
            row.status, row.last_attempt_at = "running", now
        await self._require_session().flush()
        return rows

    async def has_profile_policy(self, tenant_id, subject):
        issuer = subject.partition("|")[0]
        return bool(
            await self._require_session().scalar(
                select(
                    exists(
                        select(Mapping.tenant_id)
                        .join(
                            CorporateProvider,
                            and_(
                                CorporateProvider.id == Mapping.provider_id,
                                CorporateProvider.tenant_id == Mapping.tenant_id,
                            ),
                        )
                        .where(
                            Mapping.tenant_id == tenant_id,
                            Mapping.enabled.is_(True),
                            Mapping.profile_sync_json.is_not(None),
                            CorporateProvider.canonical_issuer == issuer,
                        )
                    )
                )
            )
        )

    async def current_token(self, identifier):
        return await self._require_session().scalar(
            select(PersonalToken)
            .where(PersonalToken.id == identifier)
            .with_for_update(read=True)
            .execution_options(populate_existing=True)
        )

    async def external_owner(self, tenant_id, provider_id, external_subject, except_subject):
        return await self._require_session().scalar(
            select(Snapshot.id).where(
                Snapshot.tenant_id == tenant_id,
                Snapshot.provider_id == provider_id,
                Snapshot.external_subject == external_subject,
                Snapshot.subject != except_subject,
            )
        )

    async def external_unit(self, tenant_id, provider_id, external_key):
        return await self._require_session().scalar(
            select(Unit).where(
                Unit.tenant_id == tenant_id,
                Unit.provider_id == provider_id,
                Unit.external_key == external_key,
            )
        )

    async def external_people(self, tenant_id, provider_id, external_subject):
        return list(
            (
                await self._require_session().scalars(
                    select(Person)
                    .where(
                        Person.tenant_id == tenant_id,
                        Person.provider_id == provider_id,
                        Person.external_subject == external_subject,
                    )
                    .limit(2)
                )
            ).all()
        )

    async def bind(self, row: Snapshot, value: BindingWrite):
        async with self._require_session().begin_nested():
            if (
                row.provider_id != value.provider_id
                or row.external_subject != value.external_subject
                or row.source_fingerprint != value.fingerprint
            ):
                row.name_available, row.avatar_available = False, False
                row.provider_revision, row.mapping_revision = 0, 0
                row.fields_json = []
                row.last_success_at, row.last_attempt_at, row.claims_observed_at = None, None, None
            row.provider_id, row.external_subject = value.provider_id, value.external_subject
            row.source_fingerprint = value.fingerprint
            row.verified_domain, row.verified_external_tenant = (
                value.verified_domain,
                value.verified_external_tenant,
            )
            row.binding_revision, row.revision = value.binding_revision, value.revision
            row.verified_at, row.next_due_at = value.observed_at, value.observed_at
            row.status = "queued"
            await self.save(row)

    async def current_observation(self, ticket: ProfileTicket, position_revision: int, members) -> bool:
        member = exists(
            subjects(members, ticket.lease.tenant_id, None).where(members.c.subject == ticket.subject)
        )
        eligible = (
            select(Snapshot.id)
            .join(CorporateProvider, CorporateProvider.id == Snapshot.provider_id)
            .join(
                Mapping,
                and_(Mapping.tenant_id == Snapshot.tenant_id, Mapping.provider_id == Snapshot.provider_id),
            )
            .outerjoin(
                Preference,
                and_(Preference.tenant_id == Snapshot.tenant_id, Preference.subject == Snapshot.subject),
            )
            .outerjoin(
                Person, and_(Person.tenant_id == Snapshot.tenant_id, Person.subject == Snapshot.subject)
            )
            .where(
                Snapshot.id == ticket.lease.id,
                Snapshot.tenant_id == ticket.lease.tenant_id,
                Snapshot.binding_revision == ticket.binding_revision,
                Snapshot.external_subject == ticket.external_subject,
                Snapshot.worker_id == ticket.lease.worker_id,
                Snapshot.lease_generation == ticket.lease.generation,
                Snapshot.lease_until > datetime.now(UTC),
                CorporateProvider.status == "active",
                CorporateProvider.revision == ticket.provider_revision,
                Mapping.enabled.is_(True),
                Mapping.profile_sync_json.is_not(None),
                Mapping.revision == ticket.mapping_revision,
                func.coalesce(Preference.revision, 0) == ticket.preference_revision,
                func.coalesce(Person.revision, 0) == position_revision,
                member,
            )
        )
        result = await self._require_session().execute(
            update(Snapshot)
            .where(Snapshot.id.in_(eligible.correlate(None)))
            .values(worker_id=None, lease_until=None)
            .returning(Snapshot.id)
            .execution_options(synchronize_session=False)
        )
        return result.scalar_one_or_none() is not None


@repository
class OrganizationPresentationPreferenceRepository(Repository[Preference, tuple[str, str]]):
    async def owner(self, tenant_id, subject, *, lock=False):
        statement = select(Preference).where(Preference.tenant_id == tenant_id, Preference.subject == subject)
        if lock:
            statement = statement.with_for_update()
        return await self._require_session().scalar(statement.execution_options(populate_existing=True))
