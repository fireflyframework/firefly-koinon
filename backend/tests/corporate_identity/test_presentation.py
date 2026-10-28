# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from types import SimpleNamespace
from unittest.mock import AsyncMock

from pyfly.security.context import SecurityContext

from koinon.corporate_identity.presentation import CorporatePresentation


async def test_saved_preferences_and_avatar_are_never_replaced_by_corporate_login():
    profiles = SimpleNamespace(
        profiles=SimpleNamespace(find_by_id=AsyncMock(return_value=object())),
        get=AsyncMock(),
        set_avatar=AsyncMock(),
    )
    providers = SimpleNamespace(find_all=AsyncMock())
    directory = SimpleNamespace(avatar=AsyncMock())
    presentation = CorporatePresentation(providers, directory, None, profiles, None)
    context = SecurityContext(
        user_id="preserved",
        attributes={
            "iss": "https://identity.test",
            "sub": "preserved",
            "name": "Verified name",
            "locale": "es-MX",
            "picture": "http://unsafe.invalid",
        },
    )
    await presentation.initialize(context)
    profiles.get.assert_awaited_once_with("https://identity.test|preserved", context.attributes)
    providers.find_all.assert_not_called()
    directory.avatar.assert_not_called()
    profiles.set_avatar.assert_not_called()
