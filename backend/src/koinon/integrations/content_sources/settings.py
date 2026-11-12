# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import math
from dataclasses import dataclass, field

from pyfly.container import component
from pyfly.core import config_properties


@component(name="content_sources.settings")
@config_properties(prefix="koinon.content_sources")
@dataclass
class ContentSourceSettings:
    enabled: bool = False
    synchronization_enabled: bool = False
    sync_scheduler_batch_size: int = 10
    sync_min_interval_seconds: int = 900
    sync_max_interval_seconds: int = 604800
    sync_lease_seconds: int = 360
    sync_max_scan_items: int = 100000
    sync_validation_max_active_per_tenant: int = 8
    sync_validation_max_active_per_owner: int = 2
    sync_validation_max_records_per_tenant: int = 1000
    sync_validation_max_retained_bytes_per_tenant: int = 17179869184
    master_key: str = field(default="", repr=False)
    providers: dict[str, dict[str, str | bool]] = field(default_factory=dict, repr=False)
    metadata_timeout_seconds: float = 30
    connect_timeout_seconds: float = 10
    read_timeout_seconds: float = 30
    transfer_timeout_seconds: float = 900
    microsoft_download_hosts: list[str] = field(default_factory=list)

    @property
    def source_heartbeat_interval(self) -> float:
        interval = min(60, self.sync_lease_seconds / 3)
        if interval + 10 + 30 >= self.sync_lease_seconds:
            raise ValueError("Source lease cannot cover heartbeat and shutdown margins")
        return interval

    def synchronization_options(self) -> None:
        if type(self.synchronization_enabled) is not bool:
            raise ValueError("Synchronization activation must be a boolean")
        if self.synchronization_enabled and not self.enabled:
            raise ValueError("Synchronization requires enabled content-source accounts")
        for value, minimum, maximum in (
            (self.sync_scheduler_batch_size, 1, 50),
            (self.sync_min_interval_seconds, 900, 604800),
            (self.sync_max_interval_seconds, 900, 604800),
            (self.sync_lease_seconds, 300, 3600),
            (self.sync_max_scan_items, 100, 1000000),
            (self.sync_validation_max_active_per_tenant, 1, 8),
            (self.sync_validation_max_active_per_owner, 1, 2),
            (self.sync_validation_max_records_per_tenant, 1, 1000),
            (self.sync_validation_max_retained_bytes_per_tenant, 1, 17179869184),
        ):
            if type(value) is not int or not minimum <= value <= maximum:
                raise ValueError("Source synchronization exceeds installation bounds")
        if self.sync_min_interval_seconds > self.sync_max_interval_seconds:
            raise ValueError("Source interval bounds are inverted")
        _ = self.source_heartbeat_interval
        if (
            self.sync_validation_max_active_per_owner > self.sync_validation_max_active_per_tenant
            or self.sync_validation_max_records_per_tenant < self.sync_validation_max_active_per_tenant
            or self.sync_validation_max_retained_bytes_per_tenant < self.sync_max_scan_items * 16384 + 8388608
        ):
            raise ValueError("Source validation capacity cannot reserve a complete bounded scan")

    def transport_options(self) -> dict[str, float]:
        values = {
            "timeout": self.metadata_timeout_seconds,
            "connect_timeout": self.connect_timeout_seconds,
            "read_timeout": self.read_timeout_seconds,
            "transfer_timeout": self.transfer_timeout_seconds,
        }
        maxima = {"timeout": 300, "connect_timeout": 120, "read_timeout": 300, "transfer_timeout": 3600}
        if any(
            type(value) not in {int, float} or not math.isfinite(value) or not 0 < value <= maxima[key]
            for key, value in values.items()
        ):
            raise ValueError("Source transport deadlines must be positive and within installation bounds")
        return values
