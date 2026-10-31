# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import subprocess

import pytest

from koinon.knowledge.bulk.worker import stop_owned_child


class Child:
    pid = 19283

    def __init__(self, exited=False):
        self.exited = exited
        self.waits = []

    def poll(self):
        return 0 if self.exited else None

    def wait(self, timeout):
        self.waits.append(timeout)
        if len(self.waits) == 1 and not self.exited:
            raise subprocess.TimeoutExpired("owned", timeout)
        self.exited = True
        return 0


def test_only_retained_unreaped_child_group_is_terminated_then_killed_and_reaped():
    child = Child()
    signals = []
    stop_owned_child(child, signal_group=lambda pid, sig: signals.append((pid, sig)))
    assert [pid for pid, _ in signals] == [child.pid, child.pid]
    assert child.exited and child.waits == [15, 5]


def test_already_reaped_child_is_never_signalled():
    child = Child(exited=True)
    stop_owned_child(child, signal_group=lambda *_: pytest.fail("Must not signal exited PID"))
    assert child.waits == [1]


def test_claimed_child_has_kernel_deadline_even_if_parent_worker_exits(monkeypatch):
    import signal

    from koinon.knowledge.bulk.worker import arm_child_deadline

    events = []
    monkeypatch.setattr(signal, "signal", lambda *args: events.append(("handler", args)))
    monkeypatch.setattr(signal, "setitimer", lambda *args: events.append(("timer", args)))
    arm_child_deadline(120)
    assert events == [("handler", (signal.SIGALRM, signal.SIG_DFL)), ("timer", (signal.ITIMER_REAL, 120))]
    for invalid in [0, 241, True, "120"]:
        with pytest.raises(ValueError):
            arm_child_deadline(invalid)


async def test_failed_child_start_is_a_known_file_failure_without_retry_or_receipt_success(monkeypatch):
    from datetime import timedelta
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from koinon.knowledge.bulk.entities import now
    from koinon.knowledge.bulk.settings import BulkSettings
    from koinon.knowledge.bulk.worker import BulkWorker

    queue = SimpleNamespace(check=AsyncMock(), failed=AsyncMock())

    def unavailable(*args, **kwargs):
        raise OSError("private process detail")

    monkeypatch.setattr(subprocess, "Popen", unavailable)
    lease = SimpleNamespace(
        item_id="item", worker_id="worker", attempt=1, expires_at=now() + timedelta(seconds=300)
    )
    await BulkWorker(queue, BulkSettings()).supervise(lease)
    queue.failed.assert_awaited_once_with(lease, code="BULK_CHILD_START_FAILED", unknown=False)


async def test_owned_child_polling_has_no_concurrent_background_reaper(monkeypatch):
    from unittest.mock import AsyncMock

    from koinon.knowledge.bulk.worker import wait_owned_child

    class PollOnlyChild:
        def __init__(self):
            self.results = iter([None, None, 0])

        def poll(self):
            return next(self.results)

        def wait(self, *args, **kwargs):
            pytest.fail("A background wait could reap and permit PID reuse before group cleanup")

    pause = AsyncMock()
    monkeypatch.setattr("koinon.knowledge.bulk.worker.asyncio.sleep", pause)
    assert await wait_owned_child(PollOnlyChild()) == 0
    assert pause.await_count == 2


def test_child_deadline_uses_remaining_lease_and_preserves_cleanup_reserve(monkeypatch):
    from datetime import UTC, datetime, timedelta
    from types import SimpleNamespace

    from koinon.knowledge.bulk.settings import BulkSettings
    from koinon.knowledge.bulk.worker import child_deadline_seconds

    clock = datetime(2026, 10, 30, tzinfo=UTC)
    monkeypatch.setattr("koinon.knowledge.bulk.worker.now", lambda: clock)
    settings = BulkSettings()
    assert child_deadline_seconds(SimpleNamespace(expires_at=clock + timedelta(seconds=300)), settings) == 240
    assert child_deadline_seconds(SimpleNamespace(expires_at=clock + timedelta(seconds=100)), settings) == 40
    assert child_deadline_seconds(SimpleNamespace(expires_at=clock + timedelta(seconds=60)), settings) == 0
    assert child_deadline_seconds(SimpleNamespace(expires_at=None), settings) == 0


async def test_parent_dispatches_only_remaining_lease_window_to_exact_child(monkeypatch):
    from datetime import UTC, datetime, timedelta
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from koinon.knowledge.bulk.settings import BulkSettings
    from koinon.knowledge.bulk.worker import BulkWorker

    clock = datetime(2026, 10, 30, tzinfo=UTC)
    monkeypatch.setattr("koinon.knowledge.bulk.worker.now", lambda: clock)
    queue = SimpleNamespace(check=AsyncMock(), failed=AsyncMock())
    calls = []

    def child(command, **options):
        calls.append((command, options))
        return SimpleNamespace(poll=lambda: 0)

    monkeypatch.setattr(subprocess, "Popen", child)
    lease = SimpleNamespace(
        item_id="item", worker_id="worker", attempt=1, expires_at=clock + timedelta(seconds=100)
    )
    await BulkWorker(queue, BulkSettings()).supervise(lease)
    command, options = calls[0]
    assert command[1:3] == ["-I", "-B"] and command[command.index("--deadline-seconds") + 1] == "40"
    assert command[command.index("--lease-expires-at") + 1] == lease.expires_at.isoformat()
    assert options["start_new_session"] is True
    queue.failed.assert_awaited_once_with(lease, code="BULK_CHILD_OUTCOME_UNCONFIRMED", unknown=True)
