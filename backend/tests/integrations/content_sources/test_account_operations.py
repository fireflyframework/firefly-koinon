# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Verified account identity is independent of local grants and unambiguous."""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest
from pyfly.client import HttpxClientAdapter
from test_remote_sources import Tokens

from koinon.integrations.content_sources.account_operation_dtos import (
    AccountOperationLease,
    AccountOperationRequest,
)
from koinon.integrations.content_sources.account_operations import (
    AccountOperationPermit,
    SourceAccountOperations,
    account_identity,
)
from koinon.integrations.content_sources.dtos import Account
from koinon.integrations.content_sources.entities import PersonalSourceConnection
from koinon.integrations.content_sources.errors import SourceError
from koinon.integrations.content_sources.transport import SourceTransport, source_operation_deadline


def connection(**changes):
    values = dict(
        id="one",
        tenant_id="tenant",
        owner="alice",
        provider="onedrive",
        revision=1,
        issuer="https://login.microsoftonline.com/external/v2.0",
        external_tenant="external",
        external_subject="subject",
        status="connected",
    )
    return PersonalSourceConnection(**(values | changes))


def test_verified_account_shares_capacity_across_grants_and_microsoft_products():
    first = account_identity(connection())
    second = account_identity(connection(id="two", owner="bob", revision=8, provider="sharepoint"))
    assert first == second
    assert first != account_identity(connection(tenant_id="other"))
    assert first != account_identity(connection(provider="google_drive"))
    assert first != account_identity(connection(issuer="https://another.example"))


def test_account_encoding_keeps_null_empty_and_component_boundaries_distinct():
    cases = [
        connection(external_tenant=None),
        connection(external_tenant=""),
        connection(external_tenant="a", external_subject="bc"),
        connection(external_tenant="ab", external_subject="c"),
    ]
    assert len({account_identity(row).account_key for row in cases}) == len(cases)


@pytest.mark.parametrize("changes", [{"issuer": None}, {"issuer": ""}, {"external_subject": None}])
def test_legacy_identity_requires_reconnect(changes):
    with pytest.raises(SourceError) as failure:
        account_identity(connection(**changes))
    assert failure.value.code == "reconnect_required"


async def test_expired_deadline_denies_http_and_does_not_poison_next_operation():
    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(200, json={"ok": True})

    client = HttpxClientAdapter(
        client=httpx.AsyncClient(transport=httpx.MockTransport(handle)), owns_client=True
    )
    transport = SourceTransport(
        Account("google_drive", "subject"), Tokens(), host="example.com", http_client=client
    )
    try:
        with source_operation_deadline(asyncio.get_running_loop().time() - 1):
            with pytest.raises(SourceError) as failure:
                async with transport.request("https://example.com/item"):
                    pytest.fail("Expired operation reached HTTP")
            assert failure.value.code == "timeout" and requests == []
        async with transport.request("https://example.com/item") as response:
            assert response.status_code == 200
        assert len(requests) == 1
    finally:
        await client.stop()


async def test_copied_deadline_context_cannot_outlive_its_source_slice():
    ready, proceed = asyncio.Event(), asyncio.Event()
    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(200, json={})

    client = HttpxClientAdapter(
        client=httpx.AsyncClient(transport=httpx.MockTransport(handle)), owns_client=True
    )
    transport = SourceTransport(
        Account("google_drive", "subject"), Tokens(), host="example.com", http_client=client
    )

    async def delayed_request():
        ready.set()
        await proceed.wait()
        with pytest.raises(SourceError) as failure:
            async with transport.request("https://example.com/item"):
                pytest.fail("Closed inherited context reached HTTP")
        return failure.value.code

    try:
        with source_operation_deadline(asyncio.get_running_loop().time() + 120):
            child = asyncio.create_task(delayed_request())
            await ready.wait()
        proceed.set()
        assert await child == "timeout"
        assert requests == []
    finally:
        await client.stop()


async def test_nested_deadline_caps_actual_transport_timeouts():
    timeouts = []

    def handle(request):
        timeouts.append(request.extensions["timeout"])
        return httpx.Response(200, json={})

    client = HttpxClientAdapter(
        client=httpx.AsyncClient(transport=httpx.MockTransport(handle)), owns_client=True
    )
    transport = SourceTransport(
        Account("google_drive", "subject"), Tokens(), host="example.com", http_client=client
    )
    try:
        now = asyncio.get_running_loop().time()
        with source_operation_deadline(now + 3), source_operation_deadline(now + 120):
            async with transport.request("https://example.com/item") as response:
                assert response.status_code == 200
        assert len(timeouts) == 1 and all(0 < value <= 3 for value in timeouts[0].values())
    finally:
        await client.stop()


@pytest.mark.parametrize("cleanup_fails", [False, True])
async def test_cleanup_failure_cannot_impersonate_confirmed_access_denial(monkeypatch, cleanup_fails):
    now = datetime.now(UTC)
    permit = AccountOperationPermit(
        AccountOperationLease(
            identity=account_identity(connection()),
            operation=AccountOperationRequest(
                kind="validation",
                operation_id="operation",
                revision=1,
                connection_id="one",
                connection_revision=1,
                owner="alice",
                process_instance_id="process",
            ),
            token=uuid4(),
            fence=1,
            ticket=1,
            started_at=now,
            expires_at=now + timedelta(seconds=150),
        ),
        asyncio.get_running_loop().time() + 120,
        asyncio.current_task(),
    )
    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(403, json={})

    client = HttpxClientAdapter(
        client=httpx.AsyncClient(transport=httpx.MockTransport(handle)), owns_client=True
    )
    transport = SourceTransport(
        Account("google_drive", "subject"),
        Tokens(),
        host="example.com",
        http_client=client,
        owns_http_client=True,
    )
    original_stop = client.stop

    async def failed_close():
        raise SourceError("access_denied")

    if cleanup_fails:
        monkeypatch.setattr(client, "stop", failed_close)
    try:
        with pytest.raises(SourceError) as failure:
            async with SourceAccountOperations(None).remote(permit):
                try:
                    async with transport.request("https://example.com/item"):
                        pytest.fail("Denied HTTP request reached body")
                finally:
                    await transport.aclose()
        assert failure.value.code == "access_denied"
        assert len(requests) == 1
        assert permit.completion.settled is (not cleanup_fails)
    finally:
        await original_stop()
