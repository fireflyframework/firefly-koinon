# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from dataclasses import dataclass

from pyfly.container import component
from pyfly.core import config_properties


@component(name="operations.settings")
@config_properties(prefix="koinon.operations")
@dataclass
class OperationalSettings:
    worker_concurrency: int = 1
    max_queued_per_subject: int = 50
    job_lease_seconds: int = 60
    max_index_workspaces: int = 32

    def __post_init__(self):
        for name, minimum, maximum in (
            ("worker_concurrency", 1, 16),
            ("max_queued_per_subject", 1, 10000),
            ("job_lease_seconds", 5, 3600),
            ("max_index_workspaces", 1, 128),
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
                raise ValueError("koinon.operations." + name + " is outside its supported range")
