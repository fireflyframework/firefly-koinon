# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Sharing checks real source state at creation and at each recipient release."""

import importlib.util
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pyfly.data.relational.datasource_registry import DataSourceRegistry
from pyfly.data.transaction import current_unit_of_work
from pyfly.kernel import GoneException, InvalidRequestException
from sqlalchemy import select, update

from koinon.catalog.errors import AccessDenied
from koinon.evidence.entities import EvidenceReview
from koinon.integrations.content_sources.entities import PersonalSourceConnection
from koinon.integrations.content_sources.errors import SourceError
from koinon.sharing.dtos import ShareBrowseInput, ShareCreate, ShareReviewInput
from koinon.sharing.entities import ConversationShare
from koinon.sharing.repositories import ConversationShareRepository
from koinon.sharing.service import ConversationShares

spec = importlib.util.spec_from_file_location(
    "sharing_source_fixture", Path(__file__).parents[1] / "exports/test_source_release_postgres.py"
)
assert spec and spec.loader
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)
reviews = fixtures.reviews
postgres_reviews = fixtures.postgres_reviews
pytestmark = pytest.mark.integration


async def created_share(context):
    service = context.get_bean(ConversationShares)
    review = await service.preview("owner", "north", ShareReviewInput(thread_id="t", message_ids=["m"]))
    created = await service.create(
        "owner", "north", ShareCreate(review_id=review.id, expected_revision=review.revision)
    )
    return service, created


async def reader_share(reviews, monkeypatch):
    _, sessions, remote = await fixtures.reader_export(reviews, monkeypatch)
    return reviews[2].get_bean(ConversationShares), sessions, remote


async def test_provider_checks_never_retain_a_sharing_transaction(reviews, monkeypatch):
    service, _, remote = await reader_share(reviews, monkeypatch)
    original = reviews[1].authorize_output

    async def checked_output(*args, **kwargs):
        unit = current_unit_of_work("primary")
        assert unit is None or unit.completed, "provider I/O inside sharing transaction"
        await original(*args, **kwargs)

    monkeypatch.setattr(reviews[1], "authorize_output", checked_output)
    _, shared = await created_share(reviews[2])
    opened = await service.read("owner", "north", shared.id)
    assert opened.messages[0].text == "Reviewed answer"
    assert remote.calls and all(actor == "owner" for actor, _, _ in remote.calls)


async def test_legacy_list_hides_imported_and_unknown_lineage_but_quota_counts_them(reviews):
    context = reviews[2]
    sessions = await fixtures.imported_graph(context)
    now = datetime.now(UTC)
    async with sessions.begin() as session:
        for identifier, manifest, snapshot in (
            ("local", [], {}),
            ("imported", [{"asset_id": "asset"}], {}),
            (
                "unknown",
                [],
                {
                    "memory_bindings": [
                        {"run_id": "missing", "results": [{"id": "missing", "sha256": "a" * 64}]}
                    ]
                },
            ),
        ):
            session.add(
                EvidenceReview(
                    id=identifier,
                    tenant_id="north",
                    owner_subject="owner",
                    kind="share",
                    title="Local notes" if identifier == "local" else "Protected notes",
                    revision="a" * 64,
                    request_json={},
                    snapshot_json=snapshot,
                    manifest_json=manifest,
                    created_at=now,
                    expires_at=now + timedelta(days=1),
                )
            )
            await session.flush()
            session.add(
                ConversationShare(
                    id=identifier,
                    tenant_id="north",
                    owner_subject="owner",
                    review_id=identifier,
                    created_at=now,
                    expires_at=now + timedelta(days=1),
                )
            )
    async with sessions() as session:
        repository = ConversationShareRepository(session=session)
        page = await repository.page("owner", "north")
        assert page["total"] == 1 and [row.id for row in page["items"]] == ["local"]
        assert await repository.active_count("owner", "north") == 3
        hidden = await repository.page("owner", "north", q="Protected")
        assert hidden["items"] == [] and hidden["total"] == hidden["pages"] == 0


async def test_disconnect_before_fence_does_not_consume_review_or_create_share(reviews, monkeypatch):
    from koinon.integrations.content_sources.read_service import SourceReadOperation

    service, sessions, _ = await reader_share(reviews, monkeypatch)
    review = await service.preview("owner", "north", ShareReviewInput(thread_id="t", message_ids=["m"]))
    original = SourceReadOperation.local_fence

    @asynccontextmanager
    async def disconnected(operation):
        async with sessions.begin() as session:
            await session.execute(update(PersonalSourceConnection).values(status="disconnected", revision=2))
        async with original(operation):
            yield

    monkeypatch.setattr(SourceReadOperation, "local_fence", disconnected)
    with pytest.raises(SourceError):
        await service.create(
            "owner", "north", ShareCreate(review_id=review.id, expected_revision=review.revision)
        )
    async with sessions() as session:
        assert (await session.get(EvidenceReview, review.id)).consumed_at is None
        assert list(await session.scalars(select(ConversationShare.id))) == []


@pytest.mark.parametrize("change", ["revoked", "expired", "review", "source"])
async def test_changes_during_source_resolution_cannot_release_shared_bytes(reviews, monkeypatch, change):
    service, sessions, _ = await reader_share(reviews, monkeypatch)
    _, shared = await created_share(reviews[2])

    class Resolver:
        async def resolve(self, actor, tenant, sources):
            async with sessions.begin() as session:
                if change == "revoked":
                    await session.execute(update(ConversationShare).values(revoked_at=datetime.now(UTC)))
                elif change == "expired":
                    await session.execute(update(ConversationShare).values(expires_at=datetime.now(UTC)))
                elif change == "review":
                    await session.execute(update(EvidenceReview).values(revision="b" * 64))
                else:
                    await session.execute(
                        update(PersonalSourceConnection).values(status="disconnected", revision=2)
                    )
            return sources

    service.reviews.sources = SimpleNamespace(get=lambda: Resolver())
    with pytest.raises((AccessDenied, GoneException, SourceError)):
        await service.read("owner", "north", shared.id)


async def test_browse_rechecks_source_and_binds_cursor_filters_and_selection(reviews, monkeypatch):
    from koinon.integrations.content_sources.read_dtos import ReaderSelectionInput

    service, sessions, _ = await reader_share(reviews, monkeypatch)
    await created_share(reviews[2])
    await created_share(reviews[2])
    cache = await fixtures.shared_cursor_store(service, reviews[2])
    try:
        first = await service.browse("owner", "north", ShareBrowseInput(page_size=1))
        assert len(first.items) == 1 and first.next_cursor
        assert first.total is None and first.total_is_exact is False
        opted_out = await service.browse(
            "owner", "north", ShareBrowseInput(page_size=1, reader_source_connections=[])
        )
        assert opted_out.items == () and opted_out.next_cursor and opted_out.total is None
        with pytest.raises(InvalidRequestException) as changed:
            await service.browse(
                "owner", "north", ShareBrowseInput(page_size=1, cursor=first.next_cursor, q="other")
            )
        assert changed.value.code == "SOURCE_CURSOR_EXPIRED"
        async with sessions.begin() as session:
            await session.execute(update(PersonalSourceConnection).values(status="disconnected", revision=2))
        second = await service.browse(
            "owner", "north", ShareBrowseInput(page_size=1, cursor=first.next_cursor)
        )
        assert second.items == () and second.next_cursor
        last = await service.browse(
            "owner", "north", ShareBrowseInput(page_size=1, cursor=second.next_cursor)
        )
        assert last.items == () and last.next_cursor is None
        reader = service.reviews.source_reader.get()
        await reader.selections.replace(
            "owner", "north", ReaderSelectionInput(expected_revision=1, operation_id=uuid4(), connections=[])
        )
        with pytest.raises(InvalidRequestException) as changed:
            await service.browse("owner", "north", ShareBrowseInput(page_size=1, cursor=first.next_cursor))
        assert changed.value.code == "SOURCE_CURSOR_EXPIRED"
    finally:
        await cache.stop()


@pytest.mark.parametrize("change", ["revoked", "expired", "review"])
async def test_state_changed_during_final_provider_check_cannot_release(reviews, monkeypatch, change):
    from koinon.integrations.content_sources.read_service import SourceReadOperation

    service, sessions, _ = await reader_share(reviews, monkeypatch)
    _, shared = await created_share(reviews[2])
    original = SourceReadOperation.release
    releases = 0
    resolving = False

    class Resolver:
        async def resolve(self, actor, tenant, sources):
            nonlocal resolving
            resolving = True
            return sources

    service.reviews.sources = SimpleNamespace(get=lambda: Resolver())

    async def changed_after_check(operation):
        nonlocal releases
        await original(operation)
        if not resolving:
            return
        releases += 1
        if releases == 2:
            async with sessions.begin() as session:
                if change == "revoked":
                    await session.execute(update(ConversationShare).values(revoked_at=datetime.now(UTC)))
                elif change == "expired":
                    await session.execute(update(ConversationShare).values(expires_at=datetime.now(UTC)))
                else:
                    await session.execute(update(EvidenceReview).values(revision="c" * 64))

    monkeypatch.setattr(SourceReadOperation, "release", changed_after_check)
    with pytest.raises((AccessDenied, GoneException)):
        await service.read("owner", "north", shared.id)
    assert releases == 2


async def test_recipient_uses_own_connection_and_cannot_borrow_owner_or_other_tenant(reviews, monkeypatch):
    from koinon.catalog.entities import Membership
    from koinon.integrations.content_sources.read_context import reader_source_scope
    from koinon.integrations.content_sources.read_dtos import ReaderSelectionInput

    service, sessions, remote = await reader_share(reviews, monkeypatch)
    _, shared = await created_share(reviews[2])
    output_actors = []

    async def output(owner, tenant, thread, messages, *, snapshot=None, reader_subject=None):
        assert snapshot.owner_subject == owner == "owner" and tenant == "north"
        output_actors.append(reader_subject or owner)

    monkeypatch.setattr(reviews[1], "authorize_output", output)
    async with sessions.begin() as session:
        session.add(Membership(id="recipient", subject="recipient", tenant_id="north", role="viewer"))
        session.add(
            PersonalSourceConnection(
                id="recipient-connection",
                tenant_id="north",
                owner="recipient",
                provider="google_drive",
                status="connected",
                external_subject="remote-recipient",
                issuer="https://accounts.google.com",
                config_fingerprint="f" * 64,
                scopes=["https://www.googleapis.com/auth/drive.readonly"],
            )
        )
    reader = service.reviews.source_reader.get()
    await reader.selections.replace(
        "recipient",
        "north",
        ReaderSelectionInput(
            expected_revision=0,
            operation_id=uuid4(),
            connections=[{"provider": "google_drive", "connection_id": "recipient-connection"}],
        ),
    )
    remote.calls.clear()
    opened = await service.read("recipient", "north", shared.id)
    assert opened.messages[0].text == "Reviewed answer"
    assert output_actors and set(output_actors) == {"recipient"}
    assert remote.calls and set(remote.calls) == {("recipient", "north", "recipient-connection")}
    remote.calls.clear()
    with (
        reader_source_scope(
            "recipient", "north", [{"provider": "google_drive", "connection_id": "connection"}]
        ),
        pytest.raises(SourceError),
    ):
        await service.read("recipient", "north", shared.id)
    assert remote.calls == []
    with pytest.raises(AccessDenied):
        await service.read("recipient", "another-tenant", shared.id)
    with reader_source_scope("recipient", "north", []), pytest.raises(SourceError):
        await service.read("recipient", "north", shared.id)
    async with sessions.begin() as session:
        await session.execute(
            update(PersonalSourceConnection)
            .where(PersonalSourceConnection.owner == "recipient")
            .values(status="disconnected", revision=2)
        )
    with pytest.raises(SourceError):
        await service.read("recipient", "north", shared.id)


async def test_source_revision_change_never_grants_historical_share_bytes(reviews, monkeypatch):
    from koinon.integrations.content_sources.mapping_entities import SourceObject

    service, sessions, _ = await reader_share(reviews, monkeypatch)
    _, shared = await created_share(reviews[2])
    async with sessions.begin() as session:
        await session.execute(update(SourceObject).values(remote_version="v2"))
    with pytest.raises(SourceError):
        await service.read("owner", "north", shared.id)
    assert (await service.browse("owner", "north", ShareBrowseInput())).items == ()
    # Owners can revoke without disclosing protected content or reconnecting a source.
    await service.revoke("owner", "north", shared.id)
    async with sessions() as session:
        assert (await session.get(ConversationShare, shared.id)).revoked_at is not None


async def test_create_limit_counts_hidden_imported_shares(reviews, monkeypatch):
    from pyfly.kernel import ConflictException

    service, _, _ = await reader_share(reviews, monkeypatch)
    await created_share(reviews[2])
    assert (await service.page("owner", "north")).total == 0
    monkeypatch.setattr(service.reviews.settings, "max_active_shares", 1)
    review = await service.preview("owner", "north", ShareReviewInput(thread_id="t", message_ids=["m"]))
    with pytest.raises(ConflictException) as error:
        await service.create(
            "owner", "north", ShareCreate(review_id=review.id, expected_revision=review.revision)
        )
    assert error.value.code == "SHARE_LIMIT_REACHED"
    async with reviews[2].get_bean(DataSourceRegistry).primary.sessionmaker() as session:
        assert (await session.get(EvidenceReview, review.id)).consumed_at is None


@pytest.mark.parametrize("surface", ["read", "browse", "revoke"])
async def test_disconnected_source_does_not_hydrate_review_content(reviews, monkeypatch, surface):
    from sqlalchemy import event

    service, sessions, _ = await reader_share(reviews, monkeypatch)
    _, shared = await created_share(reviews[2])
    async with sessions.begin() as session:
        await session.execute(update(PersonalSourceConnection).values(status="disconnected", revision=2))
    engine = reviews[2].get_bean(DataSourceRegistry).primary.engine.sync_engine
    queries = []

    def observed(connection, cursor, statement, parameters, context, many):
        queries.append(statement)

    event.listen(engine, "before_cursor_execute", observed)
    try:
        if surface == "read":
            with pytest.raises(SourceError):
                await service.read("owner", "north", shared.id)
        elif surface == "browse":
            assert (await service.browse("owner", "north", ShareBrowseInput())).items == ()
        else:
            await service.revoke("owner", "north", shared.id)
    finally:
        event.remove(engine, "before_cursor_execute", observed)
    assert queries
    assert not any("koinon_evidence_reviews.title" in statement for statement in queries)


async def test_unavailable_output_authority_does_not_consume_share_review(reviews):
    from pyfly.kernel import ServiceUnavailableException

    evidence, _, context = reviews
    service = context.get_bean(ConversationShares)
    review = await service.preview("owner", "north", ShareReviewInput(thread_id="t", message_ids=["m"]))
    evidence.outputs = None
    with pytest.raises(ServiceUnavailableException) as error:
        await service.create(
            "owner", "north", ShareCreate(review_id=review.id, expected_revision=review.revision)
        )
    assert error.value.code == "CONVERSATION_OUTPUT_UNAVAILABLE"
    async with context.get_bean(DataSourceRegistry).primary.sessionmaker() as session:
        assert list(await session.scalars(select(ConversationShare.id))) == []
        assert (await session.get(EvidenceReview, review.id)).consumed_at is None
