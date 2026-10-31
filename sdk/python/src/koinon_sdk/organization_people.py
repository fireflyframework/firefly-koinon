# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Generated wire fields.

Source: backend/src/koinon/organization_people/dtos.py
SHA256: e8755a7e85300eaf639405042cb1c14c5daadff0f376c6e6f80afcc9f08bc9cd

Server authorization and semantic validation remain authoritative.
"""

from datetime import datetime
from typing import Literal

from pydantic import ConfigDict, Field

from koinon_sdk._base import InputModel, ResponseModel
from koinon_sdk.corporate_profiles import (
    CorporatePresentationSummary,
    CorporateProfileFieldCapability,
    CorporateProfileSyncPolicy,
)

UnitKind = Literal["division", "department", "team"]
Visibility = Literal["administrators", "shared_workspaces"]
ManagedField = Literal["job_title", "unit_id", "manager_id"]


class Input(InputModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Output(ResponseModel):
    pass


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
    managed_fields: list[ManagedField] = Field(default_factory=list[ManagedField])
    observed_at: datetime | None = None
    updated_at: datetime | None = None
    observation_status: Literal["not_observed", "current", "unavailable"] = "not_observed"
    presentation: CorporatePresentationSummary | None = None


class OrganizationPersonCreate(Input):
    profile_id: str | None = Field(default=None, min_length=1, max_length=64)
    subject: str | None = Field(default=None, min_length=3, max_length=512)
    job_title: str | None = Field(default=None, max_length=160)
    unit_id: str | None = Field(default=None, min_length=1, max_length=64)
    manager_id: str | None = Field(default=None, min_length=1, max_length=64)


class OrganizationPersonPatch(Input):
    expected_revision: int = Field(ge=1, le=2147483646)
    job_title: str | None = Field(default=None, max_length=160)
    unit_id: str | None = Field(default=None, min_length=1, max_length=64)
    manager_id: str | None = Field(default=None, min_length=1, max_length=64)
    manage_locally: bool = False
    managed_provider_id: str | None = Field(default=None, min_length=1, max_length=64)


class OrganizationUnitInput(Input):
    name: str = Field(min_length=1, max_length=160)
    kind: UnitKind = "department"
    parent_id: str | None = Field(default=None, min_length=1, max_length=64)
    provider_id: str | None = Field(default=None, min_length=1, max_length=64)
    external_key: str | None = Field(default=None, min_length=1, max_length=256)


class OrganizationUnitPatch(Input):
    expected_revision: int = Field(ge=1, le=2147483646)
    name: str | None = Field(default=None, min_length=1, max_length=160)
    kind: UnitKind | None = None
    parent_id: str | None = Field(default=None, min_length=1, max_length=64)


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
    job_title: str | None = Field(default=None, pattern="^[A-Za-z][A-Za-z0-9_]{0,79}$")
    unit_external_key: str | None = Field(default=None, pattern="^[A-Za-z][A-Za-z0-9_]{0,79}$")
    manager_external_subject: str | None = Field(default=None, pattern="^[A-Za-z][A-Za-z0-9_]{0,79}$")


class OrganizationProfileMappingInput(Input):
    expected_revision: int = Field(ge=0, le=2147483646)
    enabled: bool
    fields: OrganizationProfileFields
    profile_sync: CorporateProfileSyncPolicy | None = None


class OrganizationProfileMapping(Output):
    tenant_id: str
    provider_id: str
    revision: int = Field(default=0, ge=0, le=2147483647)
    enabled: bool = False
    fields: OrganizationProfileFields = Field(default_factory=OrganizationProfileFields)
    source: Literal["verified_claims"] = "verified_claims"
    profile_sync: CorporateProfileSyncPolicy | None = None
    profile_capabilities: list[CorporateProfileFieldCapability] = Field(
        default_factory=list[CorporateProfileFieldCapability], max_length=5
    )
