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
    master_key: str = field(default="", repr=False)
    providers: dict[str, dict[str, str | bool]] = field(default_factory=dict, repr=False)
    metadata_timeout_seconds: float = 30
    connect_timeout_seconds: float = 10
    read_timeout_seconds: float = 30
    transfer_timeout_seconds: float = 900
    microsoft_download_hosts: list[str] = field(default_factory=list)

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
