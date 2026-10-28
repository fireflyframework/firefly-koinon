# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from dataclasses import dataclass

from pyfly.container import component
from pyfly.core import config_properties


@component(name="tokens.settings")
@config_properties(prefix="koinon.tokens")
@dataclass
class TokenSettings:
    max_lifetime_days: int = 365
    max_active_per_user: int = 100
    max_active_applications_per_user: int = 100

    def __post_init__(self):
        if (
            type(self.max_active_applications_per_user) is not int
            or not 1 <= self.max_active_applications_per_user <= 1000
        ):
            raise ValueError("Application connection quota must be from 1 to 1000")
