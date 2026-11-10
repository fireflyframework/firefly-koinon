# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Personal delegated grant acquisition with durable one-use and rotation fences."""

import hashlib
import secrets
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import uuid4

from pyfly.container import service
from pyfly.data.transaction import current_unit_of_work
from pyfly.oauth2 import generate_pkce

from koinon.catalog.errors import AccessDenied
from koinon.catalog.service import CatalogService
from koinon.integrations.content_sources.credentials import SourceCredentialVault
from koinon.integrations.content_sources.dtos import Account, Provider, bounded
from koinon.integrations.content_sources.entities import (
    PersonalSourceConnection,
    SourceAuthorizationChallenge,
)
from koinon.integrations.content_sources.errors import SourceError
from koinon.integrations.content_sources.identity import SourceIdentityVerifier
from koinon.integrations.content_sources.oauth import ReadOnlySourceOAuth
from koinon.integrations.content_sources.registrations import SourceRegistration, SourceRegistrations
from koinon.integrations.content_sources.repositories import (
    SourceChallengeRepository,
    SourceConnectionRepository,
)
from koinon.integrations.content_sources.sessions import SourceBrowserSessions
from koinon.security.authority import primary_authority


def _hash(value: str) -> str:
    return hashlib.sha256(bounded(value, limit=4096).encode()).hexdigest()


def _no_remote_unit() -> None:
    for name in ("primary", "canon", "structured"):
        unit = current_unit_of_work(name)
        if unit is not None and not unit.completed:
            raise SourceError("unavailable")


@dataclass(frozen=True, slots=True)
class SourceAuthorizationStart:
    connection_id: str
    challenge_id: str
    authorization_url: str = field(repr=False)
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class PersonalConnection:
    id: str
    provider: str
    status: str
    revision: int
    account: Account | None


@dataclass(frozen=True, slots=True)
class SourceReadGrant:
    tenant: str
    owner: str
    connection_id: str
    account: Account
    revision: int
    config_fingerprint: str = field(repr=False)
    scopes: tuple[str, ...]
    token: str = field(repr=False)


def connection_view(row: PersonalSourceConnection) -> PersonalConnection:
    account = (
        Account(cast(Provider, row.provider), row.external_subject, row.external_tenant)
        if row.external_subject
        else None
    )
    return PersonalConnection(row.id, row.provider, row.status, row.revision, account)


@service(name="content_sources.connections")
class SourceConnectionService:
    def __init__(
        self,
        connections: SourceConnectionRepository,
        challenges: SourceChallengeRepository,
        vault: SourceCredentialVault,
        registrations: SourceRegistrations,
        catalog: CatalogService,
        sessions: SourceBrowserSessions,
    ):
        self.connections, self.challenges = connections, challenges
        self.vault, self.registrations, self.catalog = vault, registrations, catalog
        self.sessions = sessions

    def _oauth(self, registration: SourceRegistration):
        return ReadOnlySourceOAuth(registration.config, client_secret=registration.client_secret)

    def _identity(self, registration: SourceRegistration):
        return SourceIdentityVerifier(registration.config)

    async def _authorize(self, actor, tenant):
        _no_remote_unit()
        await self.catalog._refresh_managed_memberships(actor)
        async with primary_authority():
            await self._member(actor, tenant)

    async def _member(self, actor, tenant):
        memberships = await self.catalog.memberships(actor)
        grant = await self.catalog.restriction.grant(actor) if self.catalog.restriction else None
        for workspace in {row.workspace_id for row in memberships if row.tenant_id == tenant}:
            if "catalog:read" in self.catalog._resolved_permissions(memberships, tenant, workspace, grant):
                await self.catalog._validate_workspace(tenant, workspace)
                return
        raise AccessDenied("Source connections require current organization access.", code="ACCESS_DENIED")

    async def begin(
        self, actor: str, tenant: str, session: str, provider: Provider
    ) -> SourceAuthorizationStart:
        await self.sessions.require(actor, session)
        await self._authorize(actor, tenant)
        registration = self.registrations.get(provider)
        identifier, challenge_id = str(uuid4()), str(uuid4())
        pkce = generate_pkce()
        nonce, state = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        expires = datetime.now(UTC) + timedelta(minutes=5)
        ciphertext = self.vault.encrypt(
            tenant,
            actor,
            identifier,
            "authorization",
            {
                "verifier": pkce.verifier,
                "nonce": nonce,
            },
        )
        async with self._oauth(registration) as oauth:
            url = oauth.authorization_url(state=state, code_challenge=pkce.challenge, nonce=nonce)
        async with primary_authority(read_only=False):
            await self._member(actor, tenant)
            await self.sessions.require(actor, session)
            self.registrations.require_current(registration)
            await self.connections.save(
                PersonalSourceConnection(
                    id=identifier,
                    tenant_id=tenant,
                    owner=actor,
                    provider=provider,
                    status="pending",
                    revision=1,
                    config_fingerprint=registration.fingerprint,
                )
            )
            await self.challenges.save(
                SourceAuthorizationChallenge(
                    id=challenge_id,
                    connection_id=identifier,
                    tenant_id=tenant,
                    owner=actor,
                    session_hash=_hash(session),
                    state_hash=_hash(state),
                    config_fingerprint=registration.fingerprint,
                    connection_revision=1,
                    secret_ciphertext=ciphertext,
                    expires_at=expires,
                    status="pending",
                )
            )
        return SourceAuthorizationStart(identifier, challenge_id, url, expires)

    async def _consume(self, actor, tenant, session, identifier, state):
        async with primary_authority(read_only=False):
            await self._member(actor, tenant)
            challenge = await self.challenges.find_by_id(identifier)
            if challenge is None or challenge.tenant_id != tenant or challenge.owner != actor:
                raise SourceError("access_denied")
            row = await self.connections.owned(tenant, actor, challenge.connection_id)
            if row is None or row.status != "pending" or row.revision != challenge.connection_revision:
                raise SourceError("reconnect_required")
            registration = self.registrations.get(row.provider)
            if not await self.challenges.consume(
                tenant,
                actor,
                identifier,
                _hash(session),
                _hash(state),
                registration.fingerprint,
            ):
                raise SourceError("reconnect_required")
            private = self.vault.decrypt(tenant, actor, row.id, "authorization", challenge.secret_ciphertext)
            return row.id, row.revision, registration, private

    @staticmethod
    def _grant(tokens, *, previous=None):
        refresh = tokens.refresh_token or (previous or {}).get("refresh_token")
        if not refresh or tokens.expires_in is None or tokens.expires_in <= 0:
            raise SourceError("reconnect_required")
        return {
            "access_token": tokens.access_token,
            "refresh_token": refresh,
            "expires_at": (datetime.now(UTC) + timedelta(seconds=tokens.expires_in)).timestamp(),
        }

    async def complete(
        self, actor: str, tenant: str, session: str, identifier: str, *, state: str, code: str
    ):
        await self.sessions.require(actor, session)
        await self._authorize(actor, tenant)
        connection_id, revision, registration, private = await self._consume(
            actor, tenant, session, identifier, state
        )
        # The consumed challenge is committed before any provider call. Unknown outcomes need new consent.
        try:
            _no_remote_unit()
            async with self._oauth(registration) as oauth:
                tokens = await oauth.exchange_code(code, code_verifier=private["verifier"])
            if not tokens.id_token:
                raise SourceError("invalid_identity")
            async with self._identity(registration) as verifier:
                account = await verifier.verify(tokens.id_token, nonce=private["nonce"])
                issuer = verifier.issuer
            ciphertext = self.vault.encrypt(tenant, actor, connection_id, "grant", self._grant(tokens))
        except SourceError:
            raise
        except Exception:
            raise SourceError("reconnect_required") from None
        await self._authorize(actor, tenant)
        async with primary_authority(read_only=False):
            await self._member(actor, tenant)
            await self.sessions.require(actor, session)
            self.registrations.require_current(registration)
            if not await self.connections.complete_authorization(
                tenant,
                actor,
                connection_id,
                revision,
                registration.fingerprint,
                account,
                issuer,
                (tokens.scope or "").split(),
                ciphertext,
            ):
                raise SourceError("reconnect_required")
            if not await self.challenges.complete(tenant, actor, identifier, _hash(session)):
                raise SourceError("reconnect_required")
            row = await self.connections.owned(tenant, actor, connection_id)
            return connection_view(row)

    async def disconnect(self, actor, tenant, identifier, revision):
        await self._authorize(actor, tenant)
        async with primary_authority(read_only=False):
            await self._member(actor, tenant)
            if not await self.connections.disconnect(tenant, actor, identifier, revision):
                raise SourceError("access_denied")

    async def connected(self, actor: str, tenant: str, identifier: str) -> PersonalConnection:
        await self._authorize(actor, tenant)
        async with primary_authority():
            await self._member(actor, tenant)
            row = await self.connections.owned(tenant, actor, identifier)
            if row is None or row.status != "connected" or not row.external_subject:
                raise SourceError("access_denied")
            if self.registrations.get(row.provider).fingerprint != row.config_fingerprint:
                raise SourceError("reconnect_required")
            return connection_view(row)

    async def get(self, actor: str, tenant: str, identifier: str) -> PersonalConnection:
        await self._authorize(actor, tenant)
        async with primary_authority():
            await self._member(actor, tenant)
            row = await self.connections.owned(tenant, actor, identifier)
            if row is None:
                raise SourceError("access_denied")
            view = connection_view(row)
            if row.status == "connected":
                try:
                    if self.registrations.get(row.provider).fingerprint != row.config_fingerprint:
                        raise SourceError("reconnect_required")
                    if row.refresh_expires_at is not None and row.refresh_expires_at <= datetime.now(UTC):
                        raise SourceError("reconnect_required")
                except SourceError:
                    view = replace(view, status="reconnect_required")
            return view

    async def access_token(self, actor: str, tenant: str, identifier: str, account: Account) -> str:
        """Internal reader-bound acquisition; never expose this value through an API DTO."""
        return (await self.read_grant(actor, tenant, identifier, account)).token

    async def confirm_read_grant(self, actor: str, tenant: str, identifier: str, grant: SourceReadGrant):
        if (grant.owner, grant.tenant, grant.connection_id) != (actor, tenant, identifier):
            raise SourceError("access_denied")
        await self._authorize(actor, tenant)
        async with primary_authority():
            await self._member(actor, tenant)
            row = await self.connections.owned(tenant, actor, identifier)
            if row is None or row.status != "connected" or connection_view(row).account != grant.account:
                raise SourceError("access_denied")
            if (
                row.config_fingerprint != grant.config_fingerprint
                or self.registrations.get(row.provider).fingerprint != grant.config_fingerprint
            ):
                raise SourceError("reconnect_required")
            if (
                row.revision != grant.revision
                or tuple(row.scopes) != grant.scopes
                or row.refresh_operation is not None
            ):
                raise SourceError("authority_changed")

    async def read_grant(self, actor: str, tenant: str, identifier: str, account: Account) -> SourceReadGrant:
        await self._authorize(actor, tenant)
        async with primary_authority(read_only=False):
            await self._member(actor, tenant)
            row = await self.connections.owned(tenant, actor, identifier)
            if row is None or row.status != "connected" or connection_view(row).account != account:
                raise SourceError("access_denied")
            registration = self.registrations.get(row.provider)
            if row.config_fingerprint != registration.fingerprint or row.refresh_operation is not None:
                raise SourceError("reconnect_required")
            grant = self.vault.decrypt(tenant, actor, identifier, "grant", row.secret_ciphertext)
            if grant["expires_at"] > (datetime.now(UTC) + timedelta(seconds=60)).timestamp():
                return SourceReadGrant(
                    tenant,
                    actor,
                    identifier,
                    account,
                    row.revision,
                    row.config_fingerprint,
                    tuple(row.scopes),
                    grant["access_token"],
                )
            operation, revision, scopes = str(uuid4()), row.revision, tuple(row.scopes)
            if not await self.connections.reserve_refresh(
                tenant, actor, identifier, revision, operation, datetime.now(UTC) + timedelta(seconds=60)
            ):
                raise SourceError("reconnect_required")
        try:
            _no_remote_unit()
            async with self._oauth(registration) as oauth:
                tokens = await oauth.refresh_token(grant["refresh_token"], granted_scopes=scopes)
            ciphertext = self.vault.encrypt(
                tenant, actor, identifier, "grant", self._grant(tokens, previous=grant)
            )
        except SourceError:
            raise
        except Exception:
            raise SourceError("reconnect_required") from None
        await self._authorize(actor, tenant)
        async with primary_authority(read_only=False):
            await self._member(actor, tenant)
            self.registrations.require_current(registration)
            if not await self.connections.complete_refresh(
                tenant, actor, identifier, revision, operation, ciphertext, (tokens.scope or "").split()
            ):
                raise SourceError("reconnect_required")
        return SourceReadGrant(
            tenant,
            actor,
            identifier,
            account,
            revision + 1,
            registration.fingerprint,
            tuple((tokens.scope or "").split()),
            tokens.access_token,
        )
