# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Logical MCP invocation observations over fresh native request authority."""

import asyncio
from datetime import UTC, datetime, timedelta
from time import monotonic
from types import SimpleNamespace
from uuid import UUID

import httpx
import pytest
from http_fixtures import configured_client
from mcp.server.auth.middleware.bearer_auth import AuthenticatedUser
from mcp.server.auth.provider import AccessToken
from mcp.types import CallToolRequestParams, CallToolResult
from pyfly.security.context import SecurityContext
from starlette.requests import Request
from starlette.responses import JSONResponse

from koinon.mcp.http import McpHttpBoundary
from koinon.mcp.observations import McpActivityExtension, observe
from koinon.mcp.transport_identity import transport_identity


class Recorder:
    def __init__(self):
        self.values = []

    async def record_mcp(self, observation):
        self.values.append(observation)


class Metrics:
    def __init__(self):
        self.calls = []

    def counter(self, name, description, labels=None):
        self.calls.append((name, tuple(labels or [])))
        return self

    def labels(self, **values):
        self.calls.append(values)
        return self

    def inc(self):
        self.calls.append("inc")


def scope(tenant="north", subject="person", *, mismatch=False):
    return {
        "type": "http",
        "path": "/mcp",
        "method": "POST",
        "headers": [],
        "state": {
            "security_context": SecurityContext(
                user_id="https://issuer.example|" + subject,
                attributes={"iss": "https://issuer.example", "sub": "someone-else" if mismatch else subject},
            )
        },
        "user": AuthenticatedUser(
            AccessToken(
                token="synthetic-private-token",
                client_id="server-grant-fingerprint",
                subject=subject,
                claims={"iss": "https://issuer.example", "koinon_tenant_id": tenant},
                scopes=["catalog:read"],
                expires_at=int((datetime.now(UTC) + timedelta(hours=1)).timestamp()),
            )
        ),
    }


async def test_transport_identity_projects_current_grant_tenant_not_claimed_context():
    grant = SimpleNamespace(
        id="grant",
        subject="https://issuer.example|person",
        tenant_id="north",
        purpose="personal",
        authorized_application_id=None,
        scopes=["catalog:read"],
        workspace_ids=["workspace"],
        asset_ids=None,
        resource_ids=None,
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )

    class Restriction:
        async def grant(self, subject):
            assert subject == grant.subject
            return grant

    context = SecurityContext(
        user_id=grant.subject,
        attributes={
            "iss": "https://issuer.example",
            "sub": "person",
            "koinon_tenant_id": "attacker-tenant",
        },
    )
    _, user = await transport_identity(context, "synthetic-private-token", Restriction())
    assert user.access_token.claims["koinon_tenant_id"] == "north"


async def test_tool_invocation_records_one_fixed_label_without_arguments_or_rpc_identifier():
    recorder = Recorder()
    extension = McpActivityExtension(frozenset({"koinon_search"}), lambda: recorder)
    request = Request(scope())
    ctx = SimpleNamespace(request=request)
    params = CallToolRequestParams(
        name="koinon_search",
        arguments={
            "tenant_id": "attacker-tenant",
            "question": "synthetic-private-question",
            "workspace_id": "unproven",
        },
    )

    async def result(ctx):
        return CallToolResult(is_error=True, content=[])

    returned = await extension.intercept_tool_call(params, ctx, result)
    assert returned.is_error and len(recorder.values) == 1
    value = recorder.values[0]
    assert isinstance(value.observation_id, UUID)
    assert (value.kind, value.operation, value.outcome) == ("tool", "koinon_search", "failed")
    assert value.tenant_id == "north" and value.subject == "https://issuer.example|person"
    assert value.workspace_id is None and type(value.duration_ms) is int and value.duration_ms >= 0
    wire = value.model_dump_json()
    assert all(secret not in wire for secret in ["attacker-tenant", "synthetic-private", "unproven"])


async def test_tool_cancellation_is_recorded_and_propagated():
    recorder, entered = Recorder(), asyncio.Event()
    extension = McpActivityExtension(frozenset({"koinon_query"}), lambda: recorder)

    async def blocked(ctx):
        entered.set()
        await asyncio.Event().wait()

    task = asyncio.create_task(
        extension.intercept_tool_call(
            CallToolRequestParams(name="koinon_query"),
            SimpleNamespace(request=Request(scope())),
            blocked,
        )
    )
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert len(recorder.values) == 1 and recorder.values[0].outcome == "cancelled"


async def test_concurrent_tool_requests_keep_tenants_and_generated_ids_separate():
    recorder = Recorder()
    extension = McpActivityExtension(frozenset({"koinon_context"}), lambda: recorder)

    async def result(ctx):
        await asyncio.sleep(0)
        return CallToolResult(content=[])

    await asyncio.gather(
        *(
            extension.intercept_tool_call(
                CallToolRequestParams(name="koinon_context"),
                SimpleNamespace(request=Request(scope(tenant, tenant))),
                result,
            )
            for tenant in ("north", "south")
        )
    )
    assert {(v.tenant_id, v.subject) for v in recorder.values} == {
        ("north", "https://issuer.example|north"),
        ("south", "https://issuer.example|south"),
    }
    assert len({v.observation_id for v in recorder.values}) == 2


async def test_unknown_tool_names_are_not_unbounded_observation_labels():
    recorder = Recorder()
    extension = McpActivityExtension(frozenset({"koinon_context"}), lambda: recorder)

    async def denied(ctx):
        return CallToolResult(is_error=True, content=[])

    await extension.intercept_tool_call(
        CallToolRequestParams(name="synthetic-private-unknown-name"),
        SimpleNamespace(request=Request(scope())),
        denied,
    )
    assert recorder.values[0].operation == "koinon_unknown"


async def test_unverified_or_mismatched_identity_is_never_attributed():
    recorder = Recorder()
    for value in ({"type": "http", "path": "/mcp"}, scope(mismatch=True)):
        await observe(value, "request", "POST", "succeeded", monotonic(), lambda: recorder)
    assert not recorder.values


async def test_recorder_failure_has_only_safe_counter_and_cannot_change_success(caplog):
    class Broken:
        async def record_mcp(self, observation):
            raise RuntimeError("synthetic-private-observer-error")

    metrics = Metrics()
    await observe(scope(), "request", "POST", "succeeded", monotonic(), lambda: Broken(), lambda: metrics)
    assert metrics.calls == [
        ("koinon_mcp_observation_errors_total", ("reason",)),
        {"reason": "recording_unavailable"},
        "inc",
    ]
    assert "synthetic-private" not in caplog.text and "person" not in caplog.text


@pytest.mark.parametrize("status,outcome", [(200, "succeeded"), (403, "rejected"), (500, "failed")])
async def test_http_observation_waits_for_native_auth_and_records_status_without_reading_body(
    status, outcome
):
    recorder = Recorder()

    async def app(value, receive, send):
        value.update(scope())
        await JSONResponse({"synthetic-private-body": True}, status_code=status)(value, receive, send)

    boundary = McpHttpBoundary(app, SimpleNamespace(max_concurrency=2), activity_recorder=lambda: recorder)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(boundary), base_url="http://testserver"
    ) as client:
        response = await client.post("/mcp", json={"secret": "synthetic-private-query"})
    assert response.status_code == status and len(recorder.values) == 1
    assert recorder.values[0].outcome == outcome and recorder.values[0].operation == "POST"


@pytest.fixture
def observed_client(tmp_path, monkeypatch, request):
    import koinon.app

    recorder, metrics = Recorder(), Metrics()
    original = koinon.app.create_mcp_server

    def observed_server(*args, **kwargs):
        return original(
            *args, **(kwargs | {"activity_recorder": lambda: recorder, "activity_metrics": lambda: metrics})
        )

    def observed_boundary(*args, **kwargs):
        return McpHttpBoundary(
            *args, **(kwargs | {"activity_recorder": lambda: recorder, "activity_metrics": lambda: metrics})
        )

    monkeypatch.setattr(koinon.app, "create_mcp_server", observed_server)
    monkeypatch.setattr(koinon.app, "McpHttpBoundary", observed_boundary)
    for client in configured_client(tmp_path, monkeypatch, request):
        yield client, recorder


def test_native_http_counts_each_tool_once_with_fresh_pat_bound_tenant_and_revocation(observed_client):
    from test_mcp_http import bearer, call, create_pat

    client, recorder = observed_client
    token = create_pat(client)
    assert not recorder.values
    accepted = call(client, token["token"], "koinon_context")
    assert accepted.status_code == 200 and not accepted.json()["result"]["isError"]
    denied = call(client, token["token"], "koinon_list", {"tenant_id": "south"}, **{"X-Tenant-ID": "south"})
    assert denied.status_code == 200 and denied.json()["result"]["isError"]
    assert len(recorder.values) == 4
    assert [v.kind for v in recorder.values] == ["tool", "request", "tool", "request"]
    assert [v.outcome for v in recorder.values] == ["succeeded", "succeeded", "failed", "succeeded"]
    assert {v.tenant_id for v in recorder.values} == {"north"}
    assert all(v.workspace_id is None for v in recorder.values)
    assert client.delete("/api/v1/tokens/" + token["id"], headers=bearer()).status_code == 204
    assert call(client, token["token"], "koinon_context").status_code == 401
    assert len(recorder.values) == 4


async def test_failed_recording_cannot_replace_tool_success_or_cancellation(caplog):
    class Broken:
        async def record_mcp(self, observation):
            raise RuntimeError("synthetic-private-storage-failure")

    metrics = Metrics()
    extension = McpActivityExtension(frozenset({"koinon_context"}), lambda: Broken(), lambda: metrics)
    expected = CallToolResult(content=[])

    async def succeeded(ctx):
        return expected

    params, ctx = CallToolRequestParams(name="koinon_context"), SimpleNamespace(request=Request(scope()))
    assert await extension.intercept_tool_call(params, ctx, succeeded) is expected

    async def cancelled(ctx):
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await extension.intercept_tool_call(params, ctx, cancelled)
    assert metrics.calls.count("inc") == 2 and "synthetic-private" not in caplog.text


async def test_cancelled_http_call_preserves_cancellation_and_one_observation():
    entered, recorder = asyncio.Event(), Recorder()

    async def app(value, receive, send):
        value.update(scope())
        entered.set()
        await asyncio.Event().wait()

    boundary = McpHttpBoundary(app, SimpleNamespace(max_concurrency=2), activity_recorder=lambda: recorder)

    async def unused(*args):
        pytest.fail("The suspended fixture has no request/response IO")

    task = asyncio.create_task(boundary(scope(), unused, unused))
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert len(recorder.values) == 1 and recorder.values[0].outcome == "cancelled"


async def test_metric_resolver_failure_cannot_change_success_or_expose_error(caplog):
    def failed():
        raise RuntimeError("synthetic-private-resolver-error")

    await observe(scope(), "request", "POST", "succeeded", monotonic(), failed, failed)
    assert "synthetic-private" not in caplog.text


def test_legacy_apps_denial_and_success_each_have_one_outer_tool_observation(observed_client):
    from test_mcp_http import create_pat
    from test_mcp_legacy_sessions import initialize, legacy_call

    client, recorder = observed_client
    token = create_pat(client, scopes=["catalog:read", "ingest:write"])["token"]
    session = initialize(client, token, apps=False)
    assert len(recorder.values) == 2 and all(v.kind == "request" for v in recorder.values)
    recorder.values.clear()
    denied = legacy_call(client, token, session, "koinon_stage_knowledge", {})
    assert denied.status_code == 200 and denied.json()["result"]["isError"]
    allowed = legacy_call(client, token, session, "koinon_context", {})
    assert allowed.status_code == 200 and not allowed.json()["result"]["isError"]
    assert [v.kind for v in recorder.values] == ["tool", "request", "tool", "request"]
    assert [v.outcome for v in recorder.values] == ["failed", "succeeded", "succeeded", "succeeded"]
    assert {v.tenant_id for v in recorder.values} == {"north"}
    assert len({v.observation_id for v in recorder.values}) == 4


async def test_broken_diagnostics_or_missing_identity_cannot_fail_completed_operation(monkeypatch):
    from koinon.mcp import observations

    def broken(*args, **kwargs):
        raise RuntimeError("synthetic-private-diagnostic-error")

    metrics = Metrics()
    monkeypatch.setattr(observations.logger, "warning", broken)
    await observe(scope(), "request", "POST", "succeeded", monotonic(), broken, lambda: metrics)
    assert metrics.calls[-1] == "inc"
    value = scope()
    value["state"] = None
    await observe(value, "request", "POST", "succeeded", monotonic(), lambda: Recorder())


async def test_observer_origin_cancellation_cannot_replace_tool_success():
    class Cancelled:
        async def record_mcp(self, observation):
            raise asyncio.CancelledError

    metrics = Metrics()
    extension = McpActivityExtension(frozenset({"koinon_context"}), lambda: Cancelled(), lambda: metrics)
    expected = CallToolResult(content=[])

    async def succeeded(ctx):
        return expected

    returned = await extension.intercept_tool_call(
        CallToolRequestParams(name="koinon_context"),
        SimpleNamespace(request=Request(scope())),
        succeeded,
    )
    assert returned is expected and metrics.calls.count("inc") == 1


async def test_observer_deadline_cancels_and_drains_cooperative_callback_without_failing_success(monkeypatch):
    from koinon.mcp import observations

    monkeypatch.setattr(observations, "OBSERVATION_TIMEOUT_SECONDS", 0.02, raising=False)
    drained, metrics = asyncio.Event(), Metrics()

    class Slow:
        async def record_mcp(self, observation):
            try:
                await asyncio.Event().wait()
            finally:
                drained.set()

    extension = McpActivityExtension(frozenset({"koinon_context"}), lambda: Slow(), lambda: metrics)
    expected = CallToolResult(content=[])

    async def succeeded(ctx):
        return expected

    returned = await asyncio.wait_for(
        extension.intercept_tool_call(
            CallToolRequestParams(name="koinon_context"),
            SimpleNamespace(request=Request(scope())),
            succeeded,
        ),
        0.3,
    )
    assert returned is expected and drained.is_set() and metrics.calls.count("inc") == 1


@pytest.mark.parametrize("origin", ["logger", "metrics"])
async def test_diagnostics_origin_cancellation_cannot_replace_success(monkeypatch, origin):
    from koinon.mcp import observations

    def cancelled(*args, **kwargs):
        raise asyncio.CancelledError

    class Broken:
        async def record_mcp(self, observation):
            raise RuntimeError("synthetic-private-observer-error")

    metrics = Metrics()
    if origin == "logger":
        monkeypatch.setattr(observations.logger, "warning", cancelled)
    else:
        monkeypatch.setattr(metrics, "counter", cancelled)
    await observe(scope(), "request", "POST", "succeeded", monotonic(), lambda: Broken(), lambda: metrics)


async def test_genuine_caller_cancellation_during_observation_still_propagates_and_drains():
    entered, drained = asyncio.Event(), asyncio.Event()

    class Slow:
        async def record_mcp(self, observation):
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                drained.set()

    task = asyncio.create_task(observe(scope(), "request", "POST", "succeeded", monotonic(), lambda: Slow()))
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert drained.is_set()


async def test_workspace_label_tracks_only_sole_current_unrestricted_grant():
    grant = SimpleNamespace(
        id="grant",
        subject="https://issuer.example|person",
        tenant_id="north",
        purpose="personal",
        authorized_application_id=None,
        scopes=["catalog:read"],
        workspace_ids=["first"],
        asset_ids=None,
        resource_ids=None,
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )

    class Restriction:
        async def grant(self, subject):
            return grant

    context = SecurityContext(
        user_id=grant.subject, attributes={"iss": "https://issuer.example", "sub": "person"}
    )
    recorder = Recorder()
    for workspaces, assets in [
        (["first"], None),
        (["second"], None),
        (["first", "second"], None),
        (["first"], ["asset"]),
    ]:
        grant.workspace_ids, grant.asset_ids = workspaces, assets
        _, user = await transport_identity(context, "synthetic-private-token", Restriction())
        value = scope()
        value["user"] = user
        value["headers"] = [(b"x-workspace-id", b"forged")]
        await observe(value, "request", "POST", "succeeded", monotonic(), lambda: recorder)
    assert [value.workspace_id for value in recorder.values] == ["first", "second", None, None]


def test_native_workspace_bound_pat_labels_credential_scope_without_header_inference(observed_client):
    from test_mcp_http import call, create_pat

    client, recorder = observed_client
    token = create_pat(client, workspace_ids=[client.workspace_id])["token"]
    result = call(client, token, "koinon_context", **{"X-Workspace-ID": "forged"})
    assert result.status_code == 200 and not result.json()["result"]["isError"]
    assert len(recorder.values) == 2 and {value.workspace_id for value in recorder.values} == {
        client.workspace_id
    }
