# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Generated wire fields.

Source: backend/src/koinon/corporate_profiles/dtos.py
SHA256: 0d255876ce7c6a30fe0cf60aadeffc94853c009988681bbf4013403f51d370fb

Server authorization and semantic validation remain authoritative.
"""

from datetime import datetime
from typing import Literal, Self

from pydantic import ConfigDict, Field, field_validator, model_validator
from pydantic.json_schema import SkipJsonSchema

from koinon_sdk._base import InputModel, ResponseModel

ProfilePresentationMode = Literal["organization", "personal"]
ProfileFieldSource = Literal["directory", "verified_claims", "local"]
ProfileSyncStatus = Literal[
    "not_configured", "not_bound", "queued", "running", "current", "stale", "unavailable", "conflict"
]
ProfileFieldName = Literal["display_name", "avatar", "job_title", "department", "manager"]
ProfileFieldStatus = Literal["not_observed", "current", "empty", "unavailable", "unsupported", "stale"]


class Input(InputModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Output(ResponseModel):
    pass


class KeycloakProfileAttributes(Input):
    display_name: str | None = Field(default=None, pattern="^[A-Za-z][A-Za-z0-9_]{0,79}$")
    job_title: str | None = Field(default=None, pattern="^[A-Za-z][A-Za-z0-9_]{0,79}$")
    department: str | None = Field(default=None, pattern="^[A-Za-z][A-Za-z0-9_]{0,79}$")
    manager: str | None = Field(default=None, pattern="^[A-Za-z][A-Za-z0-9_]{0,79}$")
    picture: str | None = Field(default=None, pattern="^[A-Za-z][A-Za-z0-9_]{0,79}$")


class CorporateProfileSyncPolicy(Input):
    interval_seconds: int = Field(default=900, ge=300, le=86400)
    allow_personal_overrides: bool = True
    name_source: Literal["directory", "personal"] = "directory"
    avatar_source: Literal["directory", "personal"] = "directory"
    job_title_source: ProfileFieldSource = "directory"
    unit_source: ProfileFieldSource = "directory"
    manager_source: ProfileFieldSource = "verified_claims"
    google_department: Literal["department", "org_unit_path"] = "department"
    keycloak_attributes: KeycloakProfileAttributes = Field(default_factory=KeycloakProfileAttributes)


class CorporateProfileFieldCapability(Output):
    field: ProfileFieldName
    source: Literal["directory", "verified_claims", "local", "personal"]
    supported: bool
    required_permissions: list[str] = Field(default_factory=list[str], max_length=4)
    code: str | None = Field(default=None, max_length=64)


class CorporateProfileFieldObservation(Output):
    field: ProfileFieldName
    source: Literal["directory", "verified_claims", "local", "personal"]
    status: ProfileFieldStatus
    observed_at: datetime | None = None
    code: str | None = Field(default=None, max_length=64)


class CorporatePresentationSummary(Output):
    name_source: ProfilePresentationMode = "personal"
    avatar_source: ProfilePresentationMode = "personal"
    provider_id: str | None = None
    provider_name: str | None = None
    status: ProfileSyncStatus = "not_configured"
    last_synced_at: datetime | None = None
    corporate_department: str | None = Field(default=None, max_length=160)


class OrganizationPresentation(CorporatePresentationSummary):
    tenant_id: str
    profile_id: str | None = None
    revision: int = Field(default=0, ge=0, le=2147483647)
    name_mode: ProfilePresentationMode = "organization"
    avatar_mode: ProfilePresentationMode = "organization"
    allow_personal_overrides: bool = True
    display_name: str = Field(default="", max_length=256)
    avatar_url: str | None = None
    avatar_version: str | None = None
    last_attempt_at: datetime | None = None
    fields: list[CorporateProfileFieldObservation] = Field(
        default_factory=list[CorporateProfileFieldObservation], max_length=5
    )


class OrganizationPresentationInput(Input):
    expected_revision: int = Field(ge=0, le=2147483646)
    name_mode: ProfilePresentationMode | SkipJsonSchema[None] = None
    avatar_mode: ProfilePresentationMode | SkipJsonSchema[None] = None

    @field_validator("name_mode", "avatar_mode")
    @classmethod
    def nonnull(cls, value: ProfilePresentationMode | None) -> ProfilePresentationMode:
        if value is None:
            raise ValueError("Choose organization or personal presentation")
        return value

    @model_validator(mode="after")
    def selected_mode(self) -> Self:
        if not self.model_fields_set.intersection({"name_mode", "avatar_mode"}):
            raise ValueError("Choose a presentation preference")
        return self


class CorporateProfileRefreshInput(Input):
    pass


class CorporateProfileRefresh(Output):
    tenant_id: str
    profile_id: str | None = None
    status: ProfileSyncStatus
    snapshot_revision: int = Field(default=0, ge=0, le=2147483647)
    last_synced_at: datetime | None = None
    last_attempt_at: datetime | None = None
