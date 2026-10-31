# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import asyncio
from dataclasses import replace
from unittest.mock import AsyncMock

import pytest
from flycanon.core.services.query import provenance
from flycanon.core.services.query.rlm.actions import RlmToolReceipt
from pyfly.kernel import ServiceUnavailableException

from koinon.knowledge.capture_dtos import CapturedEvidence, NativeCaptureLimits, NativeSqlAttempt
from koinon.knowledge.capture_receipt import NativeEvidenceReceipt
from koinon.knowledge.evidence_capture import checked_capture


def tool():
    return RlmToolReceipt(tool_call_id="real-call", tool_name="final_answer", request_sha256="a" * 64,
        schema_sha256="b" * 64, arguments_sha256="c" * 64, result_sha256="d" * 64,
        result_kind="accepted_final", execution_sha256="e" * 64,
        outcome="halted", execution_status="halted", execution_state="halted")


async def record(receipt):
    with provenance.observe(receipt, tenant_id="tenant", workspace_id="native", actor="owner"):
        provenance.current().source_ids.add("source")
        def execute():
            provenance.before_tool()
            provenance.tool(tool())
        await asyncio.to_thread(provenance.worker(execute))


def receipt(limits=None):
    value = NativeEvidenceReceipt("owner", "tenant", limits=limits)
    value.canonical_documents[("native", "source")] = "asset"
    value.authorize_model = AsyncMock()
    return value


async def test_zero_sql_budget_still_admits_actual_rlm_tool_and_keeps_unknown_legacy():
    value = receipt(NativeCaptureLimits(attempts=0))
    assert CapturedEvidence({}, (), False).rlm_tools is None
    await record(value)
    capture = checked_capture(value, {}, (), False)
    assert len(capture.rlm_tools) == 1 and capture.sql_attempts == () and capture.native_reads == ()
    assert capture.rlm_tools[0].source_ids == ("source",)


async def test_tool_zero_budget_denies_before_execution_and_never_uses_sql_counter():
    value = receipt(NativeCaptureLimits(tools=0, attempts=2))
    with pytest.raises(ServiceUnavailableException) as failure:
        await record(value)
    assert failure.value.code == "EVIDENCE_BUDGET_EXCEEDED"
    assert value.rlm_tools is None and value.sql_attempts == ()


async def test_mixed_sql_and_rlm_use_independent_counts_but_shared_bytes():
    value = receipt(NativeCaptureLimits(attempts=1, tools=1))
    value._attempts.append(NativeSqlAttempt(1, "execution", "e" * 64, "SELECT", "succeeded", True, {}))
    await record(value)
    value.budget.check(value)
    with pytest.raises(ServiceUnavailableException):
        value.budget.check(value, minimum_attempts=1)
    with pytest.raises(ServiceUnavailableException):
        value.budget.check(value, minimum_tools=1)
    value.budget.limits = replace(value.limits, receipt_bytes=100)
    with pytest.raises(ServiceUnavailableException):
        value.budget.check(value)


async def test_tool_hook_denies_unleased_wrong_or_expired_scope():
    value = receipt()
    with provenance.observe(value, tenant_id="tenant", workspace_id="native", actor="owner") as scope:
        scope = provenance.current()
        scope.source_ids.add("source")
        with pytest.raises(ServiceUnavailableException):
            value.document_tool(tool(), scope)
    with pytest.raises(ServiceUnavailableException):
        value.document_tool(tool(), scope)
