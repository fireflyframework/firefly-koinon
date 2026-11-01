# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Fail-closed deadlines for an owned bounded parser child, never a shared process."""

import ctypes
import os
import signal
import sys


def arm_parent_bound_deadline(seconds: int, parent_pid: int) -> None:
    if type(seconds) is not int or not 1 <= seconds <= 120 or type(parent_pid) is not int or parent_pid < 1:
        raise ValueError("Bounded child requires its original parent and a supported deadline")
    signal.signal(signal.SIGALRM, signal.SIG_DFL)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    if sys.platform.startswith("linux"):
        libc = ctypes.CDLL(None, use_errno=True)
        # Linux clears PDEATHSIG across fork; arm it in the actual parser after exec.
        if libc.prctl(1, signal.SIGKILL, 0, 0, 0) != 0:
            raise OSError("The bounded parser cannot install its parent-death guard")
    if os.getppid() != parent_pid:
        os.kill(os.getpid(), signal.SIGKILL)
        raise RuntimeError("The bounded parser lost its original parent")
