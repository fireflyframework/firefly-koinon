# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from koinon.tokens.entities import PersonalToken


def token_dto(row: PersonalToken) -> dict:
    return {
        key: getattr(row, key)
        for key in (
            "id",
            "name",
            "tenant_id",
            "prefix",
            "scopes",
            "workspace_ids",
            "asset_ids",
            "expires_at",
            "revoked_at",
            "last_used_at",
            "created_at",
        )
    }
