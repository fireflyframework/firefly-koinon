# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Durable owner and revision fences using actual SQL statements and SQLite."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


@pytest.fixture
async def stored(tmp_path):
    from koinon.catalog.entities import Tenant
    from koinon.integrations.content_sources.entities import PersonalSourceConnection
    from koinon.integrations.content_sources.repositories import SourceConnectionRepository
    from pyfly.data.relational.sqlalchemy import Base

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'sources.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        session.add(Tenant(id="tenant", name="Tenant"))
        session.add(
            PersonalSourceConnection(
                id="connection",
                tenant_id="tenant",
                owner="issuer|alice",
                provider="google_drive",
                status="connected",
                revision=1,
                external_subject="provider-alice",
                issuer="https://accounts.google.com",
                secret_ciphertext=b"opaque-ciphertext",
            )
        )
        await session.commit()
        yield SourceConnectionRepository(session=session), session
    await engine.dispose()


async def test_connection_lookup_does_not_expose_another_owner_or_tenant(stored):
    rows, _ = stored
    assert await rows.owned("tenant", "issuer|alice", "connection") is not None
    assert await rows.owned("tenant", "issuer|bob", "connection") is None
    assert await rows.owned("other", "issuer|alice", "connection") is None


async def test_refresh_reservation_serializes_rotation_without_holding_a_network_transaction(stored):
    rows, session = stored
    deadline = datetime.now(UTC) + timedelta(seconds=60)
    assert await rows.reserve_refresh("tenant", "issuer|alice", "connection", 1, "lease-a", deadline)
    await session.commit()
    assert not await rows.reserve_refresh("tenant", "issuer|alice", "connection", 1, "lease-b", deadline)
    assert not await rows.reserve_refresh("tenant", "issuer|bob", "connection", 1, "lease-b", deadline)
    assert await rows.complete_refresh(
        "tenant", "issuer|alice", "connection", 1, "lease-a", b"rotated", ["read"]
    )
    await session.commit()
    await session.refresh(await rows.owned("tenant", "issuer|alice", "connection"))
    current = await rows.owned("tenant", "issuer|alice", "connection")
    assert current.revision == 2 and current.secret_ciphertext == b"rotated"
    assert current.scopes == ["read"]
    assert not await rows.complete_refresh(
        "tenant", "issuer|alice", "connection", 1, "lease-a", b"replayed", ["read"]
    )


async def test_disconnect_clears_grant_and_fences_a_late_rotation(stored):
    rows, session = stored
    assert await rows.reserve_refresh(
        "tenant", "issuer|alice", "connection", 1, "lease", datetime.now(UTC) + timedelta(seconds=60)
    )
    assert await rows.disconnect("tenant", "issuer|alice", "connection", 1)
    await session.commit()
    assert not await rows.complete_refresh(
        "tenant", "issuer|alice", "connection", 1, "lease", b"late", ["read"]
    )
    current = await rows.owned("tenant", "issuer|alice", "connection")
    await session.refresh(current)
    assert current.secret_ciphertext is None and current.status == "disconnected"


async def test_expired_refresh_outcome_is_not_silently_replayed(stored):
    rows, session = stored
    assert await rows.reserve_refresh(
        "tenant", "issuer|alice", "connection", 1, "lease", datetime.now(UTC) + timedelta(seconds=60)
    )
    current = await rows.owned("tenant", "issuer|alice", "connection")
    current.refresh_expires_at = datetime.now(UTC) - timedelta(seconds=1)
    await session.commit()
    # A lost rotation response may already have consumed the old grant remotely.
    assert not await rows.reserve_refresh(
        "tenant", "issuer|alice", "connection", 1, "replay", datetime.now(UTC) + timedelta(seconds=60)
    )


async def test_oauth_challenge_consumption_is_one_use_and_session_owner_config_bound(stored):
    from koinon.integrations.content_sources.entities import SourceAuthorizationChallenge
    from koinon.integrations.content_sources.repositories import SourceChallengeRepository

    _, session = stored
    session.add(
        SourceAuthorizationChallenge(
            id="challenge",
            connection_id="connection",
            tenant_id="tenant",
            owner="issuer|alice",
            session_hash="session-a",
            state_hash="state-a",
            config_fingerprint="configuration-a",
            secret_ciphertext=b"encrypted-verifier",
            status="pending",
            expires_at=datetime.now(UTC) + timedelta(minutes=5),
        )
    )
    await session.commit()
    rows = SourceChallengeRepository(session=session)
    for tenant, owner, browser, config in (
        ("other", "issuer|alice", "session-a", "configuration-a"),
        ("tenant", "issuer|bob", "session-a", "configuration-a"),
        ("tenant", "issuer|alice", "session-b", "configuration-a"),
        ("tenant", "issuer|alice", "session-a", "configuration-b"),
    ):
        assert not await rows.consume(tenant, owner, "challenge", browser, "state-a", config)
    assert await rows.consume(
        "tenant", "issuer|alice", "challenge", "session-a", "state-a", "configuration-a"
    )
    await session.commit()
    assert not await rows.consume(
        "tenant", "issuer|alice", "challenge", "session-a", "state-a", "configuration-a"
    )
