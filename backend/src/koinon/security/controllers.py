# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0


from pyfly.container import rest_controller
from pyfly.web import get_mapping, request_mapping
from starlette.requests import Request
from starlette.responses import JSONResponse

from koinon.security.identity import identity_from_request


@rest_controller
@request_mapping("/auth")
class AuthController:
    @get_mapping("/me")
    async def me(self, request: Request) -> JSONResponse:
        identity = identity_from_request(request)
        return JSONResponse(
            {
                "subject": identity.subject,
                "authenticated": identity.authenticated,
                "authentication_method": identity.authentication_method,
            },
            headers={"Cache-Control": "no-store"},
        )
