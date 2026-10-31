# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Bounded presentation observations, independent from access-grant observations."""

from dataclasses import dataclass, field
from uuid import UUID

from koinon.corporate_identity.dtos import (
    EntraSettings,
    GoogleWorkspaceSettings,
    KeycloakSettings,
    ProviderSettings,
)
from koinon.corporate_profiles.dtos import CorporateProfileSyncPolicy


class ProfileObservationError(Exception):
    def __init__(self, code="PROFILE_DIRECTORY_UNAVAILABLE", *, retry_after=0):
        super().__init__("Corporate profile could not be observed")
        self.code, self.retry_after = code, retry_after


@dataclass(frozen=True, slots=True)
class FieldObservation:
    status: str
    value: str | bytes | None = None
    code: str | None = None


@dataclass(slots=True)
class DirectoryProfileObservation:
    external_subject: str
    fields: dict[str, FieldObservation] = field(default_factory=dict)
    customer_id: str | None = None
    manager_lookup: str | None = None


def text(value, maximum):
    if value is None or value == "":
        return FieldObservation("empty")
    if (
        not isinstance(value, str)
        or len(value) > maximum
        or any(ord(char) < 32 or 0xD800 <= ord(char) <= 0xDFFF for char in value)
    ):
        return FieldObservation("unavailable", code="PROFILE_FIELD_INVALID")
    value = value.strip()
    return FieldObservation("current", value) if value else FieldObservation("empty")


def observed(raw, key, maximum):
    return (
        text(raw[key], maximum)
        if key in raw
        else FieldObservation("unavailable", code="PROFILE_FIELD_ABSENT")
    )


def attribute(raw, key, maximum):
    if key is None:
        return FieldObservation("unsupported", code="PROFILE_ATTRIBUTE_REQUIRED")
    if not isinstance(raw, dict) or key not in raw:
        return FieldObservation("unavailable", code="PROFILE_FIELD_ABSENT")
    values = raw[key]
    if not isinstance(values, list) or len(values) > 1:
        return FieldObservation("unavailable", code="PROFILE_FIELD_AMBIGUOUS")
    return text(values[0] if values else None, maximum)


def normalize_user(
    settings: ProviderSettings, config: CorporateProfileSyncPolicy, expected: str, raw
) -> DirectoryProfileObservation:
    if not isinstance(raw, dict) or not isinstance(expected, str) or not 1 <= len(expected) <= 512:
        raise ProfileObservationError("PROFILE_IDENTITY_MISMATCH")
    if isinstance(settings, EntraSettings):
        try:
            same = str(UUID(raw.get("id", ""))) == str(UUID(expected))
        except (ValueError, TypeError, AttributeError):
            same = False
        if not same:
            raise ProfileObservationError("PROFILE_IDENTITY_MISMATCH")
        if raw.get("accountEnabled") is not True:
            raise ProfileObservationError("PROFILE_ACCOUNT_UNAVAILABLE")
        result = DirectoryProfileObservation(
            expected,
            {
                "display_name": observed(raw, "displayName", 256),
                "job_title": observed(raw, "jobTitle", 160),
                "department": observed(raw, "department", 160),
                "manager": FieldObservation("unsupported", code="PROFILE_MANAGER_APP_UNSUPPORTED"),
            },
        )
    elif isinstance(settings, GoogleWorkspaceSettings):
        customer = raw.get("customerId")
        if (
            raw.get("id") != expected
            or not isinstance(customer, str)
            or not 1 <= len(customer) <= 128
            or settings.customer_id not in (None, "my_customer", customer)
        ):
            raise ProfileObservationError("PROFILE_IDENTITY_MISMATCH")
        if raw.get("suspended") is not False or raw.get("archived") is True:
            raise ProfileObservationError("PROFILE_ACCOUNT_UNAVAILABLE")
        name = raw.get("name")
        result = DirectoryProfileObservation(
            expected,
            {
                "display_name": observed(name, "fullName", 256)
                if isinstance(name, dict)
                else FieldObservation("unavailable", code="PROFILE_FIELD_ABSENT")
            },
            customer_id=customer,
        )
        organizations = raw.get("organizations")
        primary = (
            [item for item in organizations if isinstance(item, dict) and item.get("primary") is True]
            if isinstance(organizations, list) and len(organizations) <= 16
            else []
        )
        organization = (
            primary[0]
            if len(primary) == 1
            else organizations[0]
            if isinstance(organizations, list)
            and len(organizations) == 1
            and isinstance(organizations[0], dict)
            else None
        )
        for target, key in (("job_title", "title"), ("department", "department")):
            result.fields[target] = (
                observed(organization, key, 160)
                if organization is not None
                else FieldObservation("empty")
                if organizations == []
                else FieldObservation("unavailable", code="PROFILE_FIELD_AMBIGUOUS")
            )
        if config.google_department == "org_unit_path":
            result.fields["department"] = observed(raw, "orgUnitPath", 160)
        relations = raw.get("relations")
        managers = (
            [item for item in relations if isinstance(item, dict) and item.get("type") == "manager"]
            if isinstance(relations, list) and len(relations) <= 32
            else []
        )
        if isinstance(relations, list) and len(relations) <= 32 and not managers:
            result.fields["manager"] = FieldObservation("empty")
        elif len(managers) == 1:
            value = text(managers[0].get("value"), 320)
            result.manager_lookup = (
                value.value
                if value.status == "current" and isinstance(value.value, str) and "@" in value.value
                else None
            )
            result.fields["manager"] = FieldObservation("unavailable", code="PROFILE_MANAGER_UNRESOLVED")
        else:
            result.fields["manager"] = FieldObservation("unavailable", code="PROFILE_FIELD_AMBIGUOUS")
    elif isinstance(settings, KeycloakSettings):
        if raw.get("id") != expected:
            raise ProfileObservationError("PROFILE_IDENTITY_MISMATCH")
        if raw.get("enabled") is not True:
            raise ProfileObservationError("PROFILE_ACCOUNT_UNAVAILABLE")
        attributes = raw.get("attributes", {})
        selected = config.keycloak_attributes
        if selected.display_name:
            name = attribute(attributes, selected.display_name, 256)
        else:
            first, last = text(raw.get("firstName"), 128), text(raw.get("lastName"), 128)
            name = (
                text(" ".join(value.value for value in (first, last) if isinstance(value.value, str)), 256)
                if all(value.status in {"empty", "current"} for value in (first, last))
                else FieldObservation("unavailable", code="PROFILE_FIELD_INVALID")
            )
        result = DirectoryProfileObservation(
            expected,
            {
                "display_name": name,
                "job_title": attribute(attributes, selected.job_title, 160),
                "department": attribute(attributes, selected.department, 160),
                "manager": attribute(attributes, selected.manager, 512),
                "avatar": attribute(attributes, selected.picture, 2048),
            },
        )
    else:
        raise ProfileObservationError("PROFILE_PROVIDER_UNSUPPORTED")
    for target, source in (
        ("job_title", config.job_title_source),
        ("department", config.unit_source),
        ("manager", config.manager_source),
    ):
        if source != "directory":
            result.fields[target] = FieldObservation("not_observed")
    if config.name_source != "directory":
        result.fields["display_name"] = FieldObservation("not_observed")
    return result
