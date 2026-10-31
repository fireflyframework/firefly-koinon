# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from sqlalchemy import and_, case, exists, func, or_, select
from sqlalchemy.orm import aliased

from koinon.corporate_identity.entities import CorporateProvider
from koinon.corporate_profiles.entities import CorporateProfileSnapshot, OrganizationPresentationPreference
from koinon.organization_people.entities import OrganizationPersonRecord, OrganizationProfileMappingRecord


def presentation_joins(query, subject, tenant_id, profile):
    snapshot = aliased(CorporateProfileSnapshot)
    preference = aliased(OrganizationPresentationPreference)
    provider = aliased(CorporateProvider)
    mapping = aliased(OrganizationProfileMappingRecord)
    provider_id = func.coalesce(snapshot.provider_id, OrganizationPersonRecord.provider_id)
    query = (
        query.outerjoin(snapshot, and_(snapshot.tenant_id == tenant_id, snapshot.subject == subject))
        .outerjoin(preference, and_(preference.tenant_id == tenant_id, preference.subject == subject))
        .outerjoin(provider, and_(provider.tenant_id == tenant_id, provider.id == provider_id))
        .outerjoin(mapping, and_(mapping.tenant_id == tenant_id, mapping.provider_id == provider_id))
    )
    active = and_(mapping.enabled.is_(True), mapping.profile_sync_json.is_not(None))
    personal = and_(
        func.coalesce(mapping.profile_sync_json["allow_personal_overrides"].as_boolean(), True),
        preference.name_mode == "personal",
    )
    corporate = and_(
        active,
        mapping.profile_sync_json["name_source"].as_string() == "directory",
        ~func.coalesce(personal, False),
    )
    policy_mapping, policy_provider = aliased(OrganizationProfileMappingRecord), aliased(CorporateProvider)
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
            func.substr(snapshot.subject, 1, func.length(policy_provider.canonical_issuer) + 1)
            == policy_provider.canonical_issuer + "|",
        )
    )
    required = exists(
        applicable.where(policy_mapping.profile_sync_json["name_source"].as_string() == "directory")
    )
    overrides_allowed = ~exists(
        applicable.where(
            func.coalesce(
                policy_mapping.profile_sync_json["allow_personal_overrides"].as_boolean(), True
            ).is_(False)
        )
    )
    conflicted = and_(
        snapshot.provider_id.is_(None),
        snapshot.status == "conflict",
        required,
        ~func.coalesce(and_(overrides_allowed, preference.name_mode == "personal"), False),
    )
    corporate = or_(corporate, conflicted)
    current = and_(
        provider.status == "active",
        snapshot.provider_revision == provider.revision,
        snapshot.mapping_revision == mapping.revision,
        snapshot.status != "conflict",
        snapshot.last_success_at.is_not(None),
        snapshot.name_available.is_(True),
    )
    name = case(
        (corporate, case((current, func.coalesce(snapshot.display_name, "")), else_="")),
        else_=func.coalesce(profile.display_name, ""),
    )
    return query, name
