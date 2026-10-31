# Copyright 2024-2026 Firefly Software Foundation
# Modifications Copyright 2026 Firefly Software Foundation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Repository for flyquery_callback_outbox -- transactional webhook outbox.

The repo's invariants:

* ``enqueue_terminal`` and the job's status flip happen in the SAME
  AsyncSession (passed in by the IngestWorker) so the outbox row is
  durable iff the job is. No "lost" or "ghost" callbacks possible.
* ``claim_due_batch`` is the only path the CallbackWorker uses to
  pick rows: it filters on ``status='PENDING' AND next_attempt_at <= now()``,
  ``ORDER BY next_attempt_at``, ``FOR UPDATE SKIP LOCKED`` so multiple
  worker instances scale horizontally without colliding.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

import sqlalchemy as sa
from pyfly.container import repository
from pyfly.context.consumer_context import public_consumer_data
from pyfly.data.transaction import Isolation, Propagation, TransactionTemplate, infrastructure_unit
from sqlalchemy.ext.asyncio import AsyncSession

from flyquery.data import StructuredSessions, unwrap_sessions

_OUTBOX = sa.table(
    "flyquery_callback_outbox",
    *[sa.column(name, sa.Uuid) for name in ("id", "ingest_job_id", "workspace_id")],
    *[
        sa.column(name, sa.String)
        for name in ("tenant_id", "callback_url", "callback_secret", "event_type", "status", "last_error")
    ],
    sa.column("callback_headers", sa.JSON),
    sa.column("payload_json", sa.JSON),
    sa.column("attempts", sa.Integer),
    sa.column("last_status_code", sa.Integer),
    *[
        sa.column(name, sa.DateTime(timezone=True))
        for name in ("last_attempt_at", "next_attempt_at", "created_at", "finished_at")
    ],
)


@repository(name="structured.CallbackOutboxRepository")
class CallbackOutboxRepository:
    """Async CRUD over the callback outbox."""

    def __init__(self, session: StructuredSessions) -> None:
        self._factory = unwrap_sessions(session)

    async def enqueue_terminal(
        self,
        *,
        session: AsyncSession,
        ingest_job_id: uuid.UUID,
        tenant_id: str,
        workspace_id: uuid.UUID,
        callback_url: str,
        callback_secret: str | None,
        callback_headers: dict[str, str],
        event_type: str,
        payload: dict[str, Any],
    ) -> uuid.UUID:
        """Append one outbox row using the caller's session.

        The CallerWorker is responsible for ``s.begin()`` / commit;
        we share its txn so the job's status flip and the outbox
        insert are atomic.
        """
        new_id = uuid.uuid4()
        await session.execute(
            sa.text(
                """
                INSERT INTO flyquery_callback_outbox
                    (id, ingest_job_id, tenant_id, workspace_id,
                     callback_url, callback_secret, callback_headers,
                     event_type, payload_json, status, attempts, next_attempt_at)
                VALUES
                    (:id, :job_id, :tenant, :ws,
                     :url, :secret, CAST(:headers AS jsonb),
                     :event, CAST(:payload AS jsonb), 'PENDING', 0, now())
                """
            ),
            {
                "id": new_id,
                "job_id": ingest_job_id,
                "tenant": tenant_id,
                "ws": workspace_id,
                "url": callback_url,
                "secret": callback_secret,
                "headers": json.dumps(callback_headers or {}),
                "event": event_type,
                "payload": json.dumps(public_consumer_data(payload), default=_json_default),
            },
        )
        return new_id

    async def claim_due_batch(
        self,
        *,
        limit: int = 25,
        lease_seconds: float = 40,
    ) -> list[dict[str, Any]]:
        """Reserve rows durably before releasing the claim transaction.

        ``last_attempt_at`` is the monotonic reservation generation, separate
        from completed delivery attempts. ``next_attempt_at`` is the lease
        deadline until the fenced outcome schedules a retry or settles it.
        """
        if not 1 <= limit <= 100 or not 1 <= lease_seconds <= 3600:
            raise ValueError("Use a bounded callback batch and lease")
        now = datetime.now(UTC)
        table = _OUTBOX
        async with infrastructure_unit(self._factory) as session:
            rows = (
                (
                    await session.execute(
                        sa.select(table)
                        .where(table.c.status == "PENDING", table.c.next_attempt_at <= now)
                        .order_by(table.c.next_attempt_at, table.c.id)
                        .limit(limit)
                        .with_for_update(skip_locked=True)
                    )
                )
                .mappings()
                .all()
            )
            reserved = []
            for row in rows:
                previous = row["last_attempt_at"]
                if previous is not None and previous.tzinfo is None:
                    previous = previous.replace(tzinfo=UTC)
                generation = max(now, previous + timedelta(microseconds=1)) if previous else now
                statement = (
                    sa.update(table)
                    .where(
                        table.c.id == row["id"],
                        table.c.status == "PENDING",
                        table.c.next_attempt_at <= now,
                        table.c.last_attempt_at == row["last_attempt_at"],
                    )
                    .values(
                        last_attempt_at=generation,
                        next_attempt_at=now + timedelta(seconds=lease_seconds),
                        last_status_code=None,
                        last_error=None,
                    )
                )
                value = (await session.execute(statement.returning(*table.c))).mappings().one_or_none()
                if value is not None:
                    reserved.append(_row_to_dict(value))
            return reserved

    @staticmethod
    def _owned(id_: uuid.UUID, claim: dict[str, Any]):
        table = _OUTBOX
        if claim.get("id") != id_ or not isinstance(claim.get("last_attempt_at"), datetime):
            raise ValueError("The exact callback reservation is required")
        return sa.and_(
            table.c.id == id_,
            table.c.status == "PENDING",
            table.c.attempts == claim["attempts"],
            table.c.last_attempt_at == claim["last_attempt_at"],
            table.c.next_attempt_at == claim["next_attempt_at"],
            table.c.next_attempt_at > datetime.now(UTC),
        )

    async def still_owned(self, claim: dict[str, Any]) -> bool:
        async with TransactionTemplate(
            self._factory,
            propagation=Propagation.REQUIRES_NEW,
            isolation=Isolation.SERIALIZABLE,
            read_only=True,
            read_from_primary=True,
        ).transaction() as unit:
            assert unit is not None
            return (
                await unit.resource.scalar(sa.select(_OUTBOX.c.id).where(self._owned(claim["id"], claim)))
                is not None
            )

    async def mark_delivered(self, *, id_: uuid.UUID, status_code: int, claim: dict[str, Any]) -> bool:
        async with infrastructure_unit(self._factory) as session:
            value = await session.execute(
                sa.update(_OUTBOX)
                .where(self._owned(id_, claim))
                .values(
                    status="DELIVERED",
                    attempts=_OUTBOX.c.attempts + 1,
                    last_status_code=int(status_code),
                    last_error=None,
                    finished_at=datetime.now(UTC),
                )
                .returning(_OUTBOX.c.id)
            )
            return value.scalar_one_or_none() is not None

    async def mark_attempt_failure(
        self,
        *,
        id_: uuid.UUID,
        status_code: int | None,
        error: str,
        backoff_seconds: int,
        terminal: bool,
        claim: dict[str, Any],
    ) -> bool:
        """Only the current reservation may spend a retry or settle delivery."""
        now = datetime.now(UTC)
        values: dict[str, Any] = dict(
            attempts=_OUTBOX.c.attempts + 1, last_status_code=status_code, last_error=error[:1000]
        )
        values.update(status="DEAD", finished_at=now) if terminal else values.update(
            next_attempt_at=now + timedelta(seconds=max(0, int(backoff_seconds)))
        )
        async with infrastructure_unit(self._factory) as session:
            value = await session.execute(
                sa.update(_OUTBOX).where(self._owned(id_, claim)).values(**values).returning(_OUTBOX.c.id)
            )
            return value.scalar_one_or_none() is not None

    async def list_for_job(
        self,
        ingest_job_id: uuid.UUID,
        *,
        tenant_id: str,
        workspace_id: uuid.UUID,
        statuses: Sequence[str] | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        conditions = [
            "ingest_job_id = :job_id",
            "tenant_id = :tenant",
            "workspace_id = :ws",
        ]
        params: dict[str, Any] = {
            "job_id": ingest_job_id,
            "tenant": tenant_id,
            "ws": workspace_id,
        }
        if statuses:
            placeholders = ", ".join(f":st_{i}" for i in range(len(statuses)))
            conditions.append(f"status IN ({placeholders})")
            for i, st in enumerate(statuses):
                params[f"st_{i}"] = st
        where = " AND ".join(conditions)

        async with infrastructure_unit(self._factory) as s:
            total = (
                await s.execute(
                    sa.text(f"SELECT COUNT(*) FROM flyquery_callback_outbox WHERE {where}"),
                    params,
                )
            ).scalar_one()

            rows = await s.execute(
                sa.text(
                    f"""
                    SELECT id, ingest_job_id, tenant_id, workspace_id,
                           callback_url, callback_secret, callback_headers,
                           event_type, payload_json, status, attempts,
                           last_attempt_at, last_status_code, last_error,
                           next_attempt_at, created_at, finished_at
                    FROM flyquery_callback_outbox
                    WHERE {where}
                    ORDER BY created_at DESC
                    LIMIT :limit OFFSET :offset
                    """
                ),
                {**params, "limit": int(limit), "offset": int(offset)},
            )
            items = [_row_to_dict(r) for r in rows.mappings().all()]
            return items, int(total)


def _json_default(o: Any) -> Any:
    """Serialise UUID / datetime fields so json.dumps doesn't choke on the payload."""
    if isinstance(o, uuid.UUID):
        return str(o)
    if isinstance(o, datetime):
        return o.isoformat()
    raise TypeError(f"unserialisable type {type(o).__name__}")


def _row_to_dict(row: Any) -> dict[str, Any]:
    d = dict(row)
    for col in ("id", "ingest_job_id", "workspace_id"):
        v = d.get(col)
        if v is not None and not isinstance(v, uuid.UUID):
            d[col] = uuid.UUID(str(v))
    return d
