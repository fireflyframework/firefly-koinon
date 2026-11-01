# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Observation writes complete independently from the observed business operation."""

from pyfly.container import service
from pyfly.data.relational.sqlalchemy import transactional
from pyfly.data.transaction import Propagation

from koinon.activity.observations import McpObservation
from koinon.activity.ports import ActivityObservationRecorder
from koinon.activity.repositories import ActivityEventRepository


@service(name="activity.observations")
class ActivityObservationService(ActivityObservationRecorder):
    def __init__(self, events: ActivityEventRepository):
        self.events = events

    @transactional(datasource="primary", propagation=Propagation.REQUIRES_NEW, timeout=2)
    async def record_mcp(self, observation: McpObservation) -> None:
        await self.events.append(observation)
