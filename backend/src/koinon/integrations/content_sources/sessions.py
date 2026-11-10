# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Read current native session authority without borrowing its OAuth credentials."""

from pyfly.container import component
from pyfly.security.context import SecurityContext
from pyfly.session.ports.outbound import SessionStore

from koinon.integrations.content_sources.dtos import bounded
from koinon.integrations.content_sources.errors import SourceError


@component(name="content_sources.browser_sessions")
class SourceBrowserSessions:
    def __init__(self, store: SessionStore):
        self.store = store

    async def require(self, actor: str, session_id: str) -> None:
        snapshot = await self.store.get(bounded(session_id, limit=256))
        context = snapshot.get("SECURITY_CONTEXT") if snapshot else None
        if not isinstance(context, SecurityContext) or not context.is_authenticated:
            raise SourceError("access_denied")
        issuer, subject = context.attributes.get("iss"), context.attributes.get("sub")
        if (
            not issuer
            or not subject
            or context.user_id != subject
            or f"{issuer}|{subject}" != actor
            or "koinon_token" in context.attributes
            or "koinon_token_id" in context.attributes
        ):
            raise SourceError("access_denied")
