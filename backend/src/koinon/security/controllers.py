# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import asyncio
import inspect
import logging
import math
from datetime import UTC, datetime

from pyfly.container import rest_controller
from pyfly.security.context import SecurityContext
from pyfly.session import HttpSession, SessionStore
from pyfly.web import get_mapping, request_mapping
from starlette.requests import Request
from starlette.responses import JSONResponse

from koinon.security.dtos import BrowserSessionView
from koinon.security.identity import identity_from_request

logger = logging.getLogger(__name__)


@rest_controller
@request_mapping("/auth")
class AuthController:
    def __init__(self, sessions: SessionStore | None = None):
        self.sessions = sessions

    @get_mapping("/me")
    async def me(self, request: Request) -> JSONResponse:
        identity = identity_from_request(request)
        expires_at = None
        authenticated_at = None
        session = getattr(request.state, "session", None)
        observe = getattr(self.sessions, "expires_at", None)
        if (
            identity.authentication_method == "oidc-session"
            and isinstance(session, HttpSession)
            and not session.is_new
            and not session.invalidated
        ):
            stored = session.get_attribute("SECURITY_CONTEXT")
            if (
                callable(observe)
                and isinstance(stored, SecurityContext)
                and f"{stored.attributes.get('iss')}|{stored.attributes.get('sub')}" == identity.subject
                and stored.user_id == stored.attributes.get("sub")
            ):
                try:
                    observation = observe(session.id)
                    if not inspect.isawaitable(observation):
                        raise TypeError("Session expiry capability must be asynchronous")
                    value = await asyncio.wait_for(observation, timeout=2)
                    if isinstance(value, datetime) and value.utcoffset() is not None:
                        expires_at = value.astimezone(UTC)
                    observed_login = getattr(session, "authenticated_at", None)
                    if (
                        isinstance(observed_login, (int, float))
                        and math.isfinite(observed_login)
                        and observed_login > 0
                    ):
                        authenticated_at = datetime.fromtimestamp(observed_login, UTC)
                except Exception as error:
                    logger.warning("session_expiry_unavailable", extra={"error_type": type(error).__name__})
        return JSONResponse(
            BrowserSessionView(
                subject=identity.subject,
                authenticated=identity.authenticated,
                authentication_method=identity.authentication_method,
                expires_at=expires_at,
                authenticated_at=authenticated_at,
                server_time=datetime.now(UTC),
            ).model_dump(mode="json"),
            headers={"Cache-Control": "no-store"},
        )
