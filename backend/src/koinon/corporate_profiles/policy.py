# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import hashlib
import json

from koinon.corporate_identity.dtos import EntraSettings, GoogleWorkspaceSettings, KeycloakSettings
from koinon.corporate_profiles.dtos import CorporateProfileFieldCapability, CorporateProfileSyncPolicy


def active_policy(mapping):
    if mapping is None or not mapping.enabled or getattr(mapping, "profile_sync_json", None) is None:
        return None
    return CorporateProfileSyncPolicy.model_validate(mapping.profile_sync_json)


def source_fingerprint(provider, settings):
    identity = (
        {"issuer": settings.issuer}
        if isinstance(settings, KeycloakSettings)
        else {"tenant_id": str(settings.tenant_id)}
        if isinstance(settings, EntraSettings)
        else {"hosted_domains": sorted(settings.hosted_domains), "customer_id": settings.customer_id}
    )
    content = [provider.kind, provider.canonical_issuer, provider.broker_alias, identity]
    return hashlib.sha256(json.dumps(content, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def capabilities(settings, policy, claims):
    if policy is None:
        return []
    sources = {
        "display_name": "directory" if policy.name_source == "directory" else "personal",
        "avatar": "directory" if policy.avatar_source == "directory" else "personal",
        "job_title": policy.job_title_source,
        "department": policy.unit_source,
        "manager": policy.manager_source,
    }
    required = (
        ["User.Read.All"]
        if isinstance(settings, EntraSettings)
        else ["https://www.googleapis.com/auth/admin.directory.user.readonly"]
        if isinstance(settings, GoogleWorkspaceSettings)
        else ["view-users or equivalent fine-grained user-view permission"]
    )
    result = []
    for target, source in sources.items():
        supported, code = True, None
        if source == "verified_claims":
            claim = getattr(
                claims,
                {
                    "job_title": "job_title",
                    "department": "unit_external_key",
                    "manager": "manager_external_subject",
                }[target],
            )
            supported, code = bool(claim), None if claim else "PROFILE_CLAIM_MAPPING_REQUIRED"
        elif source == "directory":
            if target == "manager" and isinstance(settings, EntraSettings):
                supported, code = False, "PROFILE_MANAGER_APP_UNSUPPORTED"
            elif isinstance(settings, KeycloakSettings) and target != "display_name":
                selected = getattr(policy.keycloak_attributes, "picture" if target == "avatar" else target)
                supported, code = bool(selected), None if selected else "PROFILE_ATTRIBUTE_REQUIRED"
        result.append(
            CorporateProfileFieldCapability.model_validate(
                {
                    "field": target,
                    "source": source,
                    "supported": supported,
                    "required_permissions": required if source == "directory" else [],
                    "code": code,
                }
            )
        )
    return result


def mapping_view(tenant_id, provider_id, row, provider):
    from pydantic import TypeAdapter

    from koinon.corporate_identity.dtos import ProviderSettings
    from koinon.organization_people.dtos import OrganizationProfileFields, OrganizationProfileMapping

    fields = OrganizationProfileFields.model_validate(row.fields_json if row else {})
    configured = (
        CorporateProfileSyncPolicy.model_validate(row.profile_sync_json)
        if row and row.profile_sync_json is not None
        else None
    )
    settings = TypeAdapter(ProviderSettings).validate_python(provider.settings_json) if provider else None
    return OrganizationProfileMapping(
        tenant_id=tenant_id,
        provider_id=provider_id,
        revision=row.revision if row else 0,
        enabled=row.enabled if row else False,
        fields=fields,
        profile_sync=configured,
        profile_capabilities=capabilities(settings, configured, fields) if settings else [],
    )


def position_fields(mapping):
    """Resolve declared ownership without waiting for a successful directory read."""
    if mapping is not None and mapping.profile_sync_json is not None:
        policy = CorporateProfileSyncPolicy.model_validate(mapping.profile_sync_json)
        return sorted(
            target
            for target, source in (
                ("job_title", policy.job_title_source),
                ("unit_id", policy.unit_source),
                ("manager_id", policy.manager_source),
            )
            if source != "local"
        )
    columns = {
        "job_title": "job_title",
        "unit_external_key": "unit_id",
        "manager_external_subject": "manager_id",
    }
    return (
        sorted(columns[key] for key, value in mapping.fields_json.items() if value is not None)
        if mapping
        else []
    )
