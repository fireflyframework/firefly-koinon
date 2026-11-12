# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Preserve original release selection while adding trusted attestations."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from koinon.answers.contexts import context_hash
from koinon.assistants.entities import ToolResult
from koinon.assistants.service import AssistantService


@pytest.mark.parametrize(
    "reset,expected",
    [
        (None, {"old", "new", "old-pin", "new-pin", "artifact", "refusal"}),
        (0, {"new", "new-pin", "artifact", "refusal"}),
        (5, {"new", "new-pin", "artifact", "refusal"}),
        (20, {"artifact", "refusal"}),
    ],
)
async def test_original_selection_preserves_reset_and_current_generation_semantics(reset, expected):
    now = datetime.now(UTC)
    rows = [
        ToolResult(
            id="old",
            run_id="run",
            kind="generation",
            payload={"generation": {"start_sequence": 1}},
            created_at=now,
        ),
        ToolResult(
            id="new",
            run_id="run",
            kind="generation",
            payload={"generation": {"start_sequence": 10}},
            created_at=now + timedelta(seconds=1),
        ),
        ToolResult(id="old-pin", run_id="run", kind="search", payload={"generation_id": "old"}),
        ToolResult(id="new-pin", run_id="run", kind="search", payload={"generation_id": "new"}),
        ToolResult(id="artifact", run_id="run", kind="search", payload={}),
        ToolResult(
            id="refusal",
            run_id="run",
            kind="answer_release",
            payload={
                "release": {"publication_sequence": 30},
                "generation_id": None,
                "reset_sequence": reset or 0,
                "seal_sha256": "a" * 64,
                "context_sha256": context_hash("a" * 64, reset or 0),
            },
        ),
    ]

    class Events:
        async def latest_reset(self, _run_id):
            return reset

    class Messages:
        async def find_by_id(self, _message_id):
            return SimpleNamespace(artifacts=[{"id": "artifact", "run_id": "run"}])

    service = SimpleNamespace(events=Events(), message_repository=Messages())
    selected = await AssistantService.active_results(
        service, SimpleNamespace(id="run", message_id="message"), rows
    )
    assert {row.id for row in selected} == expected
