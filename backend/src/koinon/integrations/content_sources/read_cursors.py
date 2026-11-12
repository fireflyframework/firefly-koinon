# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Bounded shared continuation positions, never cached source permission."""

import hashlib
import re
import secrets
from datetime import UTC, datetime, timedelta

from pyfly.cache.namespaces import dedicated_cache
from pyfly.cache.ports.outbound import CacheAdapter, CacheCoordination
from pyfly.container import Provider, service
from pyfly.kernel import InvalidRequestException, RateLimitException, ServiceUnavailableException

_TTL = timedelta(minutes=5)


@service(name="content_sources.read_cursors")
class SourceBrowseCursors:
    def __init__(self, cache: Provider[CacheAdapter | None] | None = None):
        self.cache = cache

    def _cache(self, resource):
        if resource not in {"catalog", "exports", "shares", "history"}:
            raise ValueError("Unsupported reader browse resource")
        cache = self.cache.get() if isinstance(self.cache, Provider) else self.cache
        if cache is None:
            raise ServiceUnavailableException(
                "Shared pagination is unavailable", code="SOURCE_CURSOR_UNAVAILABLE"
            )
        return dedicated_cache(cache, "koinon.reader_browse." + resource)

    @staticmethod
    def restart():
        return InvalidRequestException(
            "This page expired or its selection changed; restart browsing.", code="SOURCE_CURSOR_EXPIRED"
        )

    async def read(self, actor, tenant, binding, cursor, *, resource="catalog"):
        if cursor is None:
            return 1
        if not isinstance(cursor, str) or re.fullmatch(r"[A-Za-z0-9_-]{43}", cursor) is None:
            raise self.restart()
        try:
            value = await self._cache(resource).get(cursor)
        except Exception:
            raise self.restart() from None
        if (
            not isinstance(value, dict)
            or value.get("binding") != binding
            or value.get("actor") != actor
            or value.get("tenant") != tenant
            or value.get("resource") != resource
            or type(value.get("expires")) not in {int, float}
            or value["expires"] <= datetime.now(UTC).timestamp()
            or type(value.get("position")) is not int
            or not 1 <= value["position"] <= 1000000
        ):
            raise self.restart()
        return value["position"]

    async def issue(self, actor, tenant, binding, position, *, resource="catalog"):
        if type(position) is not int or not 1 <= position <= 1000000:
            raise self.restart()
        cache = self._cache(resource)
        if not isinstance(cache, CacheCoordination):
            raise ServiceUnavailableException(
                "Shared pagination is unavailable", code="SOURCE_CURSOR_UNAVAILABLE"
            )
        key = "issuance:" + hashlib.sha256((tenant + "\0" + actor).encode()).hexdigest()
        if not await cache.consume_window(key, 100, _TTL):
            raise RateLimitException("Restart browsing in a few minutes", code="SOURCE_CURSOR_LIMIT")
        cursor = secrets.token_urlsafe(32)
        stored = await cache.put_if_absent(
            cursor,
            {
                "binding": binding,
                "actor": actor,
                "tenant": tenant,
                "resource": resource,
                "position": position,
                "expires": (datetime.now(UTC) + _TTL).timestamp(),
            },
            ttl=_TTL,
        )
        if not stored:
            raise ServiceUnavailableException("Continuation is unavailable", code="SOURCE_CURSOR_UNAVAILABLE")
        return cursor
