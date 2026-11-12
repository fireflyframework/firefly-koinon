# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Human approval, provider proof and audit use actual application transactions."""

from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from test_connection_lifecycle import lifecycle as lifecycle
from test_mapping_review import review as review
from test_source_migration_postgres import source_database as source_database
from test_validation_postgres import finish_preparation
from test_validation_postgres import validation_service as validation_service

from koinon.integrations.content_sources.dtos import ItemPage
from koinon.integrations.content_sources.errors import SourceError
from koinon.integrations.content_sources.mapping_policies import SourcePolicies
from koinon.integrations.content_sources.mapping_service import SourceMappings
from koinon.integrations.content_sources.sync_dtos import (
    SourceControlInput,
    SourcePolicyApplyInput,
    SourcePolicyReviewInput,
)
from koinon.integrations.content_sources.sync_entities import (
    SourcePolicyOperation,
    SourceSyncRun,
    SourceSyncState,
)
from koinon.integrations.content_sources.sync_scheduler import SourceScheduler
from koinon.jobs.entities import Job
from koinon.security.authority import primary_authority


async def test_policy_deadline_cancels_pending_native_session_read(monkeypatch):
    import asyncio

    from koinon.integrations.content_sources.sessions import SourceBrowserSessions

    cancelled = False

    class PendingStore:
        async def get(self, _identifier):
            nonlocal cancelled
            try:
                await asyncio.Event().wait()
            finally:
                cancelled = True

    original = asyncio.timeout
    monkeypatch.setattr(asyncio, "timeout", lambda _seconds: original(0))
    policies = object.__new__(SourcePolicies)
    policies.sessions = SourceBrowserSessions(PendingStore())
    with pytest.raises(SourceError, match="timeout"):
        await asyncio.wait_for(policies.review("issuer|alice", "tenant", "browser-a", None), timeout=1)
    assert cancelled


async def test_policy_caller_cancellation_propagates_and_releases_session_read():
    import asyncio

    from koinon.integrations.content_sources.sessions import SourceBrowserSessions

    started, released = asyncio.Event(), asyncio.Event()

    class PendingStore:
        async def get(self, _identifier):
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                released.set()

    policies = object.__new__(SourcePolicies)
    policies.sessions = SourceBrowserSessions(PendingStore())
    task = asyncio.create_task(policies.review("issuer|alice", "tenant", "browser-a", None))
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert released.is_set()


@pytest.mark.integration
@pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True)
async def test_sealed_large_review_applies_without_reenumerating_and_replays_exactly(
    validation_service, review
):
    service, body, state = validation_service
    body = body.model_copy(update={"hierarchy": "flatten"})
    prepared = await finish_preparation(
        service, await service.begin_validation("issuer|alice", "tenant", "browser-a", body)
    )
    assert prepared.state == "complete" and state["children"] == 2
    policies = review.context.get_bean(SourcePolicies)
    request = SourcePolicyReviewInput(
        **body.selection().model_dump(), operation_id=str(uuid4()), validation_id=prepared.validation_id
    )
    reviewed = await policies.review("issuer|alice", "tenant", "browser-a", request)
    assert state["children"] == 2
    visible = await policies.items(
        "issuer|alice",
        "tenant",
        reviewed.policy_id,
        browser_session="browser-a",
        limit=100,
    )
    assert visible.validation_id == prepared.validation_id and visible.can_apply
    assert len(visible.items) == 100 and visible.next_cursor is not None
    assert (
        visible.total is visible.observed_count is visible.known_bytes is visible.unknown_size_count is None
    )
    opens = state["opens"]
    for session, cursor in (
        ("browser-b", visible.next_cursor),
        ("browser-a", visible.next_cursor[:-4] + "AAAA"),
    ):
        with pytest.raises(SourceError):
            await policies.items(
                "issuer|alice",
                "tenant",
                reviewed.policy_id,
                browser_session=session,
                cursor=cursor,
            )
    assert state["opens"] == opens
    final = await policies.items(
        "issuer|alice",
        "tenant",
        reviewed.policy_id,
        browser_session="browser-a",
        limit=100,
        cursor=visible.next_cursor,
    )
    assert [item.item_id for item in final.items] == ["file-0100"] and final.next_cursor is None
    assert final.items[0].ancestry == ["selected"]
    assert state["children"] == 2
    approved = SourcePolicyApplyInput(
        operation_id=str(uuid4()),
        expected_revision=reviewed.result_policy_revision,
        review_id=reviewed.policy_id,
        review_digest=reviewed.review_digest,
    )
    result = await policies.apply("issuer|alice", "tenant", "browser-a", reviewed.mapping_id, approved)
    assert result.disposition == "accepted" and state["children"] == 2
    before = (state["opens"], state["changes"])
    assert await policies.review("issuer|alice", "tenant", "browser-a", request) == reviewed
    assert (
        await policies.apply("issuer|alice", "tenant", "browser-a", reviewed.mapping_id, approved) == result
    )
    assert before == (state["opens"], state["changes"])
    async with primary_authority():
        stored = await policies.records._require_session().get(SourceSyncState, reviewed.mapping_id)
        assert stored.enabled and stored.accepted_policy_id == reviewed.policy_id


@pytest.mark.integration
@pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True)
@pytest.mark.parametrize("invalid", ["incomplete", "collision", "selection", "session"])
async def test_unusable_validation_cannot_create_policy_review(validation_service, review, invalid):
    from sqlalchemy import func

    from koinon.integrations.content_sources.sync_entities import SourceMappingPolicy
    from koinon.jobs.errors import JobConflict

    service, body, state = validation_service
    state["collision"] = invalid == "collision"
    prepared = await service.begin_validation("issuer|alice", "tenant", "browser-a", body)
    if invalid != "incomplete":
        prepared = await finish_preparation(service, prepared)
    policies = review.context.get_bean(SourcePolicies)
    selected = body.selection().model_dump()
    if invalid == "selection":
        selected["hierarchy"] = "flatten"
    request = SourcePolicyReviewInput(
        **selected, operation_id=str(uuid4()), validation_id=prepared.validation_id
    )
    with pytest.raises((JobConflict, SourceError)) as failure:
        await policies.review(
            "issuer|alice", "tenant", "browser-b" if invalid == "session" else "browser-a", request
        )
    assert failure.value.code == ("access_denied" if invalid == "session" else "SOURCE_VALIDATION_CHANGED")
    async with primary_authority():
        assert (
            await policies.records._require_session().scalar(
                select(func.count()).select_from(SourceMappingPolicy)
            )
            == 0
        )


@pytest.mark.integration
@pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True)
@pytest.mark.parametrize("race", ["abandon", "destination_collision", "expiry"])
@pytest.mark.parametrize("action", ["review", "apply"])
async def test_validation_is_rechecked_after_provider_freshness_before_policy_write(
    validation_service, review, monkeypatch, race, action
):
    from sqlalchemy import func

    from koinon.catalog.service import CatalogService
    from koinon.integrations.content_sources.mapping_validation import SourceMappingValidations
    from koinon.integrations.content_sources.sync_entities import SourceMappingPolicy
    from koinon.jobs.errors import JobConflict

    service, body, state = validation_service
    state["count"] = 1
    prepared = await finish_preparation(
        service, await service.begin_validation("issuer|alice", "tenant", "browser-a", body)
    )
    policies = review.context.get_bean(SourcePolicies)
    request = SourcePolicyReviewInput(
        **body.selection().model_dump(),
        operation_id=str(uuid4()),
        validation_id=prepared.validation_id,
    )
    reviewed = (
        await policies.review("issuer|alice", "tenant", "browser-a", request) if action == "apply" else None
    )
    original = SourceMappingValidations.seal_for_review
    raced = False

    async def after_provider_freshness(instance, *args, **kwargs):
        nonlocal raced
        sealed = await original(instance, *args, **kwargs)
        if race == "abandon":
            await service.abandon_validation(
                "issuer|alice",
                "tenant",
                "browser-a",
                prepared.validation_id,
                prepared.revision,
            )
        elif race == "expiry":
            monkeypatch.setattr(SourceMappingValidations, "_now", staticmethod(lambda: prepared.expires_at))
        else:
            await review.context.get_bean(CatalogService).create(
                "issuer|alice",
                "tenant",
                kind="collection",
                name="file-0000.txt",
                parent_id=body.destination.parent_id,
            )
        raced = True
        return sealed

    monkeypatch.setattr(SourceMappingValidations, "seal_for_review", after_provider_freshness)
    with pytest.raises((SourceError, JobConflict)) as failure:
        if action == "review":
            await policies.review("issuer|alice", "tenant", "browser-a", request)
        else:
            await policies.apply(
                "issuer|alice",
                "tenant",
                "browser-a",
                reviewed.mapping_id,
                SourcePolicyApplyInput(
                    operation_id=str(uuid4()),
                    expected_revision=reviewed.result_policy_revision,
                    review_id=reviewed.policy_id,
                    review_digest=reviewed.review_digest,
                ),
            )
    assert raced, "Policy approval never checked its retained validation"
    assert (
        failure.value.code
        == {
            "abandon": "SOURCE_VALIDATION_CHANGED",
            "destination_collision": "SOURCE_DESTINATION_COLLISION",
            "expiry": "SOURCE_VALIDATION_EXPIRED",
        }[race]
    )
    async with primary_authority():
        assert await policies.records._require_session().scalar(
            select(func.count()).select_from(SourceMappingPolicy)
        ) == (1 if action == "apply" else 0)
        if reviewed is not None:
            assert await policies.records._require_session().get(SourceSyncState, reviewed.mapping_id) is None
            assert (
                await policies.records._require_session().get(
                    SourceMappingPolicy,
                    reviewed.policy_id,
                )
            ).accepted_at is None


@pytest.mark.integration
@pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True)
async def test_sealed_single_file_policy_retains_real_parent_and_normalizes_recursion(
    validation_service, review
):
    from koinon.integrations.content_sources.sync_entities import SourceMappingPolicy

    service, body, state = validation_service
    state["file_root"] = True
    prepared = await finish_preparation(
        service, await service.begin_validation("issuer|alice", "tenant", "browser-a", body)
    )
    policies = review.context.get_bean(SourcePolicies)
    result = await policies.review(
        "issuer|alice",
        "tenant",
        "browser-a",
        SourcePolicyReviewInput(
            **body.selection().model_dump(),
            operation_id=str(uuid4()),
            validation_id=prepared.validation_id,
        ),
    )
    assert body.recursive and state["children"] == 0
    async with primary_authority():
        policy = await policies.records._require_session().get(SourceMappingPolicy, result.policy_id)
        assert policy.policy_json["root_kind"] == "file"
        assert policy.policy_json["request"]["recursive"] is False
        assert policy.root_ancestry_json == ["selected", "root"]
    page = await policies.items("issuer|alice", "tenant", result.policy_id, browser_session="browser-a")
    assert page.root_kind == "file" and len(page.items) == 1
    assert page.items[0].ancestry == [] and page.items[0].relative_path == ["chosen.txt"]
    accepted = await policies.apply(
        "issuer|alice",
        "tenant",
        "browser-a",
        result.mapping_id,
        SourcePolicyApplyInput(
            operation_id=str(uuid4()),
            expected_revision=1,
            review_id=result.policy_id,
            review_digest=result.review_digest,
        ),
    )
    assert accepted.disposition == "accepted" and state["children"] == 0


@pytest.mark.integration
@pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True)
async def test_validation_baseline_is_independent_of_unapplied_policy_review_revisions(
    validation_service, review
):
    from koinon.integrations.content_sources.mapping_validation_dtos import SourceMappingValidationInput

    service, body, state = validation_service
    state["count"] = 1
    policies = review.context.get_bean(SourcePolicies)

    async def prepare(selection):
        return await finish_preparation(
            service, await service.begin_validation("issuer|alice", "tenant", "browser-a", selection)
        )

    initial = await prepare(body)
    first = await policies.review(
        "issuer|alice",
        "tenant",
        "browser-a",
        SourcePolicyReviewInput(
            **body.selection().model_dump(),
            operation_id=str(uuid4()),
            validation_id=initial.validation_id,
        ),
    )
    await policies.apply(
        "issuer|alice",
        "tenant",
        "browser-a",
        first.mapping_id,
        SourcePolicyApplyInput(
            operation_id=str(uuid4()),
            expected_revision=1,
            review_id=first.policy_id,
            review_digest=first.review_digest,
        ),
    )
    replacement = SourceMappingValidationInput(
        **body.selection().model_dump(),
        operation_id=uuid4(),
        mapping_id=first.mapping_id,
        expected_revision=1,
    )
    validated = await prepare(replacement)
    latest = None
    for expected in (1, 2):
        latest = await policies.review(
            "issuer|alice",
            "tenant",
            "browser-a",
            SourcePolicyReviewInput(
                **body.selection().model_dump(),
                operation_id=str(uuid4()),
                validation_id=validated.validation_id,
            ),
            mapping_id=first.mapping_id,
            expected_revision=expected,
        )
        assert latest.result_policy_revision == expected + 1
    accepted = await policies.apply(
        "issuer|alice",
        "tenant",
        "browser-a",
        first.mapping_id,
        SourcePolicyApplyInput(
            operation_id=str(uuid4()),
            expected_revision=3,
            review_id=latest.policy_id,
            review_digest=latest.review_digest,
        ),
    )
    assert accepted.result_policy_revision == 3
    async with primary_authority():
        stored = await policies.records._require_session().get(SourceSyncState, first.mapping_id)
        assert stored.accepted_policy_id == latest.policy_id
    with pytest.raises(SourceError, match="authority_changed"):
        await policies.review(
            "issuer|alice",
            "tenant",
            "browser-a",
            SourcePolicyReviewInput(
                **body.selection().model_dump(),
                operation_id=str(uuid4()),
                validation_id=validated.validation_id,
            ),
            mapping_id=first.mapping_id,
            expected_revision=3,
        )


@pytest.mark.integration
@pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True)
async def test_operation_receipt_http_is_exact_read_only_and_owner_bound(empty_listing):
    import httpx
    from pyfly.kernel import PyFlyException
    from pyfly.security.context import SecurityContext
    from pyfly.web.adapters.starlette.app import create_app
    from pyfly.web.adapters.starlette.errors import global_exception_handler
    from sqlalchemy import func
    from starlette.middleware.base import BaseHTTPMiddleware

    value = empty_listing
    policies = value.context.get_bean(SourcePolicies)
    reviewed = await policies.review(
        "issuer|alice",
        "tenant",
        "browser-a",
        SourcePolicyReviewInput(**value.request.model_dump(), operation_id=str(uuid4())),
    )
    accepted = await policies.apply(
        "issuer|alice",
        "tenant",
        "browser-a",
        reviewed.mapping_id,
        SourcePolicyApplyInput(
            operation_id=str(uuid4()),
            expected_revision=1,
            review_id=reviewed.policy_id,
            review_digest=reviewed.review_digest,
        ),
    )
    mappings = value.context.get_bean(SourceMappings)
    queued = await mappings.execute(
        "issuer|alice",
        "tenant",
        reviewed.mapping_id,
        "sync",
        SourceControlInput(operation_id=str(uuid4()), expected_revision=1),
    )
    app = create_app(context=value.context, actuator_enabled=False)
    app.add_exception_handler(PyFlyException, global_exception_handler)

    async def identity(request, next_handler):
        subject = request.headers.get("x-test-subject", "alice")
        request.state.security_context = SecurityContext(
            user_id=subject, attributes={"iss": "issuer", "sub": subject}
        )
        return await next_handler(request)

    app.add_middleware(BaseHTTPMiddleware, dispatch=identity)
    before = len(value.state.calls)
    async with primary_authority():
        jobs = await value.records._require_session().scalar(select(func.count()).select_from(Job))
    base = f"/api/v1/tenants/tenant/content-sources/mappings/{reviewed.mapping_id}/operations/"
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        initial = await client.get(
            f"/api/v1/tenants/tenant/content-sources/operations/{reviewed.operation_id}",
            params={"action": "review"},
        )
        assert initial.status_code == 200, initial.text
        assert initial.json() == {
            "kind": "policy",
            "receipt": reviewed.model_dump(mode="json", by_alias=True),
        }
        for result, kind in ((accepted, "policy"), (queued, "control")):
            response = await client.get(base + result.operation_id, params={"action": result.action})
            assert response.status_code == 200, response.text
            assert response.json() == {"kind": kind, "receipt": result.model_dump(mode="json", by_alias=True)}
        for path, action, headers in (
            (base + accepted.operation_id, "sync", {}),
            (base + accepted.operation_id, "invented", {}),
            (base + str(uuid4()), "apply", {}),
            (base + accepted.operation_id, "apply", {"x-test-subject": "bob"}),
            (base.replace(reviewed.mapping_id, str(uuid4())) + accepted.operation_id, "apply", {}),
            (base.replace("/tenant/", "/other/") + accepted.operation_id, "apply", {}),
        ):
            assert (await client.get(path, params={"action": action}, headers=headers)).status_code == 403
        initial_base = "/api/v1/tenants/tenant/content-sources/operations/"
        for operation, action, headers in (
            (reviewed.operation_id, "apply", {}),
            (reviewed.operation_id, "review", {"x-test-subject": "bob"}),
            (str(uuid4()), "review", {}),
        ):
            assert (
                await client.get(initial_base + operation, params={"action": action}, headers=headers)
            ).status_code == 403
        schema = (await client.get("/openapi.json")).json()
        assert "SourcePolicyReceipt" in schema["components"]["schemas"]
        assert "SourceControlReceipt" in schema["components"]["schemas"]
        from sqlalchemy import update

        from koinon.catalog.entities import Membership
        from koinon.catalog.service import CatalogService

        other = await value.context.get_bean(CatalogService).create(
            "issuer|alice",
            "tenant",
            kind="workspace",
            name="Remaining access",
        )
        async with primary_authority(read_only=False):
            await value.records._require_session().execute(
                update(Membership).where(Membership.id == "issuer|alice").values(workspace_id=other.id)
            )
        for path, action in (
            (base + accepted.operation_id, "apply"),
            (base + queued.operation_id, "sync"),
            (initial_base + reviewed.operation_id, "review"),
        ):
            response = await client.get(path, params={"action": action})
            assert response.status_code == 403 and "receipt" not in response.json()
    assert len(value.state.calls) == before
    async with primary_authority():
        assert await value.records._require_session().scalar(select(func.count()).select_from(Job)) == jobs


@pytest.mark.integration
@pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True)
@pytest.mark.parametrize("code", ["unavailable", "access_denied"])
async def test_mapping_presentation_never_reuses_names_after_provider_denial(empty_listing, code):
    value = empty_listing
    policies = value.context.get_bean(SourcePolicies)
    reviewed = await policies.review(
        "issuer|alice",
        "tenant",
        "browser-a",
        SourcePolicyReviewInput(**value.request.model_dump(), operation_id=str(uuid4())),
    )
    mappings = value.context.get_bean(SourceMappings)
    assert (await mappings.get("issuer|alice", "tenant", reviewed.mapping_id)).presentation.source_root

    async def deny(_):
        raise SourceError(code)

    value.state.during = deny
    result = await mappings.get("issuer|alice", "tenant", reviewed.mapping_id)
    assert result.id == reviewed.mapping_id and not result.can_sync
    assert result.presentation.source_root is None and result.presentation.destination is None
    assert result.presentation.unavailable_reason == code
    page = await mappings.list("issuer|alice", "tenant")
    assert "secret remote title" not in str(page) and "Own folder" not in str(page)


@pytest.mark.integration
@pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True)
async def test_mapping_presentation_rechecks_local_access_after_provider_reads(empty_listing):
    from sqlalchemy import delete

    from koinon.catalog.entities import Membership
    from koinon.catalog.errors import AccessDenied

    value = empty_listing
    reviewed = await value.context.get_bean(SourcePolicies).review(
        "issuer|alice",
        "tenant",
        "browser-a",
        SourcePolicyReviewInput(**value.request.model_dump(), operation_id=str(uuid4())),
    )
    calls = 0

    async def revoke(identifier):
        nonlocal calls
        calls += identifier == "selected"
        if calls == 2:
            async with primary_authority(read_only=False):
                await value.records._require_session().execute(
                    delete(Membership).where(Membership.id == "issuer|alice")
                )

    value.state.during = revoke
    with pytest.raises(AccessDenied):
        await value.context.get_bean(SourceMappings).get("issuer|alice", "tenant", reviewed.mapping_id)


@pytest.fixture
def empty_listing(review, monkeypatch):
    original = review.service.browser._source

    @asynccontextmanager
    async def source(scope, tokens):
        async with original(scope, tokens) as adapter:

            async def children(folder, cursor=None):
                return ItemPage((), None)

            adapter.children = children
            yield adapter

    monkeypatch.setattr(review.service.browser, "_source", source)
    return review


@pytest.mark.integration
@pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True)
@pytest.mark.parametrize("conflict", ["source_name", "destination_name"])
async def test_conflicted_review_is_visible_and_cannot_be_applied(review, monkeypatch, conflict):
    from pyfly.kernel import ConflictException

    from koinon.catalog.service import CatalogService
    from koinon.integrations.content_sources.dtos import RemoteItem

    original = review.service.browser._source

    @asynccontextmanager
    async def source(scope, tokens):
        async with original(scope, tokens) as adapter:
            files = {
                "one": RemoteItem(
                    scope, "one", "Report.pdf", "file", "v1", 12, "application/pdf", parents=("selected",)
                ),
            }
            if conflict == "source_name":
                files["two"] = RemoteItem(
                    scope, "two", "REPORT.pdf", "file", "v1", 12, "application/pdf", parents=("selected",)
                )
            get_item = adapter.get_item

            async def read(identifier):
                return files[identifier] if identifier in files else await get_item(identifier)

            async def children(folder, cursor=None):
                return ItemPage(tuple(files.values()), None)

            adapter.get_item, adapter.children = read, children
            yield adapter

    monkeypatch.setattr(review.service.browser, "_source", source)
    if conflict == "destination_name":
        await review.context.get_bean(CatalogService).create(
            "issuer|alice",
            "tenant",
            kind="collection",
            name="report.PDF",
            parent_id=review.request.destination.parent_id,
        )
    policies = review.context.get_bean(SourcePolicies)
    receipt = await policies.review(
        "issuer|alice",
        "tenant",
        "browser-a",
        SourcePolicyReviewInput(**review.request.model_dump(), operation_id=str(uuid4())),
    )
    page = await policies.items("issuer|alice", "tenant", receipt.policy_id)
    assert page.enumeration_complete and not page.can_apply
    assert all(item.collision == conflict for item in page.items)
    assert page.items[0].destination_relative_path == ["Report.pdf"]
    assert page.destination.segments[-1].name == "Own folder"
    with pytest.raises(ConflictException) as denied:
        await policies.apply(
            "issuer|alice",
            "tenant",
            "browser-a",
            receipt.mapping_id,
            SourcePolicyApplyInput(
                operation_id=str(uuid4()),
                expected_revision=1,
                review_id=receipt.policy_id,
                review_digest=receipt.review_digest,
            ),
        )
    assert denied.value.code == "SOURCE_MAPPING_COLLISION"
    async with primary_authority():
        assert await policies.records._require_session().get(SourceSyncState, receipt.mapping_id) is None


@pytest.mark.integration
@pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True)
async def test_review_apply_replay_and_logged_out_session_use_real_units(empty_listing):
    review = empty_listing
    policies = review.context.get_bean(SourcePolicies)
    request = SourcePolicyReviewInput(**review.request.model_dump(), operation_id=str(uuid4()))
    result = await policies.review("issuer|alice", "tenant", "browser-a", request)
    mappings = review.context.get_bean(SourceMappings)
    draft = await mappings.get("issuer|alice", "tenant", result.mapping_id)
    assert draft.presentation.source_root.name == "secret remote title"
    assert [segment.name for segment in draft.presentation.destination.segments] == [
        "Own workspace",
        "Own project",
        "Own folder",
    ]
    assert draft.policy_revision is None and draft.latest_review_revision == 1 and not draft.can_sync
    page = await policies.items("issuer|alice", "tenant", result.policy_id)
    assert page.items == [] and page.enumeration_complete and page.total == 0 and page.can_apply
    with pytest.raises(SourceError, match="invalid_cursor"):
        await policies.items("issuer|alice", "tenant", result.policy_id, cursor="forged")
    calls = len(review.state.calls)
    assert await policies.review("issuer|alice", "tenant", "browser-a", request) == result
    assert len(review.state.calls) == calls
    apply = SourcePolicyApplyInput(
        operation_id=str(uuid4()),
        expected_revision=1,
        review_id=result.policy_id,
        review_digest=result.review_digest,
    )
    accepted = await policies.apply("issuer|alice", "tenant", "browser-a", result.mapping_id, apply)
    assert not (await policies.items("issuer|alice", "tenant", result.policy_id)).can_apply
    active = await mappings.get("issuer|alice", "tenant", result.mapping_id)
    assert active.policy_revision == 1 and active.control_revision == 1 and active.can_sync
    status = await mappings.list("issuer|alice", "tenant")
    assert status["items"][0]["policy_revision"] == 1
    assert status["items"][0]["presentation"]["source_root"]["name"] == "secret remote title"
    assert await mappings.runs("issuer|alice", "tenant", result.mapping_id) == {
        "items": [],
        "next_cursor": None,
    }
    calls = len(review.state.calls)
    assert await policies.apply("issuer|alice", "tenant", "browser-a", result.mapping_id, apply) == accepted
    assert len(review.state.calls) == calls
    with pytest.raises(SourceError, match="access_denied"):
        await policies.apply("issuer|alice", "tenant", "logged-out", result.mapping_id, apply)
    assert len(review.state.calls) == calls
    async with primary_authority():
        session = policies.records._require_session()
        state = await session.get(SourceSyncState, result.mapping_id)
        assert state.enabled and state.accepted_policy_id == result.policy_id
        assert len(list((await session.scalars(select(SourcePolicyOperation))).all())) == 2
    command = SourceControlInput(operation_id=str(uuid4()), expected_revision=1)
    queued = await mappings.execute("issuer|alice", "tenant", result.mapping_id, "sync", command)
    assert queued.disposition == "queued"
    live = await mappings.run("issuer|alice", "tenant", queued.run_id)
    assert live.status == "queued" and live.can_cancel
    assert (await mappings.runs("issuer|alice", "tenant", result.mapping_id))["items"][0][
        "id"
    ] == queued.run_id
    cancelled = await mappings.execute(
        "issuer|alice",
        "tenant",
        result.mapping_id,
        "cancel",
        SourceControlInput(operation_id=str(uuid4()), expected_revision=queued.control_revision),
        target_run_id=queued.run_id,
    )
    assert cancelled.disposition == "stopping"
    assert not (await mappings.run("issuer|alice", "tenant", queued.run_id)).can_cancel


@pytest.mark.integration
@pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True)
async def test_actual_scheduler_dispatches_due_policy_once_with_owner_authority(empty_listing):
    review = empty_listing
    policies = review.context.get_bean(SourcePolicies)
    scheduler = review.context.get_bean(SourceScheduler)
    request = SourcePolicyReviewInput(
        **{**review.request.model_dump(), "schedule": {"kind": "interval", "seconds": 900}},
        operation_id=str(uuid4()),
    )
    result = await policies.review("issuer|alice", "tenant", "browser-a", request)
    await policies.apply(
        "issuer|alice",
        "tenant",
        "browser-a",
        result.mapping_id,
        SourcePolicyApplyInput(
            operation_id=str(uuid4()),
            expected_revision=1,
            review_id=result.policy_id,
            review_digest=result.review_digest,
        ),
    )
    due = datetime.now(UTC) - timedelta(seconds=1801)
    async with primary_authority(read_only=False):
        state = await policies.records._require_session().get(SourceSyncState, result.mapping_id)
        state.next_run_at, state.revision = due, 2
    scheduler.settings.enabled = scheduler.settings.synchronization_enabled = True
    await scheduler.tick()
    await scheduler.tick()
    async with primary_authority():
        session = policies.records._require_session()
        runs = list((await session.scalars(select(SourceSyncRun))).all())
        jobs = list((await session.scalars(select(Job).where(Job.kind == "content.source.reconcile"))).all())
        assert len(runs) == len(jobs) == 1
        assert runs[0].trigger_kind == "interval" and runs[0].job_id == jobs[0].id
        assert (await session.get(SourceSyncState, result.mapping_id)).next_run_at == due + timedelta(
            seconds=2700
        )
