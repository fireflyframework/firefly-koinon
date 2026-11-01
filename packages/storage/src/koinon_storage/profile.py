# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Shared bounded Library ingestion policy, independent of the web/runtime framework."""

import re
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class LibraryIngestionProfile:
    raw_max_bytes: int = 128 * 1024**2
    batch_max_bytes: int = 512 * 1024**2
    lifetime_admission_bytes: int = 16 * 1024**3
    expanded_max_bytes: int = 256 * 1024**2
    scratch_max_bytes: int = 1024**3
    child_rss_max_bytes: int = 768 * 1024**2
    wall_seconds: int = 120
    text_max_bytes: int = 16 * 1024**2
    chunks_max: int = 4096

    def __post_init__(self):
        bounds = (
            128 * 1024**2,
            512 * 1024**2,
            16 * 1024**3,
            256 * 1024**2,
            1024**3,
            768 * 1024**2,
            120,
            16 * 1024**2,
            4096,
        )
        if any(
            type(value) is not int or not 1 <= value <= maximum
            for value, maximum in zip(asdict(self).values(), bounds, strict=True)
        ):
            raise ValueError("Library ingestion policy exceeds its bounded file profile")

    @classmethod
    def from_config(cls, config):
        defaults = asdict(cls())
        selected = {}
        for key, default in defaults.items():
            value = (
                config.get("koinon.knowledge.ingestion." + key, default) if config is not None else default
            )
            if isinstance(value, str) and re.fullmatch(r"[0-9]{1,12}", value):
                value = int(value)
            selected[key] = value
        return cls(**selected)
