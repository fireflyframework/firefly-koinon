# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Read current native session authority without borrowing its OAuth credentials."""

import asyncio
import inspect
from datetime import UTC, datetime

from pyfly.container import component
from pyfly.security.context import SecurityContext
from pyfly.session.ports.outbound import SessionStore

from koinon.integrations.content_sources.dtos import bounded
from koinon.integrations.content_sources.errors import SourceError


@component(name="content_sources.browser_sessions")
class SourceBrowserSessions:
    def __init__(self, store: SessionStore):
        self.store = store

    async def require_with_expiry(self, actor: str, session_id: str) -> datetime:
        """Observe a finite store deadline without saving or renewing the session."""
        await self.require(actor, session_id)
        observe = getattr(self.store, "expires_at", None)
        if not callable(observe):
            raise SourceError("unavailable")
        try:
            observation = observe(session_id)
            if not inspect.isawaitable(observation):
                raise TypeError("Session expiry observation must be asynchronous")
            expiry = await asyncio.wait_for(observation, timeout=2)
        except Exception:
            raise SourceError("unavailable") from None
        if not isinstance(expiry, datetime) or expiry.utcoffset() is None or expiry <= datetime.now(UTC):
            raise SourceError("access_denied")
        # Observation is not authority: logout or identity replacement may have raced it.
        await self.require(actor, session_id)
        return expiry.astimezone(UTC)

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
