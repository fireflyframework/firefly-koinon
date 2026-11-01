# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Count canonical knowledge pieces once, without retaining their content."""

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo

from koinon.activity.dtos import KnowledgeActivityCounts, ObservedCount

KnowledgeAction = Literal["created", "updated", "consulted"]


@dataclass(frozen=True, slots=True)
class ActivityCatalogNode:
    id: str
    tenant_id: str
    parent_id: str | None
    workspace_id: str | None
    project_id: str | None
    kind: str
    status: str
    name: str
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class KnowledgeObservation:
    asset_id: str
    action: KnowledgeAction
    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class KnowledgeActivity:
    counts: KnowledgeActivityCounts
    daily: dict[str, KnowledgeActivityCounts]


def summarize_knowledge(
    observations: Iterable[KnowledgeObservation], *, time_zone: str, partial: bool
) -> KnowledgeActivity:
    zone = ZoneInfo(time_zone)
    pieces: dict[KnowledgeAction, set[str]] = defaultdict(set)
    days: dict[str, dict[KnowledgeAction, set[str]]] = defaultdict(lambda: defaultdict(set))
    for observation in observations:
        if observation.occurred_at.tzinfo is None:
            raise ValueError("Knowledge activity requires timezone-aware timestamps")
        pieces[observation.action].add(observation.asset_id)
        day = observation.occurred_at.astimezone(zone).date().isoformat()
        days[day][observation.action].add(observation.asset_id)

    def counts(values: dict[KnowledgeAction, set[str]]) -> KnowledgeActivityCounts:
        def count(action: KnowledgeAction) -> ObservedCount:
            return ObservedCount(
                value=len(values.get(action, ())),
                status="partial" if partial or action == "consulted" else "observed",
                reason="bounded_history"
                if partial
                else "exact_source_receipts_only"
                if action == "consulted"
                else None,
            )

        return KnowledgeActivityCounts(
            created=count("created"), updated=count("updated"), consulted=count("consulted")
        )

    return KnowledgeActivity(counts(pieces), {day: counts(days[day]) for day in sorted(days)})
