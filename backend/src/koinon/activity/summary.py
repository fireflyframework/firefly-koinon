# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Release content-free summaries only under fresh native primary authority."""

import json
from collections import defaultdict
from datetime import timedelta
from hashlib import sha256
from zoneinfo import ZoneInfo

from pyfly.container import service
from pyfly.data.transaction import Isolation, Propagation, TransactionTemplate

from koinon.activity.authority import ActivityAccess
from koinon.activity.dtos import (
    ActivityCoverage,
    ActivitySummary,
    ActivityWindow,
    DailyActivity,
    ModelActivityCounts,
    ObservedCost,
    ObservedCount,
    ProjectActivity,
)
from koinon.activity.knowledge_repository import KnowledgeActivityRepository
from koinon.activity.knowledge_values import KnowledgeObservation, summarize_knowledge
from koinon.activity.ports import ActivitySummaryReader
from koinon.activity.repositories import ActivityEventRepository
from koinon.catalog.errors import AccessDenied
from koinon.catalog.service import CatalogService
from koinon.security.authority import PRIMARY_POLICY_UNIT


def unavailable(reason: str) -> ObservedCount:
    return ObservedCount(status="unavailable", reason=reason)


@service(name="activity.summary")
class ActivitySummaryService(ActivitySummaryReader):
    def __init__(
        self,
        catalog: CatalogService,
        access: ActivityAccess,
        knowledge: KnowledgeActivityRepository,
        events: ActivityEventRepository,
    ):
        self.catalog, self.access, self.knowledge, self.events = catalog, access, knowledge, events

    async def personal(self, subject: str, tenant_id: str, window: ActivityWindow) -> ActivitySummary:
        return await self._read(subject, tenant_id, window, administrative=False)

    async def administrative(self, subject: str, tenant_id: str, window: ActivityWindow) -> ActivitySummary:
        return await self._read(subject, tenant_id, window, administrative=True)

    @staticmethod
    def _snapshot():
        return TransactionTemplate(
            "primary",
            name=PRIMARY_POLICY_UNIT,
            propagation=Propagation.REQUIRES_NEW,
            isolation=Isolation.SERIALIZABLE,
            read_only=True,
            read_from_primary=True,
        ).transaction()

    async def _visible(self, subject, tenant_id, asset_id):
        try:
            entry = await self.knowledge.node(tenant_id, asset_id)
            if entry is None:
                return None
            await self.catalog.authorize(subject, tenant_id, "catalog:read", entry.workspace_id)
            if self.catalog.restriction:
                await self.catalog.restriction.resource(
                    subject, entry, parent_reader=lambda key: self.knowledge.node(tenant_id, key)
                )
            if entry.kind == "knowledge_item":
                bounds = await self.catalog.curated_read_bounds(subject, tenant_id)
                if not await self.catalog.catalog_repository.curated_visible(tenant_id, entry.id, **bounds):
                    return None
        except AccessDenied:
            return None
        if entry.kind not in {"document", "dataset", "knowledge_item"}:
            return None
        current, seen, stamp = entry, set(), []
        while current is not None and len(seen) < 16 and current.id not in seen:
            if current.tenant_id != tenant_id or current.status == "archived":
                return None
            stamp.append(
                (
                    current.id,
                    current.parent_id,
                    current.workspace_id,
                    current.project_id,
                    current.kind,
                    current.status,
                    current.name,
                    current.updated_at.isoformat(),
                )
            )
            seen.add(current.id)
            if current.parent_id is None:
                return entry, stamp
            current = await self.knowledge.node(tenant_id, current.parent_id)
        return None

    async def _read(self, subject, tenant_id, window, *, administrative):
        async with self._snapshot():
            authority = await self.access.resolve(subject, tenant_id, administrative=administrative)
            observations, bounded = await self.knowledge.observations(
                tenant_id, None if administrative else subject, window
            )
            visible, stamps, projects = {}, {}, {}
            for asset_id in dict.fromkeys(value.asset_id for value in observations):
                admitted = await self._visible(subject, tenant_id, asset_id)
                if admitted is not None:
                    entry, stamp = admitted
                    visible[asset_id], stamps[asset_id] = entry, stamp
                    if entry.project_id and entry.project_id not in projects:
                        project = await self.knowledge.node(tenant_id, entry.project_id)
                        if (
                            project is not None
                            and project.tenant_id == tenant_id
                            and project.kind == "project"
                            and project.workspace_id
                        ):
                            projects[project.id] = project
            admitted_values = [value for value in observations if value.asset_id in visible]
            counts = summarize_knowledge(admitted_values, time_zone=window.time_zone, partial=bounded)
            by_project: dict[str, list[KnowledgeObservation]] = defaultdict(list)
            for value in admitted_values:
                project_id = visible[value.asset_id].project_id
                if project_id in projects:
                    by_project[project_id].append(value)
            top = [
                ProjectActivity(
                    project_id=key,
                    workspace_id=projects[key].workspace_id,
                    name=projects[key].name,
                    knowledge=summarize_knowledge(values, time_zone=window.time_zone, partial=bounded).counts,
                )
                for key, values in by_project.items()
            ]
            top.sort(
                key=lambda item: (
                    -(
                        sum(
                            value.value or 0
                            for value in (
                                item.knowledge.created,
                                item.knowledge.updated,
                                item.knowledge.consulted,
                            )
                        )
                    ),
                    item.name.casefold(),
                    item.project_id,
                )
            )
            mcp = await self.events.aggregate(
                tenant_id,
                None if administrative else subject,
                window,
                authority.workspace_ids if not authority.asset_limited else (),
            )
            observed_since = await self.events.coverage_started_at()
            mcp = type(mcp).model_validate(
                {
                    name: (
                        unavailable("asset_scoped_mcp_not_attributed")
                        if authority.asset_limited
                        else unavailable("mcp_not_recorded")
                        if observed_since is None
                        else value.model_copy(
                            update={"status": "partial", "reason": "best_effort_observations"}
                        )
                        if value.value is not None
                        else value
                    )
                    for name, value in ((name, getattr(mcp, name)) for name in type(mcp).model_fields)
                }
            )
            reasons = ["knowledge_consultations_require_source_receipts", "mcp_observations_are_best_effort"]
            if bounded:
                reasons.append("bounded_history")
            if authority.asset_limited:
                reasons.append("asset_scoped_mcp_observations_excluded")
            daily = []
            zone = ZoneInfo(window.time_zone)
            day = window.start_at.astimezone(zone).date()
            last = (window.end_at - timedelta(microseconds=1)).astimezone(zone).date()
            empty = summarize_knowledge([], time_zone=window.time_zone, partial=bounded).counts
            while day <= last:
                daily.append(
                    DailyActivity(
                        local_date=day.isoformat(),
                        knowledge=counts.daily.get(day.isoformat(), empty),
                        mcp_tool_calls=unavailable("not_grouped_by_local_day"),
                    )
                )
                day += timedelta(days=1)
            result = ActivitySummary(
                tenant_id=tenant_id,
                audience="organization_administrators" if administrative else "personal",
                window=window,
                coverage=ActivityCoverage(
                    observed_since=observed_since,
                    complete_window=False,
                    missing_observations=None,
                    reasons=reasons,
                ),
                knowledge=counts.counts,
                top_projects=top[:10],
                daily_activity=daily,
                mcp=mcp,
                models=ModelActivityCounts(
                    input_tokens=unavailable("provider_usage_not_recorded"),
                    output_tokens=unavailable("provider_usage_not_recorded"),
                    embedding_tokens=unavailable("provider_usage_not_recorded"),
                    cost=ObservedCost(status="unavailable", reason="provider_cost_not_recorded"),
                ),
            )
            fingerprint = authority.fingerprint
            digest = sha256(json.dumps(stamps, sort_keys=True).encode()).digest()
        async with self._snapshot():
            fresh = await self.access.resolve(subject, tenant_id, administrative=administrative)
            current = {}
            for asset_id in stamps:
                admitted = await self._visible(subject, tenant_id, asset_id)
                if admitted is not None:
                    current[asset_id] = admitted[1]
            if (
                fresh.fingerprint != fingerprint
                or sha256(json.dumps(current, sort_keys=True).encode()).digest() != digest
            ):
                raise AccessDenied(
                    "Activity access changed; request a fresh summary", code="ACTIVITY_AUTHORITY_CHANGED"
                )
        return result
