# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Generated wire fields.

Source: backend/src/koinon/corporate_identity/dtos.py
SHA256: 61b82a75735a2f7e186c7373385c8d8c71f550d7e1f86f46397a9c5a85fbd559

Server authorization and semantic validation remain authoritative.
"""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, SecretStr

from koinon_sdk._base import InputModel, ResponseModel
from koinon_sdk.contracts import Role

ProviderKind = Literal["keycloak", "entra", "google_workspace"]
ProviderStatus = Literal["draft", "configured", "blocked", "verified", "active", "disabled"]
MembershipMode = Literal["direct", "transitive"]


class KeycloakSettings(InputModel):
    kind: Literal["keycloak"]
    issuer: str = Field(max_length=2048)
    client_id: str = Field(min_length=1, max_length=255)
    directory_client_id: str | None = Field(default=None, min_length=1, max_length=255)
    membership_mode: MembershipMode = "direct"


class EntraSettings(InputModel):
    kind: Literal["entra"]
    tenant_id: UUID
    client_id: str = Field(min_length=1, max_length=255)
    directory_client_id: str | None = Field(default=None, min_length=1, max_length=255)
    membership_mode: MembershipMode = "direct"


class GoogleWorkspaceSettings(InputModel):
    kind: Literal["google_workspace"]
    client_id: str = Field(min_length=1, max_length=255)
    hosted_domains: list[str] = Field(min_length=1, max_length=10)
    customer_id: str | None = Field(default=None, max_length=128)
    membership_mode: MembershipMode = "direct"


ProviderSettings = Annotated[
    KeycloakSettings | EntraSettings | GoogleWorkspaceSettings, Field(discriminator="kind")
]


class KeycloakCredential(InputModel):
    kind: Literal["keycloak"]
    secret: SecretStr = Field(min_length=1, max_length=8192)
    directory_secret: SecretStr | None = Field(default=None, min_length=1, max_length=8192)


class EntraCredential(InputModel):
    kind: Literal["entra"]
    secret: SecretStr = Field(min_length=1, max_length=8192)
    directory_secret: SecretStr | None = Field(default=None, min_length=1, max_length=8192)


class GoogleCredential(InputModel):
    kind: Literal["google_workspace"]
    secret: SecretStr | None = Field(default=None, min_length=1, max_length=8192)
    service_account_email: str | None = Field(default=None, max_length=320)
    private_key: SecretStr | None = Field(default=None, min_length=1, max_length=32768)
    private_key_id: str | None = Field(default=None, max_length=255)
    delegated_admin: str | None = Field(default=None, max_length=320)


ProviderCredential = Annotated[
    KeycloakCredential | EntraCredential | GoogleCredential, Field(discriminator="kind")
]


class IdentityProviderInput(InputModel):
    kind: ProviderKind
    name: str = Field(min_length=1, max_length=120)
    broker_alias: str | None = Field(default=None, pattern="^[a-z0-9][a-z0-9_-]{0,63}$")
    settings: ProviderSettings
    credential: ProviderCredential | None = Field(default=None, repr=False)
    credential_reference: str | None = Field(default=None, min_length=1, max_length=120)


class IdentityProviderPatch(InputModel):
    expected_revision: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=120)
    settings: ProviderSettings | None = None
    credential: ProviderCredential | None = Field(default=None, repr=False)
    credential_reference: str | None = Field(default=None, min_length=1, max_length=120)


class IdentityCheck(ResponseModel):
    id: str
    status: Literal["unconfigured", "unknown", "passed", "failed", "blocked", "not_run"]
    message: str
    supported: bool | None = None
    verified: bool = False
    available: bool | None = None
    observed_at: datetime | None = None


class IdentityProvider(ResponseModel):
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
    checks: list[IdentityCheck] = Field(default_factory=list[IdentityCheck])
    capabilities: list[str] = Field(default_factory=list[str])
    observed_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    created_by: str | None = None
    updated_by: str | None = None


class IdentityGroup(ResponseModel):
    id: str
    provider_id: str
    name: str
    path: str | None = None
    membership_mode: MembershipMode


class IdentityMappingInput(InputModel):
    group_id: str = Field(min_length=1, max_length=256)
    role: Role
    workspace_id: str | None = Field(default=None, max_length=64)
    enabled: bool = True
    expected_revision: int | None = Field(default=None, ge=1)


class IdentityValidation(ResponseModel):
    id: str
    candidate_revision: int
    expires_at: datetime
    checks: list[IdentityCheck]
    status: Literal["pending", "verified", "failed", "consumed"] = "pending"
    authorization_url: str | None = None


class IdentityRevision(InputModel):
    expected_revision: int = Field(ge=1)


class IdentityActivation(IdentityRevision):
    validation_id: str = Field(min_length=1, max_length=64)


class IdentityMapping(ResponseModel):
    id: str
    tenant_id: str
    provider_id: str
    group_id: str
    group_name: str
    role: Role
    workspace_id: str | None
    enabled: bool
    revision: int


class IdentityProviderPage(ResponseModel):
    items: list[IdentityProvider]
    total: int
    page: int
    page_size: int
    pages: int


class IdentityMappingPage(ResponseModel):
    items: list[IdentityMapping]
    total: int
    page: int
    page_size: int
    pages: int


class IdentityGroupPage(ResponseModel):
    items: list[IdentityGroup]
    next_cursor: str | None = None
