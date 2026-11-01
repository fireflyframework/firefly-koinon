# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Independent query claims use the same bounded owned-process supervisor as intake."""

import argparse
import asyncio
from contextlib import suppress
from datetime import datetime

from pyfly.container import service

from koinon.knowledge.bulk.entities import now
from koinon.knowledge.bulk.settings import BulkSettings
from koinon.knowledge.bulk.worker import ProcessSupervisor, arm_child_deadline, claimed_child_configuration
from koinon.knowledge.bulk_queries.queue import QueryBatchQueue, QueryLease
from koinon.workers.admission import WorkAdmission


@service(name="knowledge.bulk_queries.worker")
class QueryWorker(ProcessSupervisor[QueryLease]):
    def __init__(self, queue: QueryBatchQueue, settings: BulkSettings, admission: WorkAdmission):
        super().__init__(
            queue,
            settings,
            admission,
            module="koinon.knowledge.bulk_queries.worker",
            prefix="query-",
            enabled=lambda: settings.query_worker_enabled,
        )


async def run_worker(
    item_id: str | None = None,
    worker_id: str | None = None,
    attempt: int | None = None,
    deadline_seconds: int | None = None,
    lease_expires_at: str | None = None,
) -> None:
    expiry = None
    if item_id is not None:
        if (
            worker_id is None
            or attempt is None
            or attempt < 1
            or deadline_seconds is None
            or lease_expires_at is None
        ):
            raise ValueError("Exact claimed query, worker, generation and deadline required")
        expiry = datetime.fromisoformat(lease_expires_at)
        if expiry.tzinfo is None:
            raise ValueError("Timezone-aware query lease deadline required")
        remaining = int((expiry - now()).total_seconds()) - 60
        arm_child_deadline(min(deadline_seconds, remaining))
    elif any(value is not None for value in (worker_id, attempt, deadline_seconds, lease_expires_at)):
        raise ValueError("Child selectors require an exact claimed query")
    from koinon.app import create_application
    from koinon.knowledge.bulk_queries.execution import QueryBatchExecutor
    from koinon.operations.configuration import environment_configuration

    values = claimed_child_configuration(environment_configuration())
    app = create_application(values)
    context = app.state.context
    await context.start()
    try:
        queue = context.get_bean(QueryBatchQueue)
        if item_id is not None:
            if worker_id is None or attempt is None:
                raise ValueError("Exact claimed query worker required")
            lease = await queue.load_claimed(item_id, worker_id, attempt)
            if lease.expires_at != expiry:
                raise ValueError("Claimed child deadline differs from durable query lease")
            await context.get_bean(QueryBatchExecutor).execute(lease)
        else:
            from koinon.knowledge.bulk_queries.worker import QueryWorker as ManagedQueryWorker

            worker = context.get_bean(ManagedQueryWorker)
            worker.settings.query_worker_enabled = True
            while True:
                await worker.tick()
                await asyncio.sleep(0.5)
    finally:
        await context.stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--claimed-item")
    parser.add_argument("--worker")
    parser.add_argument("--attempt", type=int)
    parser.add_argument("--deadline-seconds", type=int)
    parser.add_argument("--lease-expires-at")
    args = parser.parse_args()
    with suppress(KeyboardInterrupt):
        asyncio.run(
            run_worker(
                args.claimed_item, args.worker, args.attempt, args.deadline_seconds, args.lease_expires_at
            )
        )
