# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Installation-owned client registrations; no credentials supplied by a browser."""

import hashlib
import json
from dataclasses import dataclass, field
from typing import cast

from pyfly.container import component

from koinon.integrations.content_sources.dtos import Provider, bounded
from koinon.integrations.content_sources.errors import SourceError
from koinon.integrations.content_sources.oauth import SourceOAuthConfig
from koinon.integrations.content_sources.settings import ContentSourceSettings


@dataclass(frozen=True, slots=True)
class SourceRegistration:
    config: SourceOAuthConfig
    client_secret: str = field(repr=False)
    fingerprint: str = field(repr=False)


@component(name="content_sources.registrations")
class SourceRegistrations:
    def __init__(self, settings: ContentSourceSettings):
        self.settings = settings

    def get(self, provider: str) -> SourceRegistration:
        try:
            values = dict(self.settings.providers[provider])
            if set(values) - {
                "client_id",
                "client_secret",
                "redirect_uri",
                "tenant_id",
                "allow_loopback_http",
            }:
                raise ValueError
            local_http = values.get("allow_loopback_http", False)
            if type(local_http) is not bool or any(
                type(value) is not str for key, value in values.items() if key != "allow_loopback_http"
            ):
                raise ValueError
            config = SourceOAuthConfig(
                cast(Provider, provider),
                cast(str, values["client_id"]),
                cast(str, values["redirect_uri"]),
                cast(str | None, values.get("tenant_id")),
                allow_loopback_http=local_http,
            )
            secret = bounded(values["client_secret"], limit=16384)
            fingerprint = hashlib.sha256(
                json.dumps([provider, values], sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            return SourceRegistration(config, secret, fingerprint)
        except (KeyError, ValueError, TypeError):
            raise SourceError("unavailable") from None

    def require_current(self, registration: SourceRegistration) -> None:
        current = self.get(registration.config.provider)
        if current.fingerprint != registration.fingerprint:
            raise SourceError("reconnect_required")
