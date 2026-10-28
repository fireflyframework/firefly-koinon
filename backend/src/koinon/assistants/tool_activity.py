# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Record actual native tool invocations without exposing their arguments or reasoning."""

import asyncio
from contextlib import suppress
from functools import wraps
from time import monotonic
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pyfly.kernel import ConflictException

from koinon.assistants.lifecycle import identifier, timestamp

ToolName = Literal[
    "search_knowledge",
    "inspect_schema",
    "query_dataset",
    "propose_catalog_update",
    "search_private_attachments",
]


class ToolActivity(BaseModel):
    model_config = ConfigDict(extra="forbid")
    call_id: str = Field(min_length=1, max_length=64)
    tool_name: ToolName
    status: Literal["queued", "running", "completed", "failed", "cancelled"]
    occurred_at: str
    started_at: str | None = None
    finished_at: str | None = None
    duration_ms: int | None = Field(default=None, ge=0)
    summary: str = Field(max_length=240)
    result_id: str | None = Field(default=None, max_length=64)


SUMMARIES = {
    "search_knowledge": "Search organization knowledge",
    "inspect_schema": "Inspect dataset schema",
    "query_dataset": "Query selected dataset",
    "search_private_attachments": "Search selected private files",
    "propose_catalog_update": "Propose a knowledge label change",
}


def tracked_tool(queue, authority, run_id: str, worker_id: str, tool_name: ToolName):
    def decorate(function):
        @wraps(function)
        async def invoke(*args, **kwargs):
            run, _, _, _ = await authority(run_id, worker_id)
            call_id, started, clock = identifier(), timestamp().isoformat(), monotonic()
            attempt = run.attempts

            async def emit(status, result=None):
                terminal = status in {"completed", "failed", "cancelled"}
                activity = ToolActivity(
                    call_id=call_id,
                    tool_name=tool_name,
                    status=status,
                    occurred_at=timestamp().isoformat(),
                    started_at=started if status != "queued" else None,
                    finished_at=timestamp().isoformat() if terminal else None,
                    duration_ms=max(0, int((monotonic() - clock) * 1000)) if terminal else None,
                    summary=SUMMARIES[tool_name],
                    result_id=result.get("evidence_id") if isinstance(result, dict) else None,
                )
                await queue.tool_activity(run_id, worker_id, attempt, activity)

            await emit("queued")
            await emit("running")
            try:
                result = await function(*args, **kwargs)
                await emit("completed", result)
                return result
            except asyncio.CancelledError:
                with suppress(Exception):
                    async with asyncio.timeout(1):
                        await emit("cancelled")
                raise
            except Exception as exc:
                state = (
                    "cancelled"
                    if isinstance(exc, ConflictException) and exc.code == "RUN_LEASE_LOST"
                    else "failed"
                )
                with suppress(Exception):
                    await emit(state)
                raise

        return invoke

    return decorate
