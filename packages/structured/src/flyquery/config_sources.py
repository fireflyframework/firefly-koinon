# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Normalize numeric environment settings without weakening typed constructor inputs."""

import re
from collections.abc import Callable
from typing import Any

INGESTION_INTEGERS = frozenset(
    {
        "ingest_duckdb_threads",
        "ingest_scratch_max_bytes",
        "ingest_decompressed_max_bytes",
        "ingest_native_connections",
    }
)


def ingestion_environment(source: Callable[[], dict[str, Any]]) -> Callable[[], dict[str, Any]]:
    def read() -> dict[str, Any]:
        values = source().copy()
        for name in INGESTION_INTEGERS:
            value = values.get(name)
            if isinstance(value, str) and re.fullmatch(r"[0-9]{1,20}", value, flags=re.ASCII):
                values[name] = int(value)
        return values

    return read
