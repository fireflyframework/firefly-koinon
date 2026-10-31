# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy import select
from test_query_native_repository import native_queries as native_queries
from test_query_native_repository import policy, values


@pytest.mark.parametrize("deny", [False, True])
async def test_real_named_native_query_and_marker_share_runtime_transaction_until_current_guard_exits(
    native_queries, deny
):
    from flyquery.core.services.datasets.dataset_service import DatasetService
    from flyquery.core.services.query.runtime import StructuredQueryRuntimeFactory
    from pyfly.data.transaction import infrastructure_unit
    from pyfly.kernel import ConflictException

    from koinon.knowledge.adapters import NativeDomains
    from koinon.knowledge.bulk_queries.dtos import BatchQueryOutcome
    from koinon.knowledge.bulk_queries.native_repository import receipt_of
    from koinon.knowledge.bulk_queries.native_values import QueryOperationIdentity
    from koinon.workers.admission import WorkAdmission, WorkAdmissionSettings

    repository, metadata = native_queries
    selected = policy()
    identity = QueryOperationIdentity(
        operation_id=uuid4(),
        tenant_id="north",
        subject="owner",
        workspace_id=uuid4(),
        dataset_id=uuid4(),
        catalog_workspace_id="workspace",
        catalog_dataset_id="dataset",
        question="Count",
        policy_sha256=selected.digest,
        connections_sha256="a" * 64,
    )
    async with repository.write() as unit:
        await unit.session.execute(
            metadata.tables["flyquery_datasets"].insert(),
            values(
                metadata.tables["flyquery_datasets"],
                id=identity.dataset_id,
                tenant_id="north",
                workspace_id=identity.workspace_id,
                status="ACTIVE",
            ),
        )
        await unit.admit(identity)
    query_id = uuid4()
    answer = BatchQueryOutcome(
        query_id=query_id,
        execution_status="OK",
        sql="SELECT 1",
        preview=[{"value": 1}],
        row_count=1,
        elapsed_ms=1,
        knowledge_settings_snapshot=selected,
    )
    state = {"guard": False, "session": None, "committed": False}

    @asynccontextmanager
    async def runtime(**_):
        async with infrastructure_unit(repository.resources.native()) as session:
            state["session"] = session

            async def execute(**_):
                assert not state["guard"]
                await session.execute(
                    metadata.tables["flyquery_queries"].insert(),
                    values(
                        metadata.tables["flyquery_queries"],
                        id=query_id,
                        tenant_id="north",
                        workspace_id=identity.workspace_id,
                        dataset_id=identity.dataset_id,
                        question="Count",
                        executed_sql="SELECT 1",
                        execution_status="OK",
                        row_count=1,
                        elapsed_ms=1,
                    ),
                )
                return answer.model_dump(mode="json")

            yield SimpleNamespace(pipeline=SimpleNamespace(answer=execute))
            assert state["guard"]
        state["committed"] = True

    @asynccontextmanager
    async def bindings(*_, **__):
        yield

    @asynccontextmanager
    async def guard():
        state["guard"] = True
        try:
            yield
            assert state["committed"]
        finally:
            state["guard"] = False

    async def commit(raw):
        assert state["guard"]
        async with repository.write() as unit:
            assert unit.session is state["session"]
            await unit.commit(identity, BatchQueryOutcome.model_validate(raw))
            if deny:
                raise ConflictException("Revoked", code="ACCESS_DENIED")

    beans = {
        DatasetService: SimpleNamespace(
            get=AsyncMock(
                return_value={
                    "id": str(identity.dataset_id),
                    "tenant_id": "north",
                    "workspace_id": str(identity.workspace_id),
                }
            )
        ),
        StructuredQueryRuntimeFactory: SimpleNamespace(unit=runtime),
    }
    domains = NativeDomains(
        SimpleNamespace(
            contains_type=lambda kind: kind in beans,
            resolve=lambda kind: beans[kind],
            registered_types=lambda: [],
        ),
        WorkAdmission(WorkAdmissionSettings()),
    )
    domains.model_connections = bindings
    domains.model_requirements = lambda *_: ("query", ())

    async def run():
        return await domains.query(
            tenant_id="north",
            workspace_id=str(identity.workspace_id),
            dataset_id=str(identity.dataset_id),
            dataset_allowlist={str(identity.dataset_id)},
            question="Count",
            conversation_id=None,
            sql=None,
            actor="owner",
            _query_commit=commit,
            _query_publication_guard=guard,
        )

    if deny:
        with pytest.raises(ConflictException):
            await run()
    else:
        await run()
    async with repository.read() as unit:
        receipt = receipt_of(await unit.row(identity))
        saved = await unit.session.scalar(select(metadata.tables["flyquery_queries"].c.id))
        assert (
            (saved == query_id and receipt is not None) if not deny else (saved is None and receipt is None)
        )
