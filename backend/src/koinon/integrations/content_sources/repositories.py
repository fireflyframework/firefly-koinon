# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Short primary units and fenced credential rotation, with no provider I/O."""

from datetime import UTC, datetime
from typing import cast

from pyfly.container import repository
from pyfly.data.relational.sqlalchemy import Repository
from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult

from koinon.integrations.content_sources.entities import (
    PersonalSourceConnection,
    SourceAuthorizationChallenge,
)


@repository(name="content_sources.connection_repository")
class SourceConnectionRepository(Repository[PersonalSourceConnection, str]):
    @staticmethod
    def _owner(tenant_id, owner, identifier):
        return (
            PersonalSourceConnection.id == identifier,
            PersonalSourceConnection.tenant_id == tenant_id,
            PersonalSourceConnection.owner == owner,
        )

    async def owned(
        self, tenant_id: str, owner: str, identifier: str, *, lock: bool = False
    ) -> PersonalSourceConnection | None:
        statement = select(PersonalSourceConnection).where(
            *self._owner(tenant_id, owner, identifier),
        )
        if lock:
            statement = statement.with_for_update().execution_options(populate_existing=True)
        return await self._require_session().scalar(statement)

    async def complete_authorization(
        self,
        tenant,
        owner,
        identifier,
        revision,
        config_fingerprint,
        account,
        issuer,
        scopes,
        ciphertext,
    ):
        result = await self._require_session().execute(
            update(PersonalSourceConnection)
            .where(
                *self._owner(tenant, owner, identifier),
                PersonalSourceConnection.revision == revision,
                PersonalSourceConnection.config_fingerprint == config_fingerprint,
                PersonalSourceConnection.provider == account.provider,
                PersonalSourceConnection.status == "pending",
            )
            .values(
                status="connected",
                revision=revision + 1,
                external_subject=account.subject,
                external_tenant=account.tenant_id,
                issuer=issuer,
                scopes=list(scopes),
                secret_ciphertext=ciphertext,
                updated_at=datetime.now(UTC),
            )
        )
        return cast(CursorResult, result).rowcount == 1

    async def reserve_refresh(self, tenant_id, owner, identifier, revision, operation, expires_at):
        now = datetime.now(UTC)
        if expires_at <= now or not operation:
            raise ValueError("A future refresh deadline and operation identity are required")
        result = await self._require_session().execute(
            update(PersonalSourceConnection)
            .where(
                *self._owner(tenant_id, owner, identifier),
                PersonalSourceConnection.revision == revision,
                PersonalSourceConnection.status == "connected",
                # An expired rotation may have consumed the remote refresh token. Reconnect instead of replay.
                PersonalSourceConnection.refresh_operation.is_(None),
            )
            .values(refresh_operation=operation, refresh_expires_at=expires_at, updated_at=now)
        )
        return cast(CursorResult, result).rowcount == 1

    async def complete_refresh(self, tenant_id, owner, identifier, revision, operation, ciphertext, scopes):
        now = datetime.now(UTC)
        result = await self._require_session().execute(
            update(PersonalSourceConnection)
            .where(
                *self._owner(tenant_id, owner, identifier),
                PersonalSourceConnection.revision == revision,
                PersonalSourceConnection.status == "connected",
                PersonalSourceConnection.refresh_operation == operation,
                PersonalSourceConnection.refresh_expires_at > now,
            )
            .values(
                secret_ciphertext=ciphertext,
                scopes=list(scopes),
                revision=revision + 1,
                refresh_operation=None,
                refresh_expires_at=None,
                updated_at=now,
            )
        )
        return cast(CursorResult, result).rowcount == 1

    async def disconnect(self, tenant_id, owner, identifier, revision):
        result = await self._require_session().execute(
            update(PersonalSourceConnection)
            .where(
                *self._owner(tenant_id, owner, identifier),
                PersonalSourceConnection.revision == revision,
            )
            .values(
                status="disconnected",
                secret_ciphertext=None,
                revision=revision + 1,
                refresh_operation=None,
                refresh_expires_at=None,
                updated_at=datetime.now(UTC),
            )
        )
        return cast(CursorResult, result).rowcount == 1


@repository(name="content_sources.challenge_repository")
class SourceChallengeRepository(Repository[SourceAuthorizationChallenge, str]):
    async def complete(self, tenant, owner, identifier, session_hash):
        result = await self._require_session().execute(
            update(SourceAuthorizationChallenge)
            .where(
                SourceAuthorizationChallenge.id == identifier,
                SourceAuthorizationChallenge.tenant_id == tenant,
                SourceAuthorizationChallenge.owner == owner,
                SourceAuthorizationChallenge.session_hash == session_hash,
                SourceAuthorizationChallenge.status == "exchanging",
                SourceAuthorizationChallenge.expires_at > datetime.now(UTC),
            )
            .values(status="completed", secret_ciphertext=None)
        )
        return cast(CursorResult, result).rowcount == 1

    async def consume(self, tenant, owner, identifier, session_hash, state_hash, config_fingerprint):
        result = await self._require_session().execute(
            update(SourceAuthorizationChallenge)
            .where(
                SourceAuthorizationChallenge.id == identifier,
                SourceAuthorizationChallenge.tenant_id == tenant,
                SourceAuthorizationChallenge.owner == owner,
                SourceAuthorizationChallenge.session_hash == session_hash,
                SourceAuthorizationChallenge.state_hash == state_hash,
                SourceAuthorizationChallenge.config_fingerprint == config_fingerprint,
                SourceAuthorizationChallenge.status == "pending",
                SourceAuthorizationChallenge.expires_at > datetime.now(UTC),
            )
            .values(status="exchanging")
        )
        return cast(CursorResult, result).rowcount == 1
