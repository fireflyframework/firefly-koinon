# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from types import SimpleNamespace
from unittest.mock import AsyncMock

from pyfly.container.ordering import HIGHEST_PRECEDENCE
from pyfly.security.context import SecurityContext
from starlette.requests import Request
from starlette.responses import Response

from koinon.corporate_identity.filter import CorporateAccessRefreshFilter


async def test_verified_request_refresh_precedes_business_units_and_never_uses_anonymous_claims():
    refresh = SimpleNamespace(subject=AsyncMock())
    gate = CorporateAccessRefreshFilter(refresh)
    assert HIGHEST_PRECEDENCE + 250 < gate.__pyfly_order__ < HIGHEST_PRECEDENCE + 300
    request = Request({"type": "http", "method": "GET", "path": "/api/v1/context", "headers": []})
    request.state.security_context = SecurityContext(
        user_id="preserved", attributes={"iss": "https://identity.test", "sub": "preserved"}
    )

    async def next_handler(request):
        refresh.subject.assert_awaited_once_with("https://identity.test|preserved")
        return Response(status_code=204)

    assert (await gate.do_filter(request, next_handler)).status_code == 204
    refresh.subject.reset_mock()
    request.state.security_context = SecurityContext.anonymous()

    async def anonymous_handler(request):
        return Response(status_code=401)

    assert (await gate.do_filter(request, anonymous_handler)).status_code == 401
    refresh.subject.assert_not_called()
