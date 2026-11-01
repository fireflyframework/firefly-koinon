# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import subprocess

import pytest

from koinon.workers.admission import WorkAdmission, WorkAdmissionSettings


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
    await BulkWorker(queue, BulkSettings(), WorkAdmission(WorkAdmissionSettings())).supervise(lease)
    queue.failed.assert_awaited_once_with(lease, code="BULK_CHILD_START_FAILED", unknown=False)


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
        return SimpleNamespace(pid=1, poll=lambda: 0)

    monkeypatch.setattr(subprocess, "Popen", child)
    monkeypatch.setattr("koinon.knowledge.bulk.worker.wait_owned_child", AsyncMock(return_value=0))
    monkeypatch.setattr("koinon.knowledge.bulk.worker.stop_owned_child", lambda _: None)
    lease = SimpleNamespace(
        item_id="item", worker_id="worker", attempt=1, expires_at=clock + timedelta(seconds=100)
    )
    await BulkWorker(queue, BulkSettings(), WorkAdmission(WorkAdmissionSettings())).supervise(lease)
    command, options = calls[0]
    assert command[1:3] == ["-I", "-B"] and command[command.index("--deadline-seconds") + 1] == "40"
    assert command[command.index("--lease-expires-at") + 1] == lease.expires_at.isoformat()
    assert options["start_new_session"] is True
    queue.failed.assert_awaited_once_with(lease, code="BULK_CHILD_OUTCOME_UNCONFIRMED", unknown=True)
