# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from flycanon.core.services.sources.async_ingest_service import AsyncIngestService
from flycanon.core.services.sources.lease import IngestLease, bind_ingest_lease


@pytest.mark.parametrize("origin", ["revoked", "unprovable", "stale", "current"])
async def test_document_callback_never_sends_from_revoked_unprovable_or_stale_execution(monkeypatch, origin):
    import httpx

    sent = []

    class Client:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, *args, **kwargs):
            sent.append(kwargs["content"])

    monkeypatch.setattr(httpx, "AsyncClient", Client)
    now = datetime.now(UTC)
    job = SimpleNamespace(
        id="job",
        tenant_id="north",
        workspace_id="workspace",
        attempts=1,
        started_at=now,
        status="succeeded",
        callback_url="https://receiver.invalid/callback",
        correlation_id=None,
    )
    current = SimpleNamespace(**vars(job))
    if origin == "stale":
        current.attempts = 2
    repository = SimpleNamespace(get=AsyncMock(return_value=current))
    service = AsyncIngestService(
        SimpleNamespace(),
        repository,
        SimpleNamespace(),
        SimpleNamespace(),
        SimpleNamespace(_require_model_bindings=True, webhook_secret=""),
    )

    async def authorize():
        if origin == "revoked":
            raise PermissionError("private origin credential details")

    if origin == "unprovable":
        await service._fire_webhook(job, status="succeeded")
    else:
        lease = IngestLease("job", "north", "workspace", 1, now, now + timedelta(seconds=60))
        with bind_ingest_lease(lease, authorize):
            await service._fire_webhook(job, status="succeeded")
    assert len(sent) == (1 if origin == "current" else 0)
