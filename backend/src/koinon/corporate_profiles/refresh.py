# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Leased observations: network/image work is outside every primary write unit."""

import asyncio
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import uuid4

from pydantic import TypeAdapter
from pyfly.container import service
from pyfly.data.relational.sqlalchemy import LockMode, transactional

from koinon.catalog.service import CatalogService
from koinon.corporate_identity.dtos import ProviderSettings
from koinon.corporate_identity.settings import IdentityCredentialStore
from koinon.corporate_profiles.contracts import ProfileLease, ProfileTicket, facts, owns
from koinon.corporate_profiles.directory import CorporateProfileDirectory
from koinon.corporate_profiles.normalization import (
    DirectoryProfileObservation,
    FieldObservation,
    ProfileObservationError,
)
from koinon.corporate_profiles.policy import active_policy, source_fingerprint
from koinon.corporate_profiles.repositories import (
    CorporateProfileRepository,
    OrganizationPresentationPreferenceRepository,
)
from koinon.corporate_profiles.service import bump
from koinon.organization_people.entities import OrganizationPersonRecord as Person
from koinon.organization_people.service import OrganizationPeopleService
from koinon.profiles.images import sanitize_avatar


@service(name="corporate_profiles.refresher")
class CorporateProfileRefresher:
    def __init__(
        self,
        catalog: CatalogService,
        people: OrganizationPeopleService,
        snapshots: CorporateProfileRepository,
        preferences: OrganizationPresentationPreferenceRepository,
        directory: CorporateProfileDirectory,
        credentials: IdentityCredentialStore,
    ):
        self.catalog, self.people, self.snapshots, self.preferences = catalog, people, snapshots, preferences
        self.directory, self.credentials = directory, credentials
        self._images = asyncio.Semaphore(2)

    @transactional
    async def claim(self, worker_id, *, limit=2):
        if (
            not isinstance(worker_id, str)
            or not 1 <= len(worker_id) <= 64
            or type(limit) is not int
            or not 1 <= limit <= 2
        ):
            raise ValueError("Use a bounded corporate profile lease request")
        rows = await self.snapshots.claim_due(worker_id, limit=limit, lease_seconds=120)
        return [ProfileLease(row.id, row.tenant_id, worker_id, row.lease_generation) for row in rows]

    @transactional(read_only=True)
    async def prepare(self, lease):
        row = await self.snapshots.find_by_id(lease.id)
        if not owns(row, lease) or row.provider_id is None or row.external_subject is None:
            return None
        provider = await self.people.mappings.provider(row.tenant_id, row.provider_id)
        mapping = await self.people.mappings.scoped(row.tenant_id, row.provider_id)
        policy = active_policy(mapping)
        if provider is None or provider.status != "active" or policy is None:
            raise ProfileObservationError("PROFILE_CONNECTION_CHANGED")
        settings = TypeAdapter(ProviderSettings).validate_python(provider.settings_json)
        if (
            row.source_fingerprint != source_fingerprint(provider, settings)
            or provider.canonical_issuer != row.subject.split("|", 1)[0]
        ):
            raise ProfileObservationError("PROFILE_BINDING_CHANGED")
        if not await self.people.people.member(
            self.catalog.effective_membership_rows(), row.tenant_id, row.subject
        ):
            raise ProfileObservationError("PROFILE_MEMBERSHIP_UNAVAILABLE")
        preference = await self.preferences.owner(row.tenant_id, row.subject)
        person = await self.people.people.by_subject(row.tenant_id, row.subject)
        return ProfileTicket(
            lease,
            row.subject,
            row.provider_id,
            row.external_subject,
            row.binding_revision,
            provider.revision,
            mapping.revision,
            preference.revision if preference else 0,
            facts(person),
            row.source_fingerprint,
            policy,
            settings,
            provider.secret_ciphertext,
        )

    async def execute(self, lease):
        try:
            ticket = await self.prepare(lease)
            if ticket is None:
                return False
            sources = (
                ticket.policy.name_source,
                ticket.policy.avatar_source,
                ticket.policy.job_title_source,
                ticket.policy.unit_source,
                ticket.policy.manager_source,
            )
            if "directory" in sources:
                credential = (
                    self.credentials.decrypt(lease.tenant_id, ticket.provider_id, ticket.ciphertext)
                    if ticket.ciphertext
                    else None
                )
                observation = await self.directory.observe(
                    ticket.settings, credential, ticket.policy, ticket.external_subject
                )
            else:
                observation = DirectoryProfileObservation(ticket.external_subject)
            photo = observation.fields.get("avatar")
            if photo and photo.status == "current":
                try:
                    if not isinstance(photo.value, bytes):
                        raise ValueError("Corporate photo must be bounded image bytes")
                    async with self._images:
                        image = await asyncio.to_thread(sanitize_avatar, photo.value)
                    observation.fields["avatar"] = FieldObservation("current", image)
                except ValueError:
                    observation.fields["avatar"] = FieldObservation(
                        "unavailable", code="PROFILE_PHOTO_INVALID"
                    )
            return await self.commit(ticket, observation)
        except ProfileObservationError as error:
            await self.failed(lease, error.code)
        except Exception:
            await self.failed(lease, "PROFILE_REFRESH_UNAVAILABLE")
        return False

    async def _position(self, ticket, observation, person):
        policy = ticket.policy
        targets = {
            "job_title": policy.job_title_source,
            "unit_id": policy.unit_source,
            "manager_id": policy.manager_source,
        }
        if person is not None and person.provider_id != ticket.provider_id:
            return person
        ready = any(
            observation.fields.get(field) and observation.fields[field].status in {"current", "empty"}
            for field, source in (
                ("job_title", policy.job_title_source),
                ("department", policy.unit_source),
                ("manager", policy.manager_source),
            )
            if source == "directory"
        )
        if person is None and not ready:
            return None
        person = person or Person(
            id=str(uuid4()),
            tenant_id=ticket.lease.tenant_id,
            subject=ticket.subject,
            provider_id=ticket.provider_id,
            external_subject=ticket.external_subject,
            revision=0,
            managed_fields=[],
            pending_manager=False,
            observation_status="not_observed",
            updated_by=ticket.subject,
        )
        changes = {}
        title = observation.fields.get("job_title")
        if policy.job_title_source == "directory" and title and title.status in {"current", "empty"}:
            changes["job_title"] = title.value
        department = observation.fields.get("department")
        if policy.unit_source == "directory" and department:
            if department.status == "empty":
                changes["unit_id"] = None
            elif department.status == "current":
                unit = await self.snapshots.external_unit(
                    ticket.lease.tenant_id, ticket.provider_id, department.value
                )
                if unit is not None:
                    changes["unit_id"] = unit.id
                else:
                    observation.fields["department"] = FieldObservation(
                        "unavailable", department.value, "PROFILE_UNIT_UNMAPPED"
                    )
        manager = observation.fields.get("manager")
        if policy.manager_source == "directory" and manager:
            if manager.status == "empty":
                changes["manager_id"], person.pending_manager = None, False
            elif manager.status == "current":
                candidates = await self.snapshots.external_people(
                    ticket.lease.tenant_id, ticket.provider_id, manager.value
                )
                candidate = candidates[0] if len(candidates) == 1 else None
                if candidate is not None and await self.people.people.member(
                    self.catalog.effective_membership_rows(), ticket.lease.tenant_id, candidate.subject
                ):
                    changes["manager_id"], person.pending_manager = candidate.id, False
                else:
                    changes["manager_id"], person.pending_manager = None, True
                    observation.fields["manager"] = FieldObservation(
                        "unavailable", code="PROFILE_MANAGER_UNRESOLVED"
                    )
            elif manager.status in {"unsupported", "unavailable"}:
                person.pending_manager = True
        try:
            await self.people._links(
                ticket.lease.tenant_id,
                person,
                changes.get("unit_id", person.unit_id),
                changes.get("manager_id", person.manager_id),
            )
        except Exception:
            changes.pop("unit_id", None)
            changes.pop("manager_id", None)
            person.pending_manager = True
            observation.fields["manager"] = FieldObservation("unavailable", code="PROFILE_HIERARCHY_INVALID")
        for key, value in changes.items():
            setattr(person, key, value)
        person.external_subject = ticket.external_subject
        person.managed_fields = sorted({key for key, source in targets.items() if source != "local"})
        person.revision, person.updated_at, person.observed_at = (
            bump(person.revision),
            datetime.now(UTC),
            datetime.now(UTC),
        )
        person.updated_by = ticket.subject
        person.observation_status = (
            "current"
            if all(
                value.status not in {"unavailable", "unsupported"} for value in observation.fields.values()
            )
            else "unavailable"
        )
        await self.people.people.save(person)
        return person

    @transactional
    async def commit(self, ticket, observation):
        lease = ticket.lease
        await self.catalog._lock_tenant(lease.tenant_id)
        row = await self.snapshots.find_by_id(lease.id, lock=LockMode.PESSIMISTIC_WRITE)
        if not owns(row, lease):
            return False
        provider = await self.people.mappings.provider(lease.tenant_id, ticket.provider_id)
        mapping = await self.people.mappings.scoped(lease.tenant_id, ticket.provider_id)
        preference = await self.preferences.owner(lease.tenant_id, ticket.subject)
        person = await self.people.people.by_subject(lease.tenant_id, ticket.subject)
        valid = (
            provider is not None
            and provider.status == "active"
            and provider.revision == ticket.provider_revision
            and mapping is not None
            and mapping.revision == ticket.mapping_revision
            and active_policy(mapping) is not None
            and row.binding_revision == ticket.binding_revision
            and row.provider_id == ticket.provider_id
            and row.external_subject == ticket.external_subject
            and row.source_fingerprint == ticket.fingerprint
            and (preference.revision if preference else 0) == ticket.preference_revision
            and facts(person) == ticket.position_facts
            and observation.external_subject == ticket.external_subject
        )
        if not valid or not await self.people.people.member(
            self.catalog.effective_membership_rows(), lease.tenant_id, ticket.subject
        ):
            row.worker_id, row.lease_until, row.next_due_at = (
                None,
                None,
                datetime.now(UTC) + timedelta(seconds=300),
            )
            row.status = "queued" if valid else "stale"
            await self.snapshots.save(row)
            return False
        if source_fingerprint(provider, ticket.settings) != ticket.fingerprint:
            raise ProfileObservationError("PROFILE_BINDING_CHANGED")
        now = datetime.now(UTC)
        department = observation.fields.get("department")
        if department and department.status in {"current", "empty"}:
            row.department = department.value
        person = await self._position(ticket, observation, person)
        name = observation.fields.get("display_name")
        if name and ticket.policy.name_source == "directory":
            if name.status in {"current", "empty"}:
                row.display_name, row.name_available = name.value, True
            elif name.status != "not_observed":
                row.name_available = False
        photo = observation.fields.get("avatar")
        if photo and ticket.policy.avatar_source == "directory":
            if photo.status in {"current", "empty"}:
                row.avatar_bytes, row.avatar_available = photo.value, True
                row.avatar_version = sha256(photo.value).hexdigest() if photo.value else None
            elif photo.status != "not_observed":
                row.avatar_available = False
        previous = {item["field"]: item for item in row.fields_json}
        sources = {
            "display_name": "directory" if ticket.policy.name_source == "directory" else "personal",
            "avatar": "directory" if ticket.policy.avatar_source == "directory" else "personal",
            "job_title": ticket.policy.job_title_source,
            "department": ticket.policy.unit_source,
            "manager": ticket.policy.manager_source,
        }
        records = []
        for target, source in sources.items():
            value = observation.fields.get(target, FieldObservation("not_observed"))
            if source == "verified_claims":
                records.append(
                    previous.get(
                        target,
                        {
                            "field": target,
                            "source": source,
                            "status": "not_observed",
                            "observed_at": None,
                            "code": None,
                        },
                    )
                )
            else:
                status = value.status if source == "directory" else "current"
                records.append(
                    {
                        "field": target,
                        "source": source,
                        "status": status,
                        "observed_at": now.isoformat()
                        if source == "directory" and status in {"current", "empty"}
                        else previous.get(target, {}).get("observed_at"),
                        "code": value.code if source == "directory" else None,
                    }
                )
        row.fields_json = records
        row.status = "current" if all(item["status"] in {"current", "empty"} for item in records) else "stale"
        if any(value.status in {"current", "empty"} for value in observation.fields.values()):
            row.last_success_at = now
        row.last_attempt_at, row.updated_at = now, now
        row.provider_revision, row.mapping_revision = ticket.provider_revision, ticket.mapping_revision
        row.revision = bump(row.revision)
        row.next_due_at = now + timedelta(seconds=ticket.policy.interval_seconds)
        await self.snapshots.save(row)
        await self.catalog._audit(
            ticket.subject,
            lease.tenant_id,
            "identity.profile.observed",
            row.id,
            {"provider_id": ticket.provider_id, "revision": row.revision, "status": row.status},
        )
        if not await self.snapshots.current_observation(
            ticket, person.revision if person else 0, self.catalog.effective_membership_rows()
        ):
            raise ProfileObservationError("PROFILE_SCOPE_CHANGED")
        return True

    @transactional
    async def failed(self, lease, code):
        await self.catalog._lock_tenant(lease.tenant_id)
        row = await self.snapshots.find_by_id(lease.id, lock=LockMode.PESSIMISTIC_WRITE)
        if not owns(row, lease):
            return
        row.status = "conflict" if code == "PROFILE_BINDING_CHANGED" else "unavailable"
        row.worker_id, row.lease_until = None, None
        row.next_due_at = datetime.now(UTC) + timedelta(seconds=900)
        row.last_attempt_at, row.updated_at = datetime.now(UTC), datetime.now(UTC)
        if code in {
            "PROFILE_PERMISSION_DENIED",
            "PROFILE_ACCOUNT_UNAVAILABLE",
            "PROFILE_USER_UNAVAILABLE",
            "PROFILE_IDENTITY_MISMATCH",
            "PROFILE_BINDING_CHANGED",
        }:
            row.name_available, row.avatar_available = False, False
        row.fields_json = [
            {
                **item,
                "status": "unavailable" if not row.name_available and not row.avatar_available else "stale",
                "code": code,
            }
            if item.get("source") == "directory"
            else item
            for item in row.fields_json
        ]
        row.revision = bump(row.revision)
        await self.snapshots.save(row)
