# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from koinon_storage import process_guard


def setup(monkeypatch, *, parent=41, result=0):
    native = Mock(return_value=result)
    monkeypatch.setattr(process_guard.sys, "platform", "linux")
    monkeypatch.setattr(process_guard.ctypes, "CDLL", lambda *args, **kwargs: SimpleNamespace(prctl=native))
    monkeypatch.setattr(process_guard.signal, "signal", Mock())
    monkeypatch.setattr(process_guard.signal, "setitimer", Mock())
    monkeypatch.setattr(process_guard.os, "getppid", lambda: parent)
    monkeypatch.setattr(process_guard.os, "getpid", lambda: 99)
    kill = Mock()
    monkeypatch.setattr(process_guard.os, "kill", kill)
    return native, kill


def test_linux_child_arms_native_parent_death_then_checks_original_parent(monkeypatch):
    native, kill = setup(monkeypatch)
    process_guard.arm_parent_bound_deadline(120, 41)
    native.assert_called_once_with(1, process_guard.signal.SIGKILL, 0, 0, 0)
    process_guard.signal.setitimer.assert_called_once_with(process_guard.signal.ITIMER_REAL, 120)
    kill.assert_not_called()


def test_parent_death_race_and_unavailable_native_guard_fail_closed(monkeypatch):
    native, kill = setup(monkeypatch, parent=1)
    with pytest.raises(RuntimeError, match="lost its original parent"):
        process_guard.arm_parent_bound_deadline(120, 41)
    kill.assert_called_once_with(99, process_guard.signal.SIGKILL)
    setup(monkeypatch, result=-1)
    with pytest.raises(OSError, match="parent-death guard"):
        process_guard.arm_parent_bound_deadline(120, 41)


@pytest.mark.parametrize("seconds,parent", [(True, 1), (0, 1), (121, 1), (120, 0), (120, True)])
def test_unbounded_or_invalid_child_settings_never_arm_process_signals(monkeypatch, seconds, parent):
    native, kill = setup(monkeypatch)
    with pytest.raises(ValueError):
        process_guard.arm_parent_bound_deadline(seconds, parent)
    native.assert_not_called()
    kill.assert_not_called()
