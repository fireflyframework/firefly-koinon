# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from urllib.parse import quote

from koinon.organization_people.dtos import (
    OrganizationPerson,
    OrganizationPersonReference,
    OrganizationUnit,
    OrganizationUnitSummary,
)


def unit_view(row, has_children=False):
    return OrganizationUnit(
        updated_at=row.updated_at,
        id=row.id,
        tenant_id=row.tenant_id,
        parent_id=row.parent_id,
        name=row.name,
        kind=row.kind,
        revision=row.revision,
        provider_id=row.provider_id,
        has_children=has_children,
    )


def person_view(subject, row, profile, tenant_id, workspace_id, units, managers, providers):
    unit = units.get(row.unit_id) if row else None
    department = None
    current = unit
    for _ in range(32):
        if current is None:
            break
        if current.kind == "department":
            department = current
            break
        current = units.get(current.parent_id)
    manager = managers.get(row.manager_id) if row and row.manager_id and not row.pending_manager else None
    url = None
    if profile and profile.avatar_version:
        identifier = row.id if row else profile.id
        url = (
            f"/api/v1/tenants/{quote(tenant_id, safe='')}/organization/people/"
            f"{identifier}/avatar?v={profile.avatar_version}"
        )
        if workspace_id:
            url += "&workspace_id=" + quote(workspace_id, safe="")
    provider = providers.get(row.provider_id) if row and row.provider_id else None
    return OrganizationPerson(
        id=row.id if row else None,
        profile_id=profile.id if profile else None,
        display_name=profile.display_name if profile else "",
        avatar_url=url,
        avatar_version=profile.avatar_version if profile else None,
        job_title=row.job_title if row else None,
        unit=OrganizationUnitSummary(id=unit.id, name=unit.name, kind=unit.kind) if unit else None,
        department=OrganizationUnitSummary(id=department.id, name=department.name, kind=department.kind)
        if department
        else None,
        manager=OrganizationPersonReference(
            id=manager[0].id, display_name=manager[1].display_name if manager[1] else ""
        )
        if manager
        else None,
        manager_unavailable=bool(row and (row.pending_manager or row.manager_id and manager is None)),
        revision=row.revision if row else 0,
        source=("provider" if row.provider_id else "manual") if row else "unassigned",
        provider_id=row.provider_id if row else None,
        provider_name=provider.name if provider else None,
        managed_fields=row.managed_fields if row else [],
        observed_at=row.observed_at if row else None,
        updated_at=row.updated_at if row else None,
        observation_status=(
            "unavailable"
            if row.provider_id and (provider is None or provider.status != "active")
            else row.observation_status
        )
        if row
        else "not_observed",
    )
