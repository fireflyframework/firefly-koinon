# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Interrupted generation audit keeps correlation without copying protected content."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

from koinon.assistants.queue import AssistantQueue
from koinon.knowledge.capture_dtos import CapturedEvidence, NativeSqlAttempt, NativeTableSnapshot


async def test_denied_native_receipt_drops_sql_names_and_keeps_exact_digest():
    queue = AssistantQueue(
        SimpleNamespace(
            threads=SimpleNamespace(find_by_id=AsyncMock(return_value=SimpleNamespace(subject="owner")))
        )
    )
    capture = CapturedEvidence(
        {},
        (),
        False,
        sql_attempts=(
            NativeSqlAttempt(
                ordinal=1,
                stage="query",
                statement_sha256="a" * 64,
                classification="select",
                outcome="failed",
                executed=True,
                snapshot_pins={"SENSITIVE_table": "snapshot"},
                statement="SELECT SENSITIVE_column FROM SENSITIVE_table",
                database="SENSITIVE_database",
                tables=(NativeTableSnapshot("table-id", "SENSITIVE_table", "snapshot"),),
            ),
        ),
    )
    value = await queue.native_receipts(
        SimpleNamespace(tenant_id="north", thread_id="thread"),
        [],
        capture,
        "result",
        "generation",
        authorized=False,
    )
    assert "SENSITIVE_" not in json.dumps(value)
    assert value["sql_attempts"][0]["statement_sha256"] == "a" * 64
    assert value["sql_attempts"][0]["executed"] is True
    assert value["sql_attempts"][0]["result_id"] == "result"
