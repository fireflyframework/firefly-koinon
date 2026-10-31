# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from koinon.corporate_identity.presentation import CorporatePresentation


@pytest.mark.asyncio
async def test_verified_corporate_login_never_imports_photo_into_global_personal_profile():
    profiles = SimpleNamespace(
        profiles=SimpleNamespace(find_by_id=AsyncMock(return_value=None)),
        get=AsyncMock(),
        set_avatar=AsyncMock(),
    )
    provider = SimpleNamespace(
        id="provider",
        tenant_id="north",
        secret_ciphertext=None,
        kind="entra",
        canonical_issuer="https://identity.example",
        broker_alias="company",
        settings_json={
            "kind": "entra",
            "tenant_id": "11111111-1111-4111-8111-111111111111",
            "client_id": "client",
        },
    )
    providers = SimpleNamespace(find_all=AsyncMock(return_value=[provider]))
    directory = SimpleNamespace(
        acquire=AsyncMock(return_value="inert"), avatar=AsyncMock(return_value=b"inert image")
    )
    service = CorporatePresentation(
        providers, directory, object(), profiles, SimpleNamespace(issuer="https://identity.example")
    )
    await service.initialize(
        SimpleNamespace(
            attributes={
                "iss": "https://identity.example",
                "sub": "person",
                "koinon_identity_provider": "company",
                "koinon_external_tid": "11111111-1111-4111-8111-111111111111",
                "koinon_external_oid": "22222222-2222-4222-8222-222222222222",
            },
            user_id="person",
        )
    )
    profiles.get.assert_awaited_once()
    profiles.set_avatar.assert_not_awaited()
