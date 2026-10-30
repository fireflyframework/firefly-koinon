# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

UnitKind = Literal["division", "department", "team"]
Visibility = Literal["administrators", "shared_workspaces"]
ManagedField = Literal["job_title", "unit_id", "manager_id"]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    @field_validator("name", "job_title", check_fields=False)
    @classmethod
    def readable(cls, value):
        if value is None:
            return value
        value = value.strip()
        if not value or any(ord(char) < 32 or 0xD800 <= ord(char) <= 0xDFFF for char in value):
            raise ValueError("Use readable text")
        return value


class Output(BaseModel):
    model_config = ConfigDict(frozen=True)


class OrganizationUnitSummary(Output):
    id: str
    name: str
    kind: UnitKind


class OrganizationPersonReference(Output):
    id: str
    display_name: str


class OrganizationPerson(Output):
    id: str | None = None
    profile_id: str | None = None
    display_name: str
    avatar_url: str | None = None
    avatar_version: str | None = None
    job_title: str | None = None
    unit: OrganizationUnitSummary | None = None
    department: OrganizationUnitSummary | None = None
    manager: OrganizationPersonReference | None = None
    manager_unavailable: bool = False
    revision: int = Field(default=0, ge=0, le=2147483647)
    source: Literal["unassigned", "manual", "provider"] = "unassigned"
    provider_id: str | None = None
    provider_name: str | None = None
    managed_fields: list[ManagedField] = Field(default_factory=list)
    observed_at: datetime | None = None
    updated_at: datetime | None = None
    observation_status: Literal["not_observed", "current", "unavailable"] = "not_observed"


class OrganizationPersonCreate(Input):
    profile_id: str | None = Field(default=None, min_length=1, max_length=64)
    subject: str | None = Field(default=None, min_length=3, max_length=512)
    job_title: str | None = Field(default=None, max_length=160)
    unit_id: str | None = Field(default=None, min_length=1, max_length=64)
    manager_id: str | None = Field(default=None, min_length=1, max_length=64)

    @model_validator(mode="after")
    def exact_person(self):
        if (self.profile_id is None) == (self.subject is None):
            raise ValueError("Choose one existing person identifier")
        return self


class OrganizationPersonPatch(Input):
    expected_revision: int = Field(ge=1, le=2147483646)
    job_title: str | None = Field(default=None, max_length=160)
    unit_id: str | None = Field(default=None, min_length=1, max_length=64)
    manager_id: str | None = Field(default=None, min_length=1, max_length=64)
    manage_locally: bool = False
    managed_provider_id: str | None = Field(default=None, min_length=1, max_length=64)

    @field_validator("managed_provider_id")
    @classmethod
    def explicit_provider(cls, value):
        if value is None or not value.strip():
            raise ValueError("Use manage_locally to release provider ownership")
        return value

    @model_validator(mode="after")
    def one_source_change(self):
        if self.manage_locally and self.managed_provider_id is not None:
            raise ValueError("Choose local or provider ownership")
        return self


class OrganizationUnitInput(Input):
    name: str = Field(min_length=1, max_length=160)
    kind: UnitKind = "department"
    parent_id: str | None = Field(default=None, min_length=1, max_length=64)
    provider_id: str | None = Field(default=None, min_length=1, max_length=64)
    external_key: str | None = Field(default=None, min_length=1, max_length=256)

    @model_validator(mode="after")
    def source_pair(self):
        if (self.provider_id is None) != (self.external_key is None):
            raise ValueError("A unit source requires both provider and external key")
        return self


class OrganizationUnitPatch(Input):
    expected_revision: int = Field(ge=1, le=2147483646)
    name: str | None = Field(default=None, min_length=1, max_length=160)
    kind: UnitKind | None = None
    parent_id: str | None = Field(default=None, min_length=1, max_length=64)

    @field_validator("name", "kind")
    @classmethod
    def nonnull(cls, value):
        if value is None:
            raise ValueError("Name and kind cannot be null")
        return value


class OrganizationUnit(OrganizationUnitSummary):
    updated_at: datetime | None = None
    tenant_id: str
    parent_id: str | None = None
    revision: int = Field(ge=1, le=2147483647)
    provider_id: str | None = None
    has_children: bool = False


class OrganizationPersonPage(Output):
    items: list[OrganizationPerson] = Field(max_length=50)
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=50)
    pages: int = Field(ge=0)


class OrganizationUnitPage(Output):
    items: list[OrganizationUnit] = Field(max_length=50)
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=50)
    pages: int = Field(ge=0)


class OrganizationDirectorySettings(Output):
    tenant_id: str
    visibility: Visibility = "administrators"
    revision: int = Field(default=0, ge=0, le=2147483647)


class OrganizationDirectorySettingsInput(Input):
    expected_revision: int = Field(ge=0, le=2147483646)
    visibility: Visibility


class OrganizationProfileFields(Input):
    job_title: str | None = Field(default=None, pattern=r"^[A-Za-z][A-Za-z0-9_]{0,79}$")
    unit_external_key: str | None = Field(default=None, pattern=r"^[A-Za-z][A-Za-z0-9_]{0,79}$")
    manager_external_subject: str | None = Field(default=None, pattern=r"^[A-Za-z][A-Za-z0-9_]{0,79}$")

    @field_validator("job_title", "unit_external_key", "manager_external_subject")
    @classmethod
    def presentation_only(cls, value):
        normalized = value.replace("_", "").casefold() if value else ""
        words = {
            word.casefold()
            for word in re.findall(r"[A-Z]+(?=[A-Z][a-z]|_|$)|[A-Z]?[a-z]+|[0-9]+", value or "")
        }
        if "secret" in words:
            raise ValueError("Choose an organizational presentation claim")
        credential_keys = (
            "password",
            "passwd",
            "clientsecret",
            "apikey",
            "accesstoken",
            "refreshtoken",
            "idtoken",
            "authorization",
            "cookie",
            "privatekey",
            "credential",
            "sessionid",
            "csrftoken",
        )
        if normalized and (
            any(key in normalized for key in credential_keys)
            or normalized in {"secret", "credentials", "setcookie"}
        ):
            raise ValueError("Choose an organizational presentation claim")
        if value and value.casefold() in {
            "iss",
            "sub",
            "oid",
            "tid",
            "email",
            "groups",
            "roles",
            "permissions",
            "nonce",
            "access_token",
            "refresh_token",
        }:
            raise ValueError("Choose an organizational presentation claim")
        return value


class OrganizationProfileMappingInput(Input):
    expected_revision: int = Field(ge=0, le=2147483646)
    enabled: bool
    fields: OrganizationProfileFields


class OrganizationProfileMapping(Output):
    tenant_id: str
    provider_id: str
    revision: int = Field(default=0, ge=0, le=2147483647)
    enabled: bool = False
    fields: OrganizationProfileFields = Field(default_factory=OrganizationProfileFields)
    source: Literal["verified_claims"] = "verified_claims"
