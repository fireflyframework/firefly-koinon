# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Primary SQL observations; aggregate reads never materialize event histories."""

from datetime import UTC, datetime

from pyfly.container import repository
from pyfly.data.relational.sqlalchemy import Repository, transactional
from pyfly.data.transaction import Isolation, Propagation
from pyfly.kernel import ConflictException
from sqlalchemy import and_, case, func, select
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from koinon.activity.dtos import ActivityWindow, McpActivityCounts, ObservedCount
from koinon.activity.entities import ActivityCoverageState, ActivityEvent
from koinon.activity.observations import McpObservation


@repository(name="activity.events")
class ActivityEventRepository(Repository[ActivityEvent, str]):
    async def append(self, observation: McpObservation) -> None:
        session = self._require_session()
        insert = sqlite_insert if session.get_bind().dialect.name == "sqlite" else postgres_insert
        await session.execute(
            insert(ActivityCoverageState).values(id="installation").on_conflict_do_nothing()
        )
        values = observation.model_dump(exclude={"observation_id"}) | {"id": str(observation.observation_id)}
        result = await session.execute(
            insert(ActivityEvent)
            .values(**values)
            .on_conflict_do_nothing(index_elements=["id"])
            .returning(ActivityEvent.id)
        )
        if result.scalar_one_or_none() is not None:
            return
        existing = await session.scalar(select(ActivityEvent).where(ActivityEvent.id == values["id"]))
        if existing is None or any(getattr(existing, key) != value for key, value in values.items()):
            raise ConflictException(
                "Observation UUID differs from its recorded facts", code="ACTIVITY_ID_CONFLICT"
            )

    @transactional(
        datasource="primary", propagation=Propagation.REQUIRED, read_only=True, read_from_primary=True
    )
    async def database_now(self) -> datetime:
        value = await self._require_session().scalar(select(func.current_timestamp()))
        if isinstance(value, str):
            value = datetime.fromisoformat(value)
        if not isinstance(value, datetime):
            raise RuntimeError("Activity database clock is unavailable")
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value

    @transactional(
        datasource="primary", propagation=Propagation.REQUIRED, read_only=True, read_from_primary=True
    )
    async def coverage_started_at(self) -> datetime | None:
        return await self._require_session().scalar(select(ActivityCoverageState.coverage_started_at))

    @transactional(
        datasource="primary",
        propagation=Propagation.REQUIRED,
        isolation=Isolation.SERIALIZABLE,
        read_only=True,
        read_from_primary=True,
    )
    async def aggregate(
        self,
        tenant_id: str,
        subject: str | None,
        window: ActivityWindow,
        workspace_ids: tuple[str, ...] | None,
    ) -> McpActivityCounts:
        session = self._require_session()
        scope = [
            ActivityEvent.tenant_id == tenant_id,
            ActivityEvent.created_at >= window.start_at,
            ActivityEvent.created_at < window.end_at,
        ]
        if subject is not None:
            scope.append(ActivityEvent.subject == subject)
        if workspace_ids is not None:
            scope.append(ActivityEvent.workspace_id.in_(workspace_ids))
        counts = {
            "requests": (ActivityEvent.kind == "request",),
            "tool_calls": (ActivityEvent.kind == "tool",),
            **{
                name: (ActivityEvent.kind == "tool", ActivityEvent.outcome == name)
                for name in ("succeeded", "failed", "rejected")
            },
            "tool_cancelled": (ActivityEvent.kind == "tool", ActivityEvent.outcome == "cancelled"),
            **{
                "request_" + name: (ActivityEvent.kind == "request", ActivityEvent.outcome == name)
                for name in ("succeeded", "failed", "rejected", "cancelled")
            },
        }
        row = (
            await session.execute(
                select(
                    *(
                        func.coalesce(func.sum(case((and_(*conditions), 1), else_=0)), 0).label(name)
                        for name, conditions in counts.items()
                    ),
                    func.avg(case((ActivityEvent.kind == "tool", ActivityEvent.duration_ms))).label(
                        "average"
                    ),
                ).where(*scope)
            )
        ).one()
        partial = workspace_ids is not None
        values = {
            name: ObservedCount(
                value=int(getattr(row, name)),
                status="partial" if partial else "observed",
                reason="unknown_workspace_excluded" if partial else None,
            )
            for name in counts
        }
        total = int(row.tool_calls)
        if total:
            percentile = await session.scalar(
                select(ActivityEvent.duration_ms)
                .where(
                    *scope,
                    ActivityEvent.kind == "tool",
                )
                .order_by(ActivityEvent.duration_ms, ActivityEvent.id)
                .offset((95 * total + 99) // 100 - 1)
                .limit(1)
            )
            if percentile is None:
                raise RuntimeError("Activity percentile is unavailable")
            values["average_duration_ms"] = ObservedCount(
                value=int(float(row.average) + 0.5),
                status="partial" if partial else "observed",
                reason="unknown_workspace_excluded" if partial else None,
            )
            values["p95_duration_ms"] = ObservedCount(
                value=int(percentile),
                status="partial" if partial else "observed",
                reason="unknown_workspace_excluded" if partial else None,
            )
        else:
            for name in ("average_duration_ms", "p95_duration_ms"):
                values[name] = ObservedCount(status="unavailable", reason="no_tool_observations")
        return McpActivityCounts(**values)
