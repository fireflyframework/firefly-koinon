# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import re
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator

from koinon.catalog.dtos import Role
from koinon.security.settings import _endpoint

ProviderKind = Literal["keycloak", "entra", "google_workspace"]
ProviderStatus = Literal["draft", "configured", "blocked", "verified", "active", "disabled"]
MembershipMode = Literal["direct", "transitive"]


class StrictInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class KeycloakSettings(StrictInput):
    kind: Literal["keycloak"]
    issuer: str = Field(max_length=2048)
    client_id: str = Field(min_length=1, max_length=255)
    directory_client_id: str | None = Field(default=None, min_length=1, max_length=255)
    membership_mode: MembershipMode = "direct"

    @field_validator("issuer")
    @classmethod
    def issuer_endpoint(cls, value):
        _endpoint(value)
        if "?" in value or "|" in value:
            raise ValueError("Use an exact issuer without query parameters")
        return value


class EntraSettings(StrictInput):
    kind: Literal["entra"]
    tenant_id: UUID
    client_id: str = Field(min_length=1, max_length=255)
    directory_client_id: str | None = Field(default=None, min_length=1, max_length=255)
    membership_mode: MembershipMode = "direct"


class GoogleWorkspaceSettings(StrictInput):
    kind: Literal["google_workspace"]
    client_id: str = Field(min_length=1, max_length=255)
    hosted_domains: list[str] = Field(min_length=1, max_length=10)
    customer_id: str | None = Field(default=None, max_length=128)
    membership_mode: MembershipMode = "direct"

    @field_validator("hosted_domains")
    @classmethod
    def domains(cls, values):
        result = []
        for value in values:
            value = value.casefold().encode("idna").decode("ascii")
            if len(value) > 253 or not re.fullmatch(
                r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+", value
            ):
                raise ValueError("Use explicit hosted domains without wildcards or URLs")
            if value not in result:
                result.append(value)
        return result


ProviderSettings = Annotated[
    KeycloakSettings | EntraSettings | GoogleWorkspaceSettings, Field(discriminator="kind")
]


class KeycloakCredential(StrictInput):
    kind: Literal["keycloak"]
    secret: SecretStr = Field(min_length=1, max_length=8192)
    directory_secret: SecretStr | None = Field(default=None, min_length=1, max_length=8192)


class EntraCredential(StrictInput):
    kind: Literal["entra"]
    secret: SecretStr = Field(min_length=1, max_length=8192)
    directory_secret: SecretStr | None = Field(default=None, min_length=1, max_length=8192)


class GoogleCredential(StrictInput):
    kind: Literal["google_workspace"]
    secret: SecretStr | None = Field(default=None, min_length=1, max_length=8192)
    service_account_email: str | None = Field(default=None, max_length=320)
    private_key: SecretStr | None = Field(default=None, min_length=1, max_length=32768)
    private_key_id: str | None = Field(default=None, max_length=255)
    delegated_admin: str | None = Field(default=None, max_length=320)


ProviderCredential = Annotated[
    KeycloakCredential | EntraCredential | GoogleCredential, Field(discriminator="kind")
]


class IdentityProviderInput(StrictInput):
    kind: ProviderKind
    name: str = Field(min_length=1, max_length=120)
    broker_alias: str | None = Field(default=None, pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$")
    settings: ProviderSettings
    credential: ProviderCredential | None = Field(default=None, repr=False)
    credential_reference: str | None = Field(default=None, min_length=1, max_length=120)

    @field_validator("name")
    @classmethod
    def display_name(cls, value):
        if not value.strip() or any(ord(char) < 32 for char in value):
            raise ValueError("Use a readable provider name")
        return value.strip()

    @model_validator(mode="after")
    def matching_kind(self):
        if self.settings.kind != self.kind or (self.credential and self.credential.kind != self.kind):
            raise ValueError("Provider settings and credentials must match its kind")
        if self.kind != "keycloak" and not self.broker_alias:
            raise ValueError("Corporate providers require an explicit broker alias")
        if self.credential and self.credential_reference:
            raise ValueError("Choose a replacement credential or a deployment credential reference")
        return self


class IdentityProviderPatch(StrictInput):
    expected_revision: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=120)
    settings: ProviderSettings | None = None
    credential: ProviderCredential | None = Field(default=None, repr=False)
    credential_reference: str | None = Field(default=None, min_length=1, max_length=120)

    @field_validator("name")
    @classmethod
    def display_name(cls, value):
        return IdentityProviderInput.display_name(value) if value is not None else None


class IdentityCheck(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: str
    status: Literal["unconfigured", "unknown", "passed", "failed", "blocked", "not_run"]
    message: str
    supported: bool | None = None
    verified: bool = False
    available: bool | None = None
    observed_at: datetime | None = None


class IdentityProvider(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: str
    tenant_id: str
    kind: ProviderKind
    name: str
    canonical_issuer: str
    broker_alias: str | None
    ownership: Literal["deployment", "tenant"]
    revision: int
    policy_revision: int = 1
    status: ProviderStatus
    credential_configured: bool
    settings: ProviderSettings
    checks: list[IdentityCheck] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)
    observed_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    created_by: str | None = None
    updated_by: str | None = None


class IdentityGroup(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: str
    provider_id: str
    name: str
    path: str | None = None
    membership_mode: MembershipMode


class IdentityMappingInput(StrictInput):
    group_id: str = Field(min_length=1, max_length=256)
    role: Role
    workspace_id: str | None = Field(default=None, max_length=64)
    enabled: bool = True
    expected_revision: int | None = Field(default=None, ge=1)


class IdentityValidation(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: str
    candidate_revision: int
    expires_at: datetime
    checks: list[IdentityCheck]
    status: Literal["pending", "verified", "failed", "consumed"] = "pending"
    authorization_url: str | None = None


class IdentityRevision(StrictInput):
    expected_revision: int = Field(ge=1)


class IdentityActivation(IdentityRevision):
    validation_id: str = Field(min_length=1, max_length=64)


class IdentityMapping(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: str
    tenant_id: str
    provider_id: str
    group_id: str
    group_name: str
    role: Role
    workspace_id: str | None
    enabled: bool
    revision: int


class IdentityProviderPage(BaseModel):
    items: list[IdentityProvider]
    total: int
    page: int
    page_size: int
    pages: int


class IdentityMappingPage(BaseModel):
    items: list[IdentityMapping]
    total: int
    page: int
    page_size: int
    pages: int


class IdentityGroupPage(BaseModel):
    items: list[IdentityGroup]
    next_cursor: str | None = None
