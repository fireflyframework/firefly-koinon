# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from dataclasses import dataclass

from pyfly.container import component
from pyfly.core import config_properties


@component(name="evidence.settings")
@config_properties(prefix="koinon.exports")
@dataclass
class EvidenceSettings:
    review_ttl_seconds: int = 300
    max_active_reviews: int = 50
    max_snapshot_bytes: int = 5 * 1024 * 1024
    max_download_bytes: int = 100 * 1024 * 1024
    download_timeout_seconds: int = 120
    export_ttl_seconds: int = 3600
    max_concurrent_downloads: int = 2
    max_active_exports: int = 50
    max_active_shares: int = 50

    def validate(self):
        bounds = (
            (self.review_ttl_seconds, 30, 900),
            (self.max_active_reviews, 1, 200),
            (self.max_snapshot_bytes, 1024, 5 * 1024 * 1024),
            (self.max_download_bytes, 1024, 100 * 1024 * 1024),
            (self.download_timeout_seconds, 1, 300),
            (self.export_ttl_seconds, 60, 86400),
            (self.max_concurrent_downloads, 1, 4),
            (self.max_active_exports, 1, 200),
            (self.max_active_shares, 1, 200),
        )
        if any(not lower <= value <= upper for value, lower, upper in bounds):
            raise ValueError("Export and sharing limits exceed the supported bounds")
