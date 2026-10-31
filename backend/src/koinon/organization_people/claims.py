# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Fixed presentation fields from already verified login claims. No remote operations."""

from collections import defaultdict
from datetime import UTC, datetime
from uuid import uuid4

from pydantic import ValidationError
from pyfly.security.context import SecurityContext

from koinon.corporate_identity.challenges import policy
from koinon.corporate_identity.policy import verified_identity
from koinon.organization_people.dtos import OrganizationPersonPatch, OrganizationProfileFields
from koinon.organization_people.entities import OrganizationPersonRecord as Person


async def observe_login(service, context, *, observed_at=None):
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
    candidates = await service.mappings.active(claims["iss"], claims.get("koinon_identity_provider"))
    if len(candidates) > 100:
        return
    for mapping, provider in candidates:
        grouped[provider.tenant_id].append((mapping, provider))
    for tenant_id in sorted(grouped):
        # Ambiguous sources never win by iteration order.
        if len(grouped[tenant_id]) != 1:
            continue
        mapping, provider = grouped[tenant_id][0]
        try:
            identity = verified_identity(policy(provider), claims)
        except Exception:
            continue
        expected_revision = mapping.revision
        await service.catalog._lock_tenant(tenant_id)
        current = await service.mappings.scoped(tenant_id, provider.id)
        fresh = await service.mappings.provider(tenant_id, provider.id)
        if (
            current is None
            or not current.enabled
            or current.revision != expected_revision
            or fresh is None
            or fresh.status != "active"
        ):
            continue
        try:
            identity = verified_identity(policy(fresh), claims)
        except Exception:
            continue
        if not await service.people.member(
            service.catalog.effective_membership_rows(), tenant_id, identity.subject
        ):
            continue
        row = await service.people.by_subject(tenant_id, identity.subject)
        if row is not None and row.provider_id != provider.id:
            continue
        fields = OrganizationProfileFields.model_validate(current.fields_json)
        selected = {key: value for key, value in fields.model_dump().items() if value is not None}
        from koinon.corporate_profiles.policy import active_policy

        sync = active_policy(current)
        targets = {
            "job_title": "job_title_source",
            "unit_external_key": "unit_source",
            "manager_external_subject": "manager_source",
        }
        snapshot = None
        if sync is not None:
            if service.corporate_profiles is None:
                continue
            snapshot = await service.corporate_profiles.owner(tenant_id, identity.subject)
            if (
                snapshot is None
                or snapshot.status == "conflict"
                or snapshot.provider_id != provider.id
                or snapshot.external_subject != identity.external_subject
            ):
                continue
            selected = {
                key: value
                for key, value in selected.items()
                if getattr(sync, targets[key]) == "verified_claims"
            }
        if observed_at is not None:
            if snapshot is not None and (
                snapshot.verified_at != observed_at
                or snapshot.claims_observed_at is not None
                and snapshot.claims_observed_at >= observed_at
            ):
                continue
            if (
                sync is None
                and row is not None
                and row.observed_at is not None
                and row.observed_at >= observed_at
            ):
                continue
        if not selected:
            continue
        row = row or Person(
            id=str(uuid4()),
            tenant_id=tenant_id,
            subject=identity.subject,
            provider_id=provider.id,
            external_subject=identity.external_subject,
            revision=0,
            managed_fields=[],
            pending_manager=False,
            observation_status="not_observed",
            updated_by=identity.subject,
        )
        row.external_subject = identity.external_subject
        changes = {}
        available = True
        pending = False
        for target, claim in selected.items():
            if claim not in claims:
                available = False
                continue
            value = claims[claim]
            if value is not None and (
                not isinstance(value, str) or len(value) > 512 or any(ord(char) < 32 for char in value)
            ):
                available = False
                continue
            if target == "job_title":
                try:
                    changes["job_title"] = OrganizationPersonPatch(
                        expected_revision=1, job_title=value or None
                    ).job_title
                except ValidationError:
                    available = False
            elif target == "unit_external_key":
                if not value:
                    changes["unit_id"] = None
                else:
                    unit = await service.people.external_unit(tenant_id, provider.id, value)
                    if unit is None:
                        available = False
                    else:
                        changes["unit_id"] = unit.id
            else:
                if not value:
                    changes["manager_id"] = None
                else:
                    manager_rows = await service.people.external_people(tenant_id, provider.id, value)
                    manager = manager_rows[0] if len(manager_rows) == 1 else None
                    if manager is None or not await service.people.member(
                        service.catalog.effective_membership_rows(), tenant_id, manager.subject
                    ):
                        changes["manager_id"] = None
                        pending = True
                        available = False
                    else:
                        changes["manager_id"] = manager.id
        try:
            await service._links(
                tenant_id, row, changes.get("unit_id", row.unit_id), changes.get("manager_id", row.manager_id)
            )
        except Exception:
            # Invalid upstream ancestry is metadata unavailability, never an access-policy operation.
            available = False
            changes = {}
        for key, value in changes.items():
            setattr(row, key, value)
        row.pending_manager = pending if "manager_external_subject" in selected else row.pending_manager
        row.managed_fields = [
            {
                "job_title": "job_title",
                "unit_external_key": "unit_id",
                "manager_external_subject": "manager_id",
            }[target]
            for target in selected
        ]
        if sync is not None:
            row.managed_fields = sorted(
                set(row.managed_fields)
                | {
                    target
                    for target, source in (
                        ("job_title", sync.job_title_source),
                        ("unit_id", sync.unit_source),
                        ("manager_id", sync.manager_source),
                    )
                    if source == "directory"
                }
            )
        row.revision += 1
        row.observed_at, row.updated_at = observed_at or datetime.now(UTC), datetime.now(UTC)
        row.observation_status = "current" if available else "unavailable"
        row.updated_by = identity.subject
        await service.people.save(row)
        if snapshot is not None:
            assert service.corporate_profiles is not None
            from koinon.corporate_profiles.service import bump

            previous = {item["field"]: item for item in snapshot.fields_json}
            now = (observed_at or datetime.now(UTC)).isoformat()
            for target, claim in selected.items():
                field, column = {
                    "job_title": ("job_title", "job_title"),
                    "unit_external_key": ("department", "unit_id"),
                    "manager_external_subject": ("manager", "manager_id"),
                }[target]
                applied = column in changes and not (target == "manager_external_subject" and pending)
                previous[field] = {
                    "field": field,
                    "source": "verified_claims",
                    "status": ("empty" if not claims[claim] else "current") if applied else "unavailable",
                    "observed_at": now if applied else previous.get(field, {}).get("observed_at"),
                    "code": None if applied else "PROFILE_CLAIM_UNAVAILABLE",
                }
            snapshot.fields_json = list(previous.values())
            snapshot.revision = bump(snapshot.revision)
            snapshot.updated_at = datetime.now(UTC)
            snapshot.claims_observed_at = observed_at or datetime.now(UTC)
            await service.corporate_profiles.save(snapshot)
        if not await service.people.member(
            service.catalog.effective_membership_rows(), tenant_id, identity.subject
        ):
            from koinon.organization_people.service import denied

            denied()
        await service.catalog._audit(
            identity.subject,
            tenant_id,
            "organization.profile.observed",
            row.id,
            {"revision": row.revision, "available": available},
        )
