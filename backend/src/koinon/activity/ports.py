# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Read-only summary port shared by API, MCP and communications."""

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from koinon.activity.dtos import ActivitySummary, ActivityWindow

if TYPE_CHECKING:
    from koinon.activity.observations import McpObservation


@runtime_checkable
class ActivitySummaryReader(Protocol):
    async def personal(self, subject: str, tenant_id: str, window: ActivityWindow) -> ActivitySummary: ...

    async def administrative(
        self, subject: str, tenant_id: str, window: ActivityWindow
    ) -> ActivitySummary: ...


@runtime_checkable
class ActivityObservationRecorder(Protocol):
    async def record_mcp(self, observation: "McpObservation") -> None: ...
