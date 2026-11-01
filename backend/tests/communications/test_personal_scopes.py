# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import pytest
from pyfly.security.context import SecurityContext
from starlette.requests import Request

from koinon.catalog.errors import AccessDenied
from koinon.profiles.security import require_personal_permission
from koinon.tokens.service import DEPENDENCIES, PERSONAL_SCOPES


def request(scopes):
    value = Request({"type": "http", "path": "/api/v1/notifications", "headers": []})
    value.state.security_context = SecurityContext(
        user_id="person",
        attributes={"iss": "https://issuer.test", "sub": "person", "koinon_token": {"scopes": scopes}},
    )
    return value


def test_notification_scopes_are_explicit_personal_and_write_implies_read():
    assert {"notifications:read", "notifications:write"} <= PERSONAL_SCOPES
    assert DEPENDENCIES["notifications:write"] == {"notifications:read"}
    assert (
        require_personal_permission(request(["notifications:write"]), "notifications:read").subject
        == "https://issuer.test|person"
    )
    with pytest.raises(AccessDenied):
        require_personal_permission(request(["profile:read"]), "notifications:read")
    with pytest.raises(AccessDenied):
        require_personal_permission(request(["notifications:read"]), "notifications:write")
