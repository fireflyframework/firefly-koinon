# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Verify content-grant identity separately from the application's sign-in session."""

import hmac
from dataclasses import dataclass
from typing import Self
from uuid import UUID

from koinon_storage.client_lifecycle import ClientLifecycle
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pyfly.client import HttpxClientAdapter
from pyfly.client.exceptions import ServiceClientException
from pyfly.client.ports.outbound import StreamingHttpClientPort
from pyfly.kernel import SecurityException
from pyfly.security.oauth2.resource_server import JWKSTokenValidator

from koinon.integrations.content_sources.dtos import Account, bounded
from koinon.integrations.content_sources.errors import SourceError
from koinon.integrations.content_sources.oauth import SourceOAuthConfig
from koinon.integrations.content_sources.transport import SourceTransport

_MICROSOFT_CONSUMERS = "9188040d-6c67-4c5b-b112-36a304b66dad"


class SourceDisplayProfile(BaseModel):
    """Presentation from verified claims; never part of account authorization."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    display_name: str | None = Field(default=None, max_length=255)
    display_address: str | None = Field(default=None, max_length=320)
    display_address_verified: bool = False

    @field_validator("display_name", "display_address")
    @classmethod
    def plain(cls, value):
        return bounded(value, limit=320) if value is not None else None

    @classmethod
    def from_verified_claims(cls, provider, claims):
        def text(key, limit):
            try:
                return bounded(claims.get(key), limit=limit).strip() or None
            except ValueError:
                return None

        name, address = text("name", 255), text("email", 320)
        if address is not None and (
            address.count("@") != 1
            or any(character.isspace() for character in address)
            or any(not part for part in address.split("@"))
        ):
            address = None
        return cls(
            display_name=name,
            display_address=address,
            display_address_verified=(
                address is not None and provider == "google_drive" and claims.get("email_verified") is True
            ),
        )


@dataclass(frozen=True, slots=True)
class VerifiedSourceIdentity:
    account: Account
    display: SourceDisplayProfile


class SourceIdentityVerifier:
    def __init__(
        self,
        config: SourceOAuthConfig,
        *,
        http_client: StreamingHttpClientPort | None = None,
        owns_http_client: bool = False,
    ):
        self.config = config
        self.tenant = _MICROSOFT_CONSUMERS if config.tenant_id == "consumers" else config.tenant_id
        self.issuer = (
            "https://accounts.google.com"
            if config.provider == "google_drive"
            else f"https://login.microsoftonline.com/{self.tenant}/v2.0"
        )
        self.jwks_uri = (
            "https://www.googleapis.com/oauth2/v3/certs"
            if config.provider == "google_drive"
            else f"https://login.microsoftonline.com/{self.tenant}/discovery/v2.0/keys"
        )
        self._owns_client = http_client is None or owns_http_client
        self._client = http_client or HttpxClientAdapter(trust_env=False, follow_redirects=False)
        self._lifecycle = ClientLifecycle()
        self._validator = JWKSTokenValidator(
            self.jwks_uri,
            issuer=self.issuer,
            audiences=[config.client_id],
            algorithms=["RS256"],
            leeway=30,
            async_jwks_fetcher=self._fetch,
        )

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_):
        if self._owns_client:
            await self._lifecycle.aclose(self._client.stop)

    async def _fetch(self, uri: str, *, timeout: float, max_bytes: int) -> bytes:
        if uri != self.jwks_uri:
            raise SourceError("invalid_identity")
        async with self._client.stream(
            "GET",
            uri,
            timeout=timeout,
            follow_redirects=False,
            auth=None,
            suppress_cookies=True,
            suppress_authorization=True,
            sanitize_errors=True,
            headers={"Accept-Encoding": "identity"},
        ) as response:
            if (
                response.status_code != 200
                or response.headers.get("content-encoding", "identity") != "identity"
            ):
                raise SourceError("invalid_identity")
            body = bytearray()
            async for chunk in SourceTransport.chunks(response):
                if len(chunk) > max_bytes - len(body):
                    raise SourceError("invalid_identity")
                body.extend(chunk)
            return bytes(body)

    async def verify(self, id_token: str, *, nonce: str) -> Account:
        return (await self.verify_with_profile(id_token, nonce=nonce)).account

    async def verify_with_profile(self, id_token: str, *, nonce: str) -> VerifiedSourceIdentity:
        try:
            bounded(nonce)
            with self._lifecycle.operation():
                claims = await self._validator.validate_async(id_token, timeout=10)
            if (
                not isinstance(claims.get("nonce"), str)
                or not hmac.compare_digest(claims["nonce"], nonce)
                or type(claims.get("iat")) is not int
                or type(claims.get("exp")) is not int
                or claims.get("azp", self.config.client_id) != self.config.client_id
            ):
                raise ValueError
            subject = bounded(claims.get("sub"))
            if self.config.provider != "google_drive":
                if claims.get("tid") != self.tenant:
                    raise ValueError
                subject = str(UUID(claims.get("oid", "")))
            return VerifiedSourceIdentity(
                Account(self.config.provider, subject, self.tenant),
                SourceDisplayProfile.from_verified_claims(self.config.provider, claims),
            )
        except (SecurityException, ServiceClientException, ValueError, TypeError, AttributeError):
            raise SourceError("invalid_identity") from None
