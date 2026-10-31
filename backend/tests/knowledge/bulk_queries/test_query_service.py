# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import pytest
from pyfly.kernel import ConflictException


def request(env, question="Count"):
    from koinon.knowledge.bulk_queries.dtos import QueryBatchCreate

    return QueryBatchCreate.model_validate(
        {
            "workspace_id": env.workspace.id,
            "items": [{"client_item_id": "one", "dataset_id": env.dataset.id, "question": question}],
        }
    )


async def test_query_admission_is_durable_owner_token_bound_and_does_not_invoke_any_model(queries):
    from koinon.catalog.errors import AccessDenied
    from koinon.knowledge.bulk_queries.queue import QueryBatchQueue
    from koinon.knowledge.bulk_queries.service import QueryBatches

    service = queries.context.get_bean(QueryBatches)
    batch = await service.create("issuer|analyst", "north", request(queries), "create-key")
    replay = await service.create("issuer|analyst", "north", request(queries), "create-key")
    assert batch.id == replay.id and batch.status == "queued" and batch.total_items == 1
    with pytest.raises(ConflictException):
        await service.create("issuer|analyst", "north", request(queries, "Changed"), "create-key")
    with pytest.raises(AccessDenied):
        await service.get("issuer|other", "north", batch.id)
    items = await service.items("issuer|analyst", "north", batch.id)
    assert items.total == 1 and items.items[0].question == "Count"
    lease = await queries.context.get_bean(QueryBatchQueue).claim("worker")
    assert (
        lease.item_id == items.items[0].id and lease.subject == "issuer|analyst" and lease.question == "Count"
    )
    await queries.context.get_bean(QueryBatchQueue).check(lease)
    assert lease.policy.tenant_id == "north" and lease.dataset_id == queries.dataset.id


async def test_current_role_revocation_after_last_counts_does_not_return_private_questions_or_totals(queries):
    from koinon.catalog.errors import AccessDenied
    from koinon.knowledge.bulk_queries.service import QueryBatches

    service = queries.context.get_bean(QueryBatches)
    batch = await service.create("issuer|analyst", "north", request(queries), "create")
    original = service.records.counts

    async def revoke(batch_id):
        from pyfly.data.relational.datasource_registry import DataSourceRegistry
        from sqlalchemy import update

        from koinon.catalog.entities import Membership

        result = await original(batch_id)
        datasource = queries.context.get_bean(DataSourceRegistry).get("primary")
        async with datasource.engine.begin() as connection:
            await connection.execute(
                update(Membership).where(Membership.id == "issuer|analyst").values(active=False)
            )
        return result

    service.records.counts = revoke
    with pytest.raises(AccessDenied):
        await service.get("issuer|analyst", "north", batch.id)


async def test_originating_pat_is_required_and_current_scopes_are_rechecked_before_claim_execution(queries):
    from datetime import timedelta

    from pyfly.security.context import SecurityContext
    from pyfly.security.context_holder import SecurityContextHolder

    from koinon.catalog.errors import AccessDenied
    from koinon.knowledge.bulk.entities import now
    from koinon.knowledge.bulk_queries.queue import QueryBatchQueue
    from koinon.knowledge.bulk_queries.service import QueryBatches
    from koinon.tokens.entities import PersonalToken
    from koinon.tokens.repositories import PersonalTokenRepository

    tokens = queries.context.get_bean(PersonalTokenRepository)
    token = PersonalToken(
        id="query-origin",
        subject="issuer|analyst",
        tenant_id="north",
        name="Inert",
        token_hash="a" * 64,
        prefix="test",
        scopes=["catalog:read", "query:execute"],
        workspace_ids=[queries.workspace.id],
        asset_ids=None,
        resource_ids=None,
        expires_at=now() + timedelta(hours=1),
    )
    await tokens.save(token)
    service = queries.context.get_bean(QueryBatches)
    queue = queries.context.get_bean(QueryBatchQueue)
    with SecurityContextHolder.using(
        SecurityContext(user_id=token.subject, attributes={"koinon_token_id": token.id})
    ):
        batch = await service.create(token.subject, "north", request(queries), "pat-create")
    with pytest.raises(AccessDenied):
        await service.get(token.subject, "north", batch.id)
    lease = await queue.claim("worker")
    assert lease.token_id == token.id
    await queue.check(lease)
    token.scopes = ["catalog:read"]
    await tokens.save(token)
    with pytest.raises(AccessDenied):
        await queue.check(lease)


async def test_queued_cancellation_is_idempotent_and_unknown_native_outcomes_are_never_executed_again(
    queries,
):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from koinon.knowledge.bulk_queries.dtos import QueryBatchAction
    from koinon.knowledge.bulk_queries.execution import QueryBatchExecutor
    from koinon.knowledge.bulk_queries.queue import QueryBatchQueue
    from koinon.knowledge.bulk_queries.service import QueryBatches

    service = queries.context.get_bean(QueryBatches)
    batch = await service.create("issuer|analyst", "north", request(queries), "cancel-create")
    cancelled = await service.cancel(
        "issuer|analyst", "north", batch.id, QueryBatchAction(expected_revision=batch.revision), "cancel"
    )
    assert cancelled.cancellation_requested
    assert (
        await service.cancel(
            "issuer|analyst", "north", batch.id, QueryBatchAction(expected_revision=batch.revision), "cancel"
        )
        == cancelled
    )
    queue = queries.context.get_bean(QueryBatchQueue)
    assert await queue.claim("worker") is None
    batch = await service.create("issuer|analyst", "north", request(queries), "unknown-create")
    lease = await queue.claim("worker")
    native = SimpleNamespace(
        inspect=AsyncMock(return_value=("admitted", None)), execute=AsyncMock(), acknowledge=AsyncMock()
    )
    await QueryBatchExecutor(queue, native).execute(lease)
    native.execute.assert_not_awaited()
    native.acknowledge.assert_not_awaited()
    item = (await service.items("issuer|analyst", "north", batch.id)).items[0]
    assert item.status == "reconciling" and item.error_code == "BULK_QUERY_OUTCOME_UNRESOLVED"
    assert await queue.claim("worker") is None


async def test_nonpage_rebound_dataset_is_excluded_before_private_total(queries):
    from uuid import uuid4

    from koinon.knowledge.bulk_queries.dtos import QueryBatchCreate
    from koinon.knowledge.bulk_queries.service import QueryBatches
    from koinon.knowledge.entities import DomainBinding

    service = queries.context.get_bean(QueryBatches)
    await service.create("issuer|analyst", "north", request(queries), "older")
    dataset = await queries.catalog.create(
        "issuer|admin", "north", kind="dataset", name="Another", parent_id=queries.dataset.parent_id
    )
    original = (await queries.bindings.find_all(tenant_id="north", catalog_id=queries.dataset.id))[0]
    await queries.bindings.save(
        DomainBinding(
            id=str(uuid4()),
            tenant_id="north",
            catalog_id=dataset.id,
            workspace_id=queries.workspace.id,
            domain="structured",
            entity_kind="dataset",
            native_id=str(uuid4()),
            native_workspace_id=original.native_workspace_id,
            created_by="issuer|admin",
        )
    )
    latest = await service.create(
        "issuer|analyst",
        "north",
        QueryBatchCreate.model_validate(
            {
                "workspace_id": queries.workspace.id,
                "items": [{"client_item_id": "one", "dataset_id": dataset.id, "question": "Count another"}],
            }
        ),
        "newer",
    )
    original.native_id = str(uuid4())
    await queries.bindings.save(original)
    result = await service.list("issuer|analyst", "north", page_size=1)
    assert result.total == 1 and [row.id for row in result.items] == [latest.id]


async def test_empty_page_cannot_return_private_total_after_last_read_revokes_membership(queries):
    from pyfly.data.relational.datasource_registry import DataSourceRegistry
    from sqlalchemy import update

    from koinon.catalog.entities import Membership
    from koinon.catalog.errors import AccessDenied
    from koinon.knowledge.bulk_queries.service import QueryBatches

    service = queries.context.get_bean(QueryBatches)
    await service.create("issuer|analyst", "north", request(queries), "create")
    original = service.records.visible_page
    calls = 0

    async def revoke(*args, **kwargs):
        nonlocal calls
        result = await original(*args, **kwargs)
        calls += 1
        if calls == 2:
            datasource = queries.context.get_bean(DataSourceRegistry).get("primary")
            async with datasource.engine.begin() as connection:
                await connection.execute(
                    update(Membership).where(Membership.id == "issuer|analyst").values(active=False)
                )
        return result

    service.records.visible_page = revoke
    with pytest.raises(AccessDenied):
        await service.list("issuer|analyst", "north", page=2, page_size=1)
