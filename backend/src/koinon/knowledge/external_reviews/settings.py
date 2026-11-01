# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from dataclasses import dataclass

from pyfly.container import component
from pyfly.core import config_properties


@component(name="knowledge.external_reviews.settings")
@config_properties(prefix="koinon.external_reviews")
@dataclass
class ExternalReviewSettings:
    max_active_files: int = 8
    max_staged_bytes: int = 512 * 1024 * 1024
    max_file_bytes: int = 128 * 1024 * 1024
    ttl_seconds: int = 900

    def validate(self):
        limits = (
            (self.max_active_files, 1, 64),
            (self.max_staged_bytes, 1, 1024 * 1024 * 1024),
            (self.max_file_bytes, 1, 128 * 1024 * 1024),
            (self.ttl_seconds, 60, 900),
        )
        if any(type(value) is not int or not low <= value <= high for value, low, high in limits):
            raise ValueError("External review settings exceed supported resource bounds")
