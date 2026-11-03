# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from types import SimpleNamespace

import pytest
from pyfly.kernel import ForbiddenException
from pyfly.security.context import SecurityContext
from pyfly.session.session import HttpSession
from starlette.requests import Request
from test_connection_lifecycle import begin, complete
from test_connection_lifecycle import lifecycle as lifecycle


def request(*, subject="alice", session="browser-a", token=False):
    result = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/bff/api/v1/tenants/tenant/content-sources",
            "headers": [],
            "query_string": b"",
            "scheme": "https",
            "server": ("app.test", 443),
        }
    )
    attributes = {"iss": "issuer", "sub": subject}
    if token:
        attributes["koinon_token_id"] = "personal-api-token"
    result.state.security_context = SecurityContext(user_id=subject, attributes=attributes)
    result.state.session = HttpSession(session)
    return result


async def test_personal_api_never_returns_grants_and_denies_token_consent(lifecycle):
    from koinon.integrations.content_sources.api_dtos import SourceAuthorizationInput
    from koinon.integrations.content_sources.controllers import ContentConnectionsController

    service, _, _, context = lifecycle
    controller = context.get_bean(ContentConnectionsController)
    with pytest.raises(ForbiddenException):
        await controller.begin(
            "tenant", SourceAuthorizationInput(provider="google_drive"), request(token=True)
        )
    start, state = await begin(service)
    await complete(service, start, state)
    result = await controller.get("tenant", start.connection_id, request())
    assert result["status"] == "connected" and result["account"]["subject"] == "verified-alice"
    assert not {"secret_ciphertext", "refresh_token", "access_token", "config_fingerprint"} & set(result)
    with pytest.raises(ForbiddenException):
        await controller.get("tenant", start.connection_id, request(subject="bob"))


async def test_api_session_identifier_comes_only_from_native_request(lifecycle):
    from koinon.integrations.content_sources.api_dtos import SourceAuthorizationInput
    from koinon.integrations.content_sources.controllers import ContentConnectionsController

    _, _, _, context = lifecycle
    controller = context.get_bean(ContentConnectionsController)
    unauthenticated = request()
    unauthenticated.state.session = SimpleNamespace(id="browser-a")
    with pytest.raises(ForbiddenException):
        await controller.begin("tenant", SourceAuthorizationInput(provider="google_drive"), unauthenticated)


async def test_changed_read_authority_has_retryable_read_conflict_without_replay():
    from koinon.integrations.content_sources.controllers import _safe
    from koinon.integrations.content_sources.errors import SourceError
    from pyfly.kernel import ConflictException

    calls = []

    async def read():
        calls.append("read")
        raise SourceError("authority_changed")

    with pytest.raises(ConflictException) as failure:
        await _safe(read())
    assert failure.value.code == "SOURCE_AUTHORITY_CHANGED"
    assert calls == ["read"]
