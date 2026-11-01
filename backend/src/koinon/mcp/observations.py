# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Best-effort observations of verified execution, without request payload capture."""

import asyncio
import logging
from collections.abc import Callable
from contextlib import suppress
from time import monotonic
from typing import Any, Literal
from uuid import uuid4

from mcp.server.auth.middleware.bearer_auth import AuthenticatedUser, authorization_context
from mcp.server.context import CallNext, HandlerResult, ServerRequestContext
from mcp.server.extension import Extension
from mcp.types import CallToolRequestParams, CallToolResult
from pyfly.observability.ports import MetricsRecorder
from pyfly.security.context import SecurityContext
from starlette.types import Scope

from koinon.activity.observations import McpObservation
from koinon.activity.ports import ActivityObservationRecorder
from koinon.mcp.transport_identity import MCP_TENANT_CLAIM, MCP_WORKSPACE_CLAIM

RecorderResolver = Callable[[], ActivityObservationRecorder]
MetricsResolver = Callable[[], MetricsRecorder | None]
Outcome = Literal["succeeded", "failed", "rejected", "cancelled"]
logger = logging.getLogger(__name__)
OBSERVATION_TIMEOUT_SECONDS = 3.0


def _identity(scope: Scope | None) -> tuple[str, str, str | None] | None:
    if scope is None:
        return None
    user = scope.get("user")
    context = scope.get("state", {}).get("security_context")
    if (
        not isinstance(user, AuthenticatedUser)
        or not user.access_token.expires_at
        or not isinstance(context, SecurityContext)
        or not context.is_authenticated
    ):
        return None
    identity = authorization_context(user)
    tenant = (user.access_token.claims or {}).get(MCP_TENANT_CLAIM)
    if (
        not isinstance(tenant, str)
        or not tenant
        or not identity["client_id"]
        or not identity["issuer"]
        or not identity["subject"]
        or identity["issuer"] != context.attributes.get("iss")
        or identity["subject"] != context.attributes.get("sub")
    ):
        return None
    workspaces = (user.access_token.claims or {}).get(MCP_WORKSPACE_CLAIM)
    workspace = (
        workspaces[0]
        if isinstance(workspaces, list)
        and len(workspaces) == 1
        and isinstance(workspaces[0], str)
        and 1 <= len(workspaces[0]) <= 64
        else None
    )
    return tenant, identity["issuer"] + "|" + identity["subject"], workspace


def _unavailable(metrics: MetricsResolver | None) -> None:
    with suppress(Exception, asyncio.CancelledError):
        logger.warning("MCP activity observation unavailable", extra={"code": "MCP_OBSERVATION_UNAVAILABLE"})
    if metrics is None:
        return
    try:
        recorder = metrics()
        if recorder is not None:
            recorder.counter(
                "koinon_mcp_observation_errors_total",
                "MCP activity observations unavailable",
                ["reason"],
            ).labels(reason="recording_unavailable").inc()
    except (Exception, asyncio.CancelledError):
        # Diagnostics must not alter an already completed domain operation.
        pass


async def observe(
    scope: Scope | None,
    kind: Literal["request", "tool"],
    operation: str,
    outcome: Outcome,
    started: float,
    recorder: RecorderResolver | None,
    metrics: MetricsResolver | None = None,
) -> None:
    if recorder is None:
        return

    async def record() -> None:
        identity = _identity(scope)
        if identity is None:
            return
        tenant, subject, workspace = identity
        observation = McpObservation(
            observation_id=uuid4(),
            tenant_id=tenant,
            subject=subject,
            # The sole authorized credential workspace; no executed-asset inference.
            workspace_id=workspace,
            kind=kind,
            operation=operation,
            outcome=outcome,
            duration_ms=min(86400000, max(0, int((monotonic() - started) * 1000))),
        )
        await recorder().record_mcp(observation)

    caller = asyncio.current_task()
    cancelling = caller.cancelling() if caller is not None else 0
    try:
        # A child distinguishes observer cancellation from cancellation of the request.
        # Deadline cancellation drains cooperative cleanup, including native rollback.
        await asyncio.wait_for(asyncio.create_task(record()), OBSERVATION_TIMEOUT_SECONDS)
    except asyncio.CancelledError:
        if caller is not None and caller.cancelling() > cancelling:
            raise
        _unavailable(metrics)
    except Exception:
        _unavailable(metrics)


class McpActivityExtension(Extension):
    identifier = "org.fireflyframework.koinon/activity"

    def __init__(
        self,
        tools: frozenset[str],
        recorder: RecorderResolver,
        metrics: MetricsResolver | None = None,
    ):
        self.tool_names, self.recorder, self.metrics = tools, recorder, metrics

    async def intercept_tool_call(
        self, params: CallToolRequestParams, ctx: ServerRequestContext[Any, Any], call_next: CallNext
    ) -> HandlerResult:
        started = monotonic()
        outcome: Outcome = "failed"
        try:
            result = await call_next(ctx)
            outcome = "failed" if isinstance(result, CallToolResult) and result.is_error else "succeeded"
            return result
        except asyncio.CancelledError:
            outcome = "cancelled"
            raise
        finally:
            request = ctx.request
            await observe(
                request.scope if request is not None else None,
                "tool",
                params.name if params.name in self.tool_names else "koinon_unknown",
                outcome,
                started,
                self.recorder,
                self.metrics,
            )
