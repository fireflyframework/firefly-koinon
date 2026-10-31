# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest


@pytest.mark.parametrize("deny_commit", [False, True])
async def test_query_receipt_publication_holds_current_guard_through_native_commit_without_model_lock(
    deny_commit,
):
    from flyquery.core.services.datasets.dataset_service import DatasetService
    from flyquery.core.services.query.runtime import StructuredQueryRuntimeFactory
    from pyfly.kernel import ConflictException

    from koinon.knowledge.adapters import NativeDomains
    from koinon.workers.admission import WorkAdmission, WorkAdmissionSettings

    workspace, dataset = str(uuid4()), str(uuid4())
    events = []
    active = False
    output = {"query_id": str(uuid4()), "execution_status": "OK", "sql": "SELECT 1", "snapshot_pins": {}}

    async def answer(**values):
        assert active is False and values["conversation_id"] is None
        events.append("model")
        return output

    @asynccontextmanager
    async def unit(**values):
        events.append("native-enter")
        try:
            yield SimpleNamespace(pipeline=SimpleNamespace(answer=answer))
        except BaseException:
            events.append("rollback")
            raise
        else:
            assert active
            events.append("commit")

    @asynccontextmanager
    async def connections(*args, **kwargs):
        yield

    @asynccontextmanager
    async def publication():
        nonlocal active
        active = True
        events.append("guard-enter")
        try:
            yield
        finally:
            events.append("guard-exit")
            active = False

    async def receipt(value):
        assert active and value == output
        events.append("receipt")
        if deny_commit:
            raise ConflictException("Revoked", code="ACCESS_DENIED")

    services = {
        DatasetService: SimpleNamespace(
            get=AsyncMock(return_value={"id": dataset, "tenant_id": "north", "workspace_id": workspace})
        ),
        StructuredQueryRuntimeFactory: SimpleNamespace(unit=unit),
    }
    domains = NativeDomains(
        SimpleNamespace(
            contains_type=lambda kind: kind in services,
            resolve=lambda kind: services[kind],
            registered_types=lambda: [],
        ),
        WorkAdmission(WorkAdmissionSettings()),
    )
    domains.model_requirements = lambda *args: ("query", ())
    domains.model_connections = connections

    async def execute():
        return await domains.query(
            tenant_id="north",
            workspace_id=workspace,
            dataset_id=dataset,
            dataset_allowlist={dataset},
            question="Count",
            conversation_id=None,
            sql=None,
            actor="owner",
            _query_commit=receipt,
            _query_publication_guard=publication,
        )

    if deny_commit:
        with pytest.raises(ConflictException):
            await execute()
        assert "commit" not in events and events[-1] == "rollback"
    else:
        assert await execute() == output
        assert events == ["native-enter", "model", "guard-enter", "receipt", "commit", "guard-exit"]
