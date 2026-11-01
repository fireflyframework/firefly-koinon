# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Apply one typed installation profile before native component binding."""

from copy import deepcopy
from dataclasses import asdict

from koinon_storage.profile import LibraryIngestionProfile
from pyfly.core import Config


def resolve_ingestion_profile(values):
    result = deepcopy(values)
    profile = LibraryIngestionProfile.from_config(Config(values))
    knowledge = result.setdefault("koinon", {}).setdefault("knowledge", {})
    knowledge["ingestion"] = asdict(profile)
    bulk = knowledge.setdefault("bulk", {})
    for key, limit in (
        ("max_file_bytes", profile.raw_max_bytes),
        ("max_batch_bytes", profile.batch_max_bytes),
        ("max_staged_bytes_per_tenant", profile.lifetime_admission_bytes),
    ):
        selected = Config(values).get("koinon.knowledge.bulk." + key, limit)
        if isinstance(selected, str) and selected.isascii() and selected.isdecimal():
            selected = int(selected)
        if type(selected) is not int or not 1 <= selected <= limit:
            raise ValueError("Bulk admission exceeds the installation Library profile")
        bulk[key] = selected
    return result
