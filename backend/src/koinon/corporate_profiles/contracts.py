# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Immutable verified binding and leased observation contracts."""

from dataclasses import dataclass, field
from datetime import UTC, datetime

from koinon.corporate_identity.dtos import ProviderSettings
from koinon.corporate_profiles.dtos import CorporateProfileSyncPolicy


@dataclass(frozen=True, slots=True)
class ProfileLease:
    id: str
    tenant_id: str
    worker_id: str
    generation: int


@dataclass(frozen=True, slots=True)
class ProfileTicket:
    lease: ProfileLease
    subject: str
    provider_id: str
    external_subject: str
    binding_revision: int
    provider_revision: int
    mapping_revision: int
    preference_revision: int
    position_facts: tuple
    fingerprint: str
    policy: CorporateProfileSyncPolicy
    settings: ProviderSettings
    ciphertext: bytes | None = field(repr=False)


def facts(person):
    return (
        (
            person.id,
            person.revision,
            person.provider_id,
            person.external_subject,
            tuple(sorted(person.managed_fields)),
        )
        if person
        else (None, 0, None, None, ())
    )


def owns(row, lease):
    return bool(
        row
        and row.status != "conflict"
        and row.tenant_id == lease.tenant_id
        and row.worker_id == lease.worker_id
        and row.lease_generation == lease.generation
        and row.lease_until is not None
        and row.lease_until > datetime.now(UTC)
    )


@dataclass(frozen=True, slots=True)
class BindingWrite:
    provider_id: str
    external_subject: str
    fingerprint: str
    verified_domain: str | None
    verified_external_tenant: str | None
    binding_revision: int
    revision: int
    observed_at: datetime
