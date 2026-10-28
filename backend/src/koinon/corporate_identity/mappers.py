# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from koinon.corporate_identity.dtos import IdentityProvider
from koinon.corporate_identity.entities import CorporateProvider


def provider_dto(row: CorporateProvider) -> IdentityProvider:
    return IdentityProvider.model_validate(
        {
            **{
                field: getattr(row, field)
                for field in (
                    "id",
                    "tenant_id",
                    "kind",
                    "name",
                    "canonical_issuer",
                    "broker_alias",
                    "ownership",
                    "revision",
                    "policy_revision",
                    "status",
                    "observed_at",
                    "created_at",
                    "updated_at",
                    "created_by",
                    "updated_by",
                )
            },
            "credential_configured": row.secret_ciphertext is not None
            or row.credential_reference is not None,
            "settings": row.settings_json,
            "checks": row.checks_json,
            "capabilities": ["configuration"],
        }
    )
