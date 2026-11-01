# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Operator-only delivery observations; they never establish authentication or membership."""

from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

from koinon.communications.directory import delivery_address
from koinon.corporate_identity.policy import IdentityPolicy


class ContactIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: Literal["keycloak", "entra", "google_workspace"]
    issuer: str = Field(min_length=1, max_length=512)
    client_id: str = Field(min_length=1, max_length=255)
    external_subject: str = Field(min_length=1, max_length=512)
    broker_alias: str | None = Field(default=None, min_length=1, max_length=255)
    external_tenant_id: str | None = None
    hosted_domains: tuple[str, ...] = ()
    identity_mode: Literal["direct", "brokered"] = "direct"

    @model_validator(mode="after")
    def explicit_identity(self):
        if self.kind == "entra":
            if self.external_tenant_id != str(UUID(self.external_tenant_id or "")):
                raise ValueError("Use the exact immutable Entra tenant identifier")
            if self.external_subject != str(UUID(self.external_subject)):
                raise ValueError("Use the exact immutable Entra object identifier")
            if self.identity_mode == "direct" and (
                self.broker_alias is not None
                or self.issuer != f"https://login.microsoftonline.com/{self.external_tenant_id}/v2.0"
            ):
                raise ValueError("Direct Entra requires its exact tenant issuer without a broker")
            if self.identity_mode == "brokered" and not self.broker_alias:
                raise ValueError("Brokered Entra requires an explicit broker alias")
        elif self.kind == "google_workspace":
            if not self.broker_alias or not 1 <= len(self.hosted_domains) <= 20:
                raise ValueError("Google Workspace requires its verified broker and hosted domains")
        elif self.external_tenant_id is not None or self.hosted_domains:
            raise ValueError("Keycloak uses its exact configured issuer and immutable user identifier")
        return self

    def policy(self) -> IdentityPolicy:
        return IdentityPolicy(
            "operator-contact",
            self.kind,
            self.issuer,
            self.broker_alias,
            self.external_tenant_id,
            self.hosted_domains,
            self.identity_mode,
            self.client_id,
        )


class OperatorContactInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    tenant_id: str = Field(min_length=1, max_length=64)
    identity: ContactIdentity
    email: str = Field(min_length=3, max_length=320, repr=False)
    display_name: str = Field(min_length=1, max_length=120)
    source: Literal["microsoft_graph_v1", "keycloak_admin", "google_admin"]
    account_enabled: bool | None = Field(default=None, strict=True)
    observed_at: AwareDatetime
    expires_at: AwareDatetime

    @field_validator("email")
    @classmethod
    def validated_address(cls, value):
        parsed = delivery_address(value)
        if parsed is None:
            raise ValueError("Supply the operator-verified directory delivery address")
        return parsed

    @field_validator("display_name")
    @classmethod
    def safe_name(cls, value):
        if value != value.strip() or any(ord(char) < 32 or ord(char) == 127 for char in value):
            raise ValueError("Supply a safe verified display name")
        return value

    @model_validator(mode="after")
    def verified_source(self):
        if (
            self.account_enabled is False
            or self.source
            != {
                "entra": "microsoft_graph_v1",
                "keycloak": "keycloak_admin",
                "google_workspace": "google_admin",
            }[self.identity.kind]
        ):
            raise ValueError("Use its authoritative directory observation; a disabled account is ineligible")
        return self
