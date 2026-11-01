# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import json
from datetime import UTC, datetime, timedelta

import pytest
from pyfly.kernel.exceptions import UnauthorizedException
from pyfly.security.context import SecurityContext
from pyfly.session import HttpSession
from starlette.requests import Request

from koinon.security.controllers import AuthController


def request(subject="alice"):
    value = Request({"type": "http", "path": "/auth/me", "method": "GET", "headers": []})
    context = SecurityContext(
        user_id=subject, attributes={"iss": "https://identity.example.test", "sub": subject}
    )
    value.state.security_context = context
    value.state.session = HttpSession("private-session-id", {"SECURITY_CONTEXT": context})
    return value


async def test_authenticated_current_session_exposes_only_actual_expiry_and_server_time():
    deadline = datetime.now(UTC) + timedelta(seconds=60)
    calls = []

    class Expiry:
        async def expires_at(self, session_id):
            calls.append(session_id)
            return deadline

    response = await AuthController(Expiry()).me(request())
    result = json.loads(response.body)
    assert result["expires_at"] == deadline.isoformat().replace("+00:00", "Z")
    assert result["subject"] == "https://identity.example.test|alice"
    assert datetime.fromisoformat(result["server_time"].replace("Z", "+00:00")) <= deadline
    assert calls == ["private-session-id"]
    assert "private-session-id" not in response.body.decode()
    assert set(result) == {
        "subject",
        "authenticated",
        "authentication_method",
        "expires_at",
        "authenticated_at",
        "server_time",
    }
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("store", [None, object()])
async def test_old_or_custom_store_without_expiry_keeps_metadata_unknown(store):
    response = await AuthController(store).me(request())
    assert json.loads(response.body)["expires_at"] is None


async def test_metadata_failure_is_unknown_and_never_exposes_error_content():
    class Unavailable:
        async def expires_at(self, session_id):
            raise RuntimeError("secret credential sentinel")

    response = await AuthController(Unavailable()).me(request())
    assert json.loads(response.body)["expires_at"] is None
    assert "sentinel" not in response.body.decode()


async def test_unauthenticated_or_wrong_principal_cannot_read_session_expiry():
    calls = []

    class Forbidden:
        async def expires_at(self, session_id):
            calls.append(session_id)
            raise AssertionError("Must not inspect another principal's session")

    current = request()
    current.state.security_context = SecurityContext()
    with pytest.raises(UnauthorizedException):
        await AuthController(Forbidden()).me(current)
    current = request()
    current.state.session.set_attribute("SECURITY_CONTEXT", request("bob").state.security_context)
    assert json.loads((await AuthController(Forbidden()).me(current)).body)["expires_at"] is None
    assert calls == []


async def test_bearer_identity_does_not_report_a_matching_cookie_lifetime():
    calls = []

    class Forbidden:
        async def expires_at(self, session_id):
            calls.append(session_id)
            raise AssertionError("Bearer authentication has its own lifetime")

    current = request()
    current.scope["path"] = "/api/v1/session-info"
    result = json.loads((await AuthController(Forbidden()).me(current)).body)
    assert result["authentication_method"] == "bearer"
    assert result["expires_at"] is None
    assert result["authenticated_at"] is None
    assert calls == []
