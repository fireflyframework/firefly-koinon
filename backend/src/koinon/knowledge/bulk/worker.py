# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Existing durable jobs with one owned process per file; timeout never means replay permission."""

import argparse
import asyncio
import os
import signal
import subprocess
import sys
from collections.abc import Callable
from contextlib import suppress
from datetime import datetime, timedelta
from typing import Protocol
from uuid import uuid4

from pyfly.container import service
from pyfly.kernel import ConflictException
from pyfly.scheduling import scheduled

from koinon.knowledge.bulk.entities import now
from koinon.knowledge.bulk.queue import BulkLease, BulkQueue
from koinon.knowledge.bulk.settings import BulkSettings


def arm_child_deadline(seconds: int) -> None:
    if os.name != "posix" or type(seconds) is not int or not 1 <= seconds <= 240:
        raise ValueError("Claimed bulk children require a POSIX kernel deadline from 1 to 240 seconds")
    # A kernel default action also stops blocked native parsing after the parent exits.
    signal.signal(signal.SIGALRM, signal.SIG_DFL)
    signal.setitimer(signal.ITIMER_REAL, seconds)


class ProcessLease(Protocol):
    @property
    def item_id(self) -> str: ...
    @property
    def worker_id(self) -> str: ...
    @property
    def attempt(self) -> int: ...
    @property
    def expires_at(self) -> datetime | None: ...


class ProcessQueue[Lease: ProcessLease](Protocol):
    async def claim(self, worker_id: str) -> Lease | None: ...
    async def check(self, lease: Lease) -> None: ...
    async def failed(self, lease: Lease, *, code: str, unknown: bool) -> None: ...


def child_deadline_seconds(lease: ProcessLease, settings: BulkSettings) -> int:
    if lease.expires_at is None or lease.expires_at.tzinfo is None:
        return 0
    remaining = int((lease.expires_at - now()).total_seconds()) - 60
    return max(0, min(settings.processing_timeout_seconds, remaining))


def stop_owned_child(process, *, signal_group=os.killpg) -> None:
    if process.poll() is not None:
        process.wait(timeout=1)
        return
    if os.name == "posix":
        with suppress(ProcessLookupError):
            signal_group(process.pid, signal.SIGTERM)
    else:
        process.terminate()
    try:
        process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        if process.poll() is None:
            if os.name == "posix":
                with suppress(ProcessLookupError):
                    signal_group(process.pid, signal.SIGKILL)
            else:
                process.kill()
        process.wait(timeout=5)


async def wait_owned_child(process) -> int:
    while True:
        result = process.poll()
        if result is not None:
            return result
        await asyncio.sleep(0.1)


class ProcessSupervisor[Lease: ProcessLease]:
    def __init__(
        self,
        queue: ProcessQueue[Lease],
        settings: BulkSettings,
        *,
        module: str,
        prefix: str,
        enabled: Callable[[], bool],
    ):
        self.queue, self.settings = queue, settings
        self.module, self.enabled = module, enabled
        self.worker_id = prefix + uuid4().hex
        self._busy = asyncio.Lock()

    @scheduled(fixed_delay=timedelta(seconds=1))
    async def tick(self) -> None:
        if not self.enabled() or self._busy.locked():
            return
        async with self._busy:
            lease = await self.queue.claim(self.worker_id)
            if lease is not None:
                await self.supervise(lease)

    async def supervise(self, lease: Lease) -> None:
        self.settings.validate()
        await self.queue.check(lease)
        deadline = child_deadline_seconds(lease, self.settings)
        expiry = lease.expires_at
        if deadline <= 0 or expiry is None:
            await self._unknown(lease, "BULK_LEASE_WINDOW_EXHAUSTED")
            return
        command = [
            sys.executable,
            "-I",
            "-B",
            "-m",
            self.module,
            "--claimed-item",
            lease.item_id,
            "--worker",
            lease.worker_id,
            "--attempt",
            str(lease.attempt),
            "--deadline-seconds",
            str(deadline),
            "--lease-expires-at",
            expiry.isoformat(),
        ]
        try:
            process = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except OSError:
            await self._unknown(lease, "BULK_CHILD_START_FAILED", unknown=False)
            return
        try:
            async with asyncio.timeout(child_deadline_seconds(lease, self.settings)):
                await wait_owned_child(process)
        except BaseException as error:
            cleanup = asyncio.create_task(asyncio.to_thread(stop_owned_child, process))
            while not cleanup.done():
                try:
                    await asyncio.shield(cleanup)
                except asyncio.CancelledError:
                    continue
            cleanup.result()
            await self._unknown(lease, "BULK_WORKER_STOPPED")
            if isinstance(error, TimeoutError):
                return
            raise
        await self._unknown(lease, "BULK_CHILD_OUTCOME_UNCONFIRMED")

    async def _unknown(self, lease: Lease, code: str, *, unknown: bool = True) -> None:
        try:
            await self.queue.failed(lease, code=code, unknown=unknown)
        except ConflictException as error:
            if error.code != "BULK_LEASE_LOST":
                raise


@service(name="knowledge.bulk.worker")
class BulkWorker(ProcessSupervisor[BulkLease]):
    def __init__(self, queue: BulkQueue, settings: BulkSettings):
        super().__init__(
            queue,
            settings,
            module="koinon.knowledge.bulk.worker",
            prefix="bulk-",
            enabled=lambda: settings.worker_enabled,
        )


async def run_worker(
    item_id: str | None = None,
    worker_id: str | None = None,
    attempt: int | None = None,
    deadline_seconds: int | None = None,
    lease_expires_at: str | None = None,
) -> None:
    expiry: datetime | None = None
    if item_id is not None:
        if (
            worker_id is None
            or attempt is None
            or attempt < 1
            or deadline_seconds is None
            or lease_expires_at is None
        ):
            raise ValueError("Exact claimed worker, generation and deadline required")
        expiry = datetime.fromisoformat(lease_expires_at)
        if expiry.tzinfo is None:
            raise ValueError("Exact timezone-aware lease deadline required")
        remaining = int((expiry - now()).total_seconds()) - 60
        arm_child_deadline(min(deadline_seconds, remaining))
    elif (
        worker_id is not None
        or attempt is not None
        or deadline_seconds is not None
        or lease_expires_at is not None
    ):
        raise ValueError("Child selectors require an exact claimed item")
    from koinon.app import create_application
    from koinon.knowledge.bulk.execution import BulkExecutor
    from koinon.operations.configuration import environment_configuration

    values = environment_configuration()
    values.setdefault("pyfly", {}).setdefault("scheduling", {})["enabled"] = False
    app = create_application(values)
    context = app.state.context
    await context.start()
    try:
        queue = context.get_bean(BulkQueue)
        if item_id is not None:
            if worker_id is None or attempt is None or attempt < 1:
                raise ValueError("Exact claimed worker attempt required")
            lease = await queue.load_claimed(item_id, worker_id, attempt)
            if expiry is None or lease.expires_at != expiry:
                raise ValueError("Claimed child deadline differs from its durable lease")
            await context.get_bean(BulkExecutor).execute(lease)
        else:
            from koinon.knowledge.bulk.worker import BulkWorker as ManagedBulkWorker

            worker = context.get_bean(ManagedBulkWorker)
            worker.settings.worker_enabled = True
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
