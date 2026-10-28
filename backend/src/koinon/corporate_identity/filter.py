# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from pyfly.container import component
from pyfly.container.ordering import HIGHEST_PRECEDENCE
from pyfly.kernel import UnauthorizedException
from pyfly.web.filters import OncePerRequestFilter

from koinon.corporate_identity.refresh import CorporateAccessRefresh
from koinon.security.identity import identity_from_request


@component(name="identity.request_refresh")
class CorporateAccessRefreshFilter(OncePerRequestFilter):
    __pyfly_order__ = HIGHEST_PRECEDENCE + 275
    url_patterns = ["/api/v1/*", "/bff/api/v1/*"]

    def __init__(self, refresh: CorporateAccessRefresh):
        self.refresh = refresh

    async def do_filter(self, request, call_next):
        try:
            identity = identity_from_request(request)
        except UnauthorizedException:
            return await call_next(request)
        await self.refresh.subject(identity.subject)
        return await call_next(request)
