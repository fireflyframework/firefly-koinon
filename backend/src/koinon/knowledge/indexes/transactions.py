# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Provider entry points cannot inherit a caller's database transaction."""

from pyfly.data.transaction import current_unit_of_work


def require_detached_provider_work() -> None:
    if any(current_unit_of_work(name) is not None for name in ("primary", "canon", "structured")):
        raise RuntimeError("Index provider work must start outside database transactions")
