# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Tenant presentation ownership and verified bindings; no access-grant writes."""

import math
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import TypeAdapter
from pyfly.container import service
from pyfly.data.relational.sqlalchemy import transactional
from pyfly.kernel import ConflictException, DuplicateKeyException
from pyfly.security.context import SecurityContext
from pyfly.security.context_holder import SecurityContextHolder
from sqlalchemy.exc import IntegrityError

from koinon.catalog.service import CatalogService
from koinon.corporate_identity.challenges import policy as identity_policy
from koinon.corporate_identity.dtos import ProviderSettings
from koinon.corporate_identity.policy import verified_identity
from koinon.corporate_profiles.contracts import BindingWrite
from koinon.corporate_profiles.dtos import CorporateProfileRefresh
from koinon.corporate_profiles.entities import CorporateProfileSnapshot as Snapshot
from koinon.corporate_profiles.entities import OrganizationPresentationPreference as Preference
from koinon.corporate_profiles.policy import active_policy, source_fingerprint
from koinon.corporate_profiles.projector import CorporateProfileProjector, denied
from koinon.corporate_profiles.repositories import (
    CorporateProfileRepository,
    OrganizationPresentationPreferenceRepository,
)
from koinon.organization_people.service import OrganizationPeopleService
from koinon.profiles.service import profile_id
from koinon.security.authority import primary_authority
from koinon.security.settings import OidcSettings


def conflict(code="PROFILE_REVISION_CONFLICT"):
    raise ConflictException("Review the current corporate profile settings", code=code)


def bump(value):
    if type(value) is not int or not 0 <= value < 2147483647:
        conflict()
    return value + 1


def mark_conflict(row):
    row.status = "conflict"
    row.worker_id, row.lease_until = None, None
    row.name_available, row.avatar_available = False, False
    row.binding_revision, row.revision = bump(row.binding_revision or 0), bump(row.revision or 0)
    row.updated_at = datetime.now(UTC)


@service(name="corporate_profiles.service")
class CorporateProfileService:
    def __init__(
        self,
        catalog: CatalogService,
        people: OrganizationPeopleService,
        projector: CorporateProfileProjector,
        snapshots: CorporateProfileRepository,
        preferences: OrganizationPresentationPreferenceRepository,
        oidc: OidcSettings | None = None,
    ):
        self.oidc = oidc
        self.catalog, self.people, self.projector = catalog, people, projector
        self.snapshots, self.preferences = snapshots, preferences

    async def _owner(self, actor, tenant_id, workspace_id=None, *, write=False):
        grant = await self.people._membership(actor, tenant_id, workspace_id)
        if grant is not None and not (
            {"profile:write"} if write else {"profile:read", "profile:write"}
        ).intersection(grant.scopes):
            denied()
        context = SecurityContextHolder.get_context()
        attributes: dict[str, Any] = context.attributes if context else {}
        token = attributes.get("koinon_token")
        if token is not None:
            if not isinstance(token, dict) or not token.get("id"):
                denied()
            row = await self.snapshots.current_token(token["id"])
            if (
                row is None
                or row.subject != actor
                or row.tenant_id != tenant_id
                or row.revoked_at is not None
                or row.expires_at <= datetime.now(UTC)
                or row.asset_ids is not None
                or row.workspace_ids is not None
                and workspace_id not in row.workspace_ids
                or not ({"profile:write"} if write else {"profile:read", "profile:write"}).intersection(
                    row.scopes
                )
            ):
                denied()

    @primary_authority()
    async def presentation(self, actor, tenant_id, *, workspace_id=None):
        await self._owner(actor, tenant_id, workspace_id)
        values = await self.projector.batch(actor, tenant_id, {actor}, workspace_id, own=True)
        return values[actor].own(tenant_id, workspace_id)

    @transactional
    async def update_presentation(self, actor, tenant_id, body, *, workspace_id=None):
        await self._owner(actor, tenant_id, workspace_id, write=True)
        await self.catalog._lock_tenant(tenant_id)
        await self._owner(actor, tenant_id, workspace_id, write=True)
        row = await self.preferences.owner(tenant_id, actor, lock=True)
        if (row.revision if row else 0) != body.expected_revision:
            conflict()
        snapshot = await self.snapshots.owner(tenant_id, actor)
        mapping = (
            await self.people.mappings.scoped(tenant_id, snapshot.provider_id)
            if snapshot and snapshot.provider_id
            else None
        )
        selected = active_policy(mapping)
        if (
            selected
            and not selected.allow_personal_overrides
            and any(value == "personal" for value in (body.name_mode, body.avatar_mode))
        ):
            conflict("PROFILE_OVERRIDES_DISABLED")
        row = row or Preference(
            tenant_id=tenant_id,
            subject=actor,
            name_mode="organization",
            avatar_mode="organization",
            revision=0,
        )
        for key in ("name_mode", "avatar_mode"):
            if key in body.model_fields_set:
                setattr(row, key, getattr(body, key))
        row.revision, row.updated_at = bump(row.revision), datetime.now(UTC)
        await self.preferences.save(row)
        await self._owner(actor, tenant_id, workspace_id, write=True)
        await self.catalog._audit(
            actor,
            tenant_id,
            "organization.presentation.updated",
            profile_id(actor),
            {"revision": row.revision},
        )
        values = await self.projector.batch(actor, tenant_id, {actor}, workspace_id, own=True, write=True)
        from koinon.corporate_profiles.mappers import effective

        fresh = values[actor]
        if not (
            fresh.policy.allow_personal_overrides if fresh.policy else fresh.conflict_overrides_allowed
        ) and (row.name_mode == "personal" or row.avatar_mode == "personal"):
            conflict("PROFILE_OVERRIDES_DISABLED")
        # The fresh read cannot see our uncommitted preference. Apply only that
        # value to its current, guarded source projection without another await.
        return effective(
            actor,
            fresh.profile,
            fresh.snapshot,
            row,
            fresh.provider,
            fresh.mapping,
            conflict_enabled=fresh.conflict_enabled,
            conflict_name_required=fresh.conflict_name_required,
            conflict_avatar_required=fresh.conflict_avatar_required,
            conflict_overrides_allowed=fresh.conflict_overrides_allowed,
            current_member=fresh.current_member,
        ).own(tenant_id, workspace_id)

    def _refresh_dto(self, tenant_id, subject, row):
        return CorporateProfileRefresh(
            tenant_id=tenant_id,
            profile_id=profile_id(subject),
            status=row.status if row else "not_bound",
            snapshot_revision=row.revision if row else 0,
            last_synced_at=row.last_success_at if row else None,
            last_attempt_at=row.last_attempt_at if row else None,
        )

    async def _enqueue(self, tenant_id, subject):
        row = await self.snapshots.owner(tenant_id, subject, lock=True)
        if row is None or row.provider_id is None:
            if not await self.snapshots.has_profile_policy(tenant_id, subject):
                return self._refresh_dto(tenant_id, subject, row).model_copy(
                    update={"status": "not_configured"}
                )
            return self._refresh_dto(tenant_id, subject, row)
        mapping = await self.people.mappings.scoped(tenant_id, row.provider_id)
        provider = await self.people.mappings.provider(tenant_id, row.provider_id)
        if active_policy(mapping) is None:
            return self._refresh_dto(tenant_id, subject, row).model_copy(update={"status": "not_configured"})
        if row.status == "conflict":
            return self._refresh_dto(tenant_id, subject, row)
        if provider is None or provider.status != "active":
            return self._refresh_dto(tenant_id, subject, row).model_copy(update={"status": "unavailable"})
        now = datetime.now(UTC)
        if row.lease_until is None or row.lease_until <= now:
            row.status, row.next_due_at = "queued", now
            row.revision = bump(row.revision)
            await self.snapshots.save(row)
        return self._refresh_dto(tenant_id, subject, row)

    @transactional
    async def refresh_self(self, actor, tenant_id, *, workspace_id=None):
        await self._owner(actor, tenant_id, workspace_id, write=True)
        await self.catalog._lock_tenant(tenant_id)
        await self._owner(actor, tenant_id, workspace_id, write=True)
        result = await self._enqueue(tenant_id, actor)
        await self._owner(actor, tenant_id, workspace_id, write=True)
        return result

    @transactional
    async def refresh_person(self, actor, tenant_id, identifier, *, workspace_id=None):
        await self.catalog.authorize(actor, tenant_id, "identity:manage")
        await self.catalog.authorize(actor, tenant_id, "members:write")
        await self.catalog._lock_tenant(tenant_id)
        await self.people._membership(actor, tenant_id, workspace_id)
        person = await self.people.people.scoped(tenant_id, identifier)
        profile = await self.people.profiles.profiles.find_by_id(identifier) if person is None else None
        subject = person.subject if person else profile.subject if profile else None
        if subject is None:
            denied()
        await self.people._member(tenant_id, subject, workspace_id)
        result = await self._enqueue(tenant_id, subject)
        await self.catalog.authorize(actor, tenant_id, "identity:manage")
        await self.catalog.authorize(actor, tenant_id, "members:write")
        await self.people._member(tenant_id, subject, workspace_id)
        return result

    @transactional
    async def observe_login(self, context, *, observed_at=None):
        if (
            not isinstance(context, SecurityContext)
            or not context.is_authenticated
            or context.attributes.get("sub") != context.user_id
            or not isinstance(context.attributes.get("iss"), str)
            or "koinon_token" in context.attributes
            or "koinon_token_id" in context.attributes
        ):
            return
        claims = context.attributes
        grouped = defaultdict(list)
        for mapping, provider in await self.people.mappings.active(
            claims["iss"], claims.get("koinon_identity_provider")
        ):
            try:
                if active_policy(mapping) is not None:
                    grouped[provider.tenant_id].append(
                        (mapping, provider, verified_identity(identity_policy(provider, self.oidc), claims))
                    )
            except Exception:
                continue
        for tenant_id, candidates in sorted(grouped.items()):
            subject = claims["iss"] + "|" + claims["sub"]
            await self.catalog._lock_tenant(tenant_id)
            if not await self.people.people.member(
                self.catalog.effective_membership_rows(), tenant_id, subject
            ):
                continue
            row = await self.snapshots.owner(tenant_id, subject, lock=True)
            if observed_at is not None and row is not None and row.verified_at >= observed_at:
                continue
            position = await self.people.people.by_subject(tenant_id, subject)
            owner_provider = (
                position.provider_id
                if position and position.provider_id
                else row.provider_id
                if row
                else None
            )
            old_mapping = (
                await self.people.mappings.scoped(tenant_id, owner_provider) if owner_provider else None
            )
            if owner_provider and (
                position and position.provider_id or active_policy(old_mapping) is not None
            ):
                candidates = [item for item in candidates if item[1].id == owner_provider]
            if len(candidates) != 1:
                row = row or Snapshot(
                    id=str(uuid4()),
                    tenant_id=tenant_id,
                    subject=subject,
                    provider_id=None,
                    external_subject=None,
                    source_fingerprint="",
                    binding_revision=0,
                )
                mark_conflict(row)
                await self.snapshots.save(row)
                continue
            mapping, provider, identity = candidates[0]
            fresh = await self.people.mappings.provider(tenant_id, provider.id)
            current = await self.people.mappings.scoped(tenant_id, provider.id)
            if (
                fresh is None
                or fresh.status != "active"
                or fresh.revision != provider.revision
                or current is None
                or current.revision != mapping.revision
                or active_policy(current) is None
            ):
                continue
            identity = verified_identity(identity_policy(fresh, self.oidc), claims)
            settings = TypeAdapter(ProviderSettings).validate_python(fresh.settings_json)
            collision = await self.snapshots.external_owner(
                tenant_id, fresh.id, identity.external_subject, subject
            )
            if collision is not None:
                row = row or Snapshot(
                    id=str(uuid4()),
                    tenant_id=tenant_id,
                    subject=subject,
                    provider_id=None,
                    external_subject=None,
                    source_fingerprint="",
                    binding_revision=0,
                    revision=0,
                )
                mark_conflict(row)
                await self.snapshots.save(row)
                continue
            row = row or Snapshot(
                id=str(uuid4()), tenant_id=tenant_id, subject=subject, binding_revision=0, revision=0
            )
            try:
                value = BindingWrite(
                    fresh.id,
                    identity.external_subject,
                    source_fingerprint(fresh, settings),
                    claims.get("koinon_google_hd") if fresh.kind == "google_workspace" else None,
                    claims.get("koinon_external_tid") if fresh.kind == "entra" else None,
                    bump(row.binding_revision),
                    bump(row.revision),
                    observed_at or datetime.now(UTC),
                )
                await self.snapshots.bind(row, value)
            except (DuplicateKeyException, IntegrityError):
                row = await self.snapshots.owner(tenant_id, subject, lock=True)
                row = row or Snapshot(
                    id=str(uuid4()),
                    tenant_id=tenant_id,
                    subject=subject,
                    provider_id=None,
                    external_subject=None,
                    source_fingerprint="",
                    binding_revision=0,
                    revision=0,
                )
                mark_conflict(row)
                await self.snapshots.save(row)

    async def observe_bearer(self, context):
        if (
            not isinstance(context, SecurityContext)
            or not context.is_authenticated
            or "koinon_token" in context.attributes
            or "koinon_token_id" in context.attributes
        ):
            return
        attributes: dict[str, Any] = context.attributes
        issued = attributes.get("iat")
        if not isinstance(issued, (int, float)) or isinstance(issued, bool):
            return
        if not math.isfinite(issued) or issued < 0 or issued > datetime.now(UTC).timestamp() + 30:
            return
        evidence = datetime.fromtimestamp(issued, UTC)
        await self.observe_login(context, observed_at=evidence)
        await self.people.observe_login(context, observed_at=evidence)
