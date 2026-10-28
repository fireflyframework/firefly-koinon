# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Application policy for claims already authenticated by native OIDC validation."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal, get_args
from uuid import UUID

from pyfly.kernel import ServiceUnavailableException

from koinon.catalog.dtos import Role
from koinon.catalog.errors import AccessDenied


@dataclass(frozen=True, slots=True)
class IdentityPolicy:
    provider_id: str
    kind: Literal["keycloak", "entra", "google_workspace"]
    canonical_issuer: str
    broker_alias: str | None
    external_tenant_id: str | None = None
    hosted_domains: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CorporateIdentity:
    subject: str
    external_subject: str
    requires_directory: bool


def _reject():
    return AccessDenied(
        "The verified identity does not match this corporate connection.", code="IDENTITY_PROVIDER_MISMATCH"
    )


def _text(claims: dict, name: str) -> str:
    value = claims.get(name)
    if not isinstance(value, str) or not value or len(value) > 512:
        raise _reject()
    return value


def verified_identity(policy: IdentityPolicy, claims: dict) -> CorporateIdentity:
    issuer, subject = _text(claims, "iss"), _text(claims, "sub")
    if issuer != policy.canonical_issuer or len(issuer + "|" + subject) > 512:
        raise _reject()
    if claims.get("koinon_identity_provider") != policy.broker_alias:
        raise _reject()
    if policy.kind == "keycloak":
        external = _text(claims, "koinon_external_subject") if policy.broker_alias else subject
    elif policy.kind == "entra":
        try:
            tenant = str(UUID(_text(claims, "koinon_external_tid")))
            expected = str(UUID(policy.external_tenant_id or ""))
            external = str(UUID(_text(claims, "koinon_external_oid")))
        except ValueError as exc:
            raise _reject() from exc
        if not policy.broker_alias or tenant != expected:
            raise _reject()
    elif policy.kind == "google_workspace":
        domain = _text(claims, "koinon_google_hd").casefold()
        if not policy.broker_alias or domain not in {value.casefold() for value in policy.hosted_domains}:
            raise _reject()
        external = _text(claims, "koinon_external_subject")
    else:
        raise _reject()
    claim_names = claims.get("_claim_names")
    overage = (
        claims.get("hasgroups") is True
        or claims.get("koinon_groups_overage") is True
        or (isinstance(claim_names, dict) and "groups" in claim_names)
    )
    return CorporateIdentity(issuer + "|" + subject, external, overage)


@dataclass(frozen=True, slots=True)
class MappingRule:
    id: str
    group_id: str
    role: Role
    workspace_id: str | None
    enabled: bool = True


@dataclass(frozen=True, slots=True)
class DirectorySnapshot:
    external_subject: str
    groups: frozenset[str]
    complete: bool
    observed_at: datetime
    expires_at: datetime


def planned_grants(
    rules: list[MappingRule],
    snapshot: DirectorySnapshot | None,
    *,
    expected_subject: str,
    now: datetime,
    active: bool = True,
    max_age_seconds: int = 300,
) -> list[MappingRule]:
    if not active:
        return []
    if (
        snapshot is None
        or snapshot.complete is not True
        or snapshot.external_subject != expected_subject
        or not expected_subject
    ):
        raise ServiceUnavailableException(
            "Corporate group membership could not be verified.", code="IDENTITY_DIRECTORY_UNVERIFIED"
        )
    if (
        not 1 <= max_age_seconds <= 300
        or any(value.utcoffset() is None for value in (now, snapshot.observed_at, snapshot.expires_at))
        or snapshot.expires_at <= now
        or snapshot.observed_at > now + timedelta(seconds=30)
        or snapshot.expires_at <= snapshot.observed_at
        or (snapshot.expires_at - snapshot.observed_at).total_seconds() > max_age_seconds
        or len(snapshot.groups) > 10000
        or any(not isinstance(group, str) or not 1 <= len(group) <= 256 for group in snapshot.groups)
    ):
        raise ServiceUnavailableException(
            "Corporate group membership needs a fresh complete observation.",
            code="IDENTITY_DIRECTORY_UNVERIFIED",
        )
    selected = []
    for rule in rules:
        if rule.enabled and rule.group_id in snapshot.groups:
            if rule.role not in get_args(Role):
                raise ServiceUnavailableException(
                    "Corporate access mapping is invalid.", code="IDENTITY_MAPPING_INVALID"
                )
            selected.append(rule)
    return sorted(selected, key=lambda rule: rule.id)
