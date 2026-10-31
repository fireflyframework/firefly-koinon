# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Pure corporate presentation projection; no repository or network operations."""

import base64
from dataclasses import dataclass
from urllib.parse import quote

from koinon.corporate_identity.entities import CorporateProvider
from koinon.corporate_profiles.dtos import (
    CorporatePresentationSummary,
    CorporateProfileSyncPolicy,
    OrganizationPresentation,
)
from koinon.corporate_profiles.entities import CorporateProfileSnapshot as Snapshot
from koinon.corporate_profiles.entities import OrganizationPresentationPreference as Preference
from koinon.corporate_profiles.policy import position_fields
from koinon.organization_people.entities import OrganizationProfileMappingRecord as Mapping
from koinon.profiles.entities import Profile


@dataclass(slots=True)
class EffectivePresentation:
    subject: str
    profile_id: str | None
    name: str
    avatar: bytes | None
    avatar_version: str | None
    summary: CorporatePresentationSummary
    preference: Preference | None
    snapshot: Snapshot | None
    policy: CorporateProfileSyncPolicy | None
    profile: Profile | None
    provider: CorporateProvider | None
    mapping: Mapping | None
    conflict_overrides_allowed: bool = True
    current_member: bool = True
    conflict_enabled: bool = False
    conflict_name_required: bool = False
    conflict_avatar_required: bool = False

    def url(self, tenant_id, workspace_id=None):
        if not self.profile_id or not self.avatar_version:
            return None
        url = (
            f"/api/v1/tenants/{quote(tenant_id, safe='')}/organization/people/"
            f"{self.profile_id}/avatar?v={self.avatar_version}"
        )
        return url + "&workspace_id=" + quote(workspace_id, safe="") if workspace_id else url

    def own(self, tenant_id, workspace_id=None):
        return OrganizationPresentation(
            **self.summary.model_dump(),
            tenant_id=tenant_id,
            profile_id=self.profile_id,
            revision=self.preference.revision if self.preference else 0,
            name_mode="personal"
            if self.preference and self.preference.name_mode == "personal"
            else "organization",
            avatar_mode="personal"
            if self.preference and self.preference.avatar_mode == "personal"
            else "organization",
            allow_personal_overrides=self.policy.allow_personal_overrides
            if self.policy
            else self.conflict_overrides_allowed,
            display_name=self.name,
            avatar_url=self.url(tenant_id, workspace_id),
            avatar_version=self.avatar_version,
            last_attempt_at=self.snapshot.last_attempt_at if self.snapshot else None,
            fields=self.snapshot.fields_json if self.snapshot and self.policy else [],
        )


def effective(
    subject,
    profile,
    snapshot,
    preference,
    provider,
    mapping,
    *,
    conflict_enabled=False,
    conflict_name_required=False,
    conflict_avatar_required=False,
    conflict_overrides_allowed=True,
    current_member=True,
):
    try:
        policy = (
            CorporateProfileSyncPolicy.model_validate(mapping.profile_sync_json)
            if mapping and mapping.enabled and mapping.profile_sync_json is not None
            else None
        )
    except Exception:
        policy = None
    name, photo, version = (
        (profile.display_name, profile.avatar_bytes, profile.avatar_version) if profile else ("", None, None)
    )
    name_source = avatar_source = "personal"
    current = bool(
        policy
        and current_member
        and provider
        and provider.status == "active"
        and mapping.enabled
        and snapshot
        and snapshot.provider_revision == provider.revision
        and snapshot.mapping_revision == mapping.revision
        and snapshot.status != "conflict"
    )
    if policy:
        allowed = policy.allow_personal_overrides
        if policy.name_source == "directory" and not (
            allowed and preference and preference.name_mode == "personal"
        ):
            name_source = "organization"
            name = snapshot.display_name or "" if current and snapshot.name_available else ""
        if policy.avatar_source == "directory" and not (
            allowed and preference and preference.avatar_mode == "personal"
        ):
            avatar_source = "organization"
            photo, version = (
                (snapshot.avatar_bytes, snapshot.avatar_version)
                if current and snapshot.avatar_available
                else (None, None)
            )
    if not current_member:
        name, photo, version = "", None, None
    status = (snapshot.status if snapshot else "not_bound") if policy else "not_configured"
    if policy and (provider is None or provider.status != "active"):
        status = "unavailable"
    if (
        snapshot
        and snapshot.status == "conflict"
        and (policy or snapshot.provider_id is None and conflict_enabled)
    ):
        status = "conflict"
        if policy is None and snapshot.provider_id is None:
            if conflict_name_required and not (
                conflict_overrides_allowed and preference and preference.name_mode == "personal"
            ):
                name, name_source = "", "organization"
            if conflict_avatar_required and not (
                conflict_overrides_allowed and preference and preference.avatar_mode == "personal"
            ):
                photo, version, avatar_source = None, None, "organization"
    if policy and snapshot and not current and status not in {"queued", "running", "conflict", "unavailable"}:
        status = "stale"
    summary = CorporatePresentationSummary(
        name_source=name_source,
        avatar_source=avatar_source,
        provider_id=provider.id if policy and provider else None,
        provider_name=provider.name if policy and provider else None,
        status=status,
        last_synced_at=snapshot.last_success_at if policy and snapshot else None,
        corporate_department=snapshot.department if current else None,
    )
    return EffectivePresentation(
        subject,
        profile.id if profile else None,
        name,
        photo,
        version,
        summary,
        preference,
        snapshot,
        policy,
        profile,
        provider,
        mapping,
        conflict_overrides_allowed,
        current_member,
        conflict_enabled,
        conflict_name_required,
        conflict_avatar_required,
    )


def decorate_person(value, subject, presentations, tenant_id, workspace_id=None, manager_subject=None):
    item = presentations[subject]
    manager = value.manager
    if manager is not None:
        other = presentations.get(manager_subject)
        manager = manager.model_copy(update={"display_name": other.name}) if other else None
    return value.model_copy(
        update={
            "display_name": item.name,
            "avatar_url": item.url(tenant_id, workspace_id),
            "avatar_version": item.avatar_version,
            "presentation": item.summary,
            "managed_fields": position_fields(item.mapping)
            if value.source == "provider" and item.mapping and item.mapping.provider_id == value.provider_id
            else value.managed_fields,
            "manager": manager,
            "manager_unavailable": value.manager_unavailable or value.manager is not None and manager is None,
        }
    )


def author_view(value):
    return {
        "subject": value.subject,
        "display_name": value.name,
        "avatar_data_url": ("data:image/jpeg;base64," + base64.b64encode(value.avatar).decode())
        if value.avatar
        else None,
        "avatar_version": value.avatar_version,
    }
