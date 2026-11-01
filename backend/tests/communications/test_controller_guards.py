# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pyfly.security.context import SecurityContext
from starlette.requests import Request

from koinon.catalog.errors import AccessDenied
from koinon.communications.controllers import CommunicationsController, NotificationController


def request(scopes=None):
    value = Request({"type": "http", "path": "/api/v1/notifications", "headers": []})
    attributes = {"iss": "https://issuer.test", "sub": "owner"}
    if scopes is not None:
        attributes["koinon_token"] = {"scopes": scopes}
    value.state.security_context = SecurityContext(user_id="owner", attributes=attributes)
    return value


async def test_owner_inbox_requires_explicit_personal_scope_and_never_accepts_owner_parameter():
    service = SimpleNamespace(page=AsyncMock(return_value="own"), update_preferences=AsyncMock())
    controller = NotificationController(service)
    with pytest.raises(AccessDenied):
        await controller.page(request(["profile:read"]))
    assert await controller.page(request(["notifications:read"])) == "own"
    assert service.page.await_args.args == ("https://issuer.test|owner",)
    with pytest.raises(AccessDenied):
        await controller.preferences_update(None, request(["notifications:read"]))
    service.update_preferences.assert_not_awaited()


async def test_email_acceptance_preserves_interactive_credential_guard_before_any_directory_lookup():
    invitations = SimpleNamespace(accept=AsyncMock())
    controller = CommunicationsController(None, invitations, None, None)
    with pytest.raises(AccessDenied):
        await controller.accept("uuid", request(["members:write"]))
    invitations.accept.assert_not_awaited()
