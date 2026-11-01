# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from typing import Protocol

from pyfly.security.context import SecurityContext
from pyfly.security.oauth2.client import ClientRegistration
from starlette.requests import Request


class BootstrapLoginObserver(Protocol):
    """Called only after the native interactive OIDC callback verifies its ID token."""

    async def observe_login(
        self, request: Request, registration: ClientRegistration, context: SecurityContext
    ) -> None: ...
