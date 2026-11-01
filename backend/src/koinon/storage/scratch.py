# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Shared per-process admission for disposable API file preparation."""

import threading

from koinon_storage.profile import LibraryIngestionProfile
from pyfly.container import component
from pyfly.core import Config
from pyfly.kernel import PayloadTooLargeException, RateLimitException


class ScratchReservation:
    def __init__(self, owner: "ScratchAdmission", size_bytes: int):
        self.owner, self.size_bytes = owner, size_bytes
        self.closed = False

    def close(self) -> None:
        with self.owner._lock:
            if not self.closed:
                self.closed = True
                self.owner._reserved -= self.size_bytes

    def __enter__(self) -> "ScratchReservation":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()


@component(name="storage.scratch_admission")
class ScratchAdmission:
    def __init__(self, config: Config):
        self.capacity_bytes = LibraryIngestionProfile.from_config(config).scratch_max_bytes
        self._reserved = 0
        self._lock = threading.Lock()

    @property
    def available_bytes(self) -> int:
        with self._lock:
            return self.capacity_bytes - self._reserved

    def reserve(self, size_bytes: int) -> ScratchReservation:
        if type(size_bytes) is not int or not 1 <= size_bytes <= self.capacity_bytes:
            raise PayloadTooLargeException(
                "File preparation exceeds the configured temporary-space budget", code="SCRATCH_FILE_LIMIT"
            )
        with self._lock:
            if size_bytes + self._reserved > self.capacity_bytes:
                raise RateLimitException("File preparation capacity is busy; try again", code="SCRATCH_BUSY")
            self._reserved += size_bytes
        return ScratchReservation(self, size_bytes)
