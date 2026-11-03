# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import asyncio
import os
import subprocess
import sys
import time
from types import SimpleNamespace
from unittest.mock import Mock

import psutil
import pytest

from koinon.knowledge.bulk.worker import record_owned_session, stop_owned_child, wait_owned_child
from koinon.workers.admission import WorkAdmission, WorkAdmissionSettings

pytestmark = pytest.mark.skipif(
    not hasattr(os, "WNOWAIT"), reason="requires POSIX unreaped-child observation"
)


def live(process):
    try:
        return process.is_running() and process.status() != psutil.STATUS_ZOMBIE
    except psutil.NoSuchProcess:
        return False


@pytest.mark.parametrize("leader_exits", [False, True])
async def test_shared_permit_is_held_until_term_resistant_same_group_descendant_dies(
    tmp_path, monkeypatch, leader_exits
):
    monkeypatch.setattr("koinon.knowledge.bulk.worker._CHILD_TERM_GRACE_SECONDS", 0.1, raising=False)
    pidfile = tmp_path / "owned-child.pid"
    child_code = (
        "import os,signal,time;from pathlib import Path;"
        "signal.signal(signal.SIGTERM,signal.SIG_IGN);"
        f"Path({str(pidfile)!r}).write_text(str(os.getpid()));time.sleep(60)"
    )
    leader_code = (
        "import subprocess,sys,time;"
        f"subprocess.Popen([sys.executable,'-I','-c',{child_code!r}]);"
        f"time.sleep({0.2 if leader_exits else 60})"
    )
    leader = subprocess.Popen([sys.executable, "-I", "-c", leader_code], start_new_session=True)
    record_owned_session(leader)
    descendant = None
    try:
        deadline = time.monotonic() + 5
        while not pidfile.exists():
            assert time.monotonic() < deadline
            await asyncio.sleep(0.01)
        descendant = psutil.Process(int(pidfile.read_text()))
        if leader_exits:
            await asyncio.sleep(0.3)
        admission = WorkAdmission(WorkAdmissionSettings(worker_capacity=1))
        async with admission.hold("bulk"):
            cleanup = asyncio.create_task(asyncio.to_thread(stop_owned_child, leader))
            await asyncio.sleep(0.03)
            assert admission.worker_active == 1
            await cleanup
            assert not live(descendant)
        assert admission.worker_active == 0 and leader.returncode is not None
    finally:
        if descendant is not None and live(descendant):
            descendant.kill()
        if leader.poll() is None:
            leader.kill()
        leader.wait(timeout=5)


async def test_exit_observation_keeps_leader_unreaped_until_group_cleanup():
    leader = subprocess.Popen([sys.executable, "-I", "-c", "pass"], start_new_session=True)
    record_owned_session(leader)
    try:
        assert await wait_owned_child(leader) == 0
        assert leader.returncode is None
        assert os.waitid(os.P_PID, leader.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT) is not None
        stop_owned_child(leader)
        assert leader.returncode == 0
    finally:
        if leader.poll() is None:
            leader.kill()
        leader.wait(timeout=5)


def test_already_reaped_pid_cannot_authorize_group_signals():
    leader = subprocess.Popen([sys.executable, "-I", "-c", "pass"], start_new_session=True)
    leader.wait(timeout=5)
    with pytest.raises(RuntimeError, match="ownership"):
        stop_owned_child(
            leader, signal_group=lambda *_: pytest.fail("Reaped PID cannot prove group ownership")
        )


@pytest.mark.parametrize("lookup", ["getpgid", "getsid"])
@pytest.mark.parametrize("exited", [False, True])
def test_child_exit_between_observation_and_identity_lookup_retains_unreaped_ownership(
    monkeypatch, lookup, exited
):
    from koinon.knowledge.bulk import worker

    process = record_owned_session(SimpleNamespace(pid=12345, returncode=None))
    status = SimpleNamespace(si_status=0) if exited else None
    observed = Mock(side_effect=[None, status])
    native = SimpleNamespace(
        name="posix",
        P_PID=os.P_PID,
        WEXITED=os.WEXITED,
        WNOHANG=os.WNOHANG,
        WNOWAIT=os.WNOWAIT,
        waitid=observed,
        getpgid=Mock(return_value=process.pid),
        getsid=Mock(return_value=process.pid),
    )
    getattr(native, lookup).side_effect = ProcessLookupError
    monkeypatch.setattr(worker, "os", native)
    assert worker._owned_child_exit(process) is status
    assert observed.call_count == 2
    assert all(call.args[-1] & os.WNOWAIT for call in observed.call_args_list)


@pytest.mark.parametrize("spawn_owned", [False, True])
def test_identity_lookup_race_never_signals_without_current_unreaped_spawn_ownership(
    monkeypatch, spawn_owned
):
    from koinon.knowledge.bulk import worker

    process = SimpleNamespace(pid=12345, returncode=None)
    if spawn_owned:
        record_owned_session(process)
    monkeypatch.setattr(
        worker,
        "os",
        SimpleNamespace(
            name="posix",
            P_PID=os.P_PID,
            WEXITED=os.WEXITED,
            WNOHANG=os.WNOHANG,
            WNOWAIT=os.WNOWAIT,
            waitid=Mock(side_effect=[None, ChildProcessError() if spawn_owned else None]),
            getpgid=Mock(side_effect=ProcessLookupError),
        ),
    )
    with pytest.raises(RuntimeError, match="ownership"):
        stop_owned_child(process, signal_group=lambda *_: pytest.fail("Unproven ownership cannot signal"))
