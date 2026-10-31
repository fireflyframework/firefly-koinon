# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from dataclasses import dataclass

from pyfly.container import component
from pyfly.core import config_properties


@component(name="knowledge.external_reviews.read_receipts.settings")
@config_properties(prefix="koinon.external_reviews.read_receipts")
@dataclass
class ExternalReadReceiptSettings:
    max_active_receipts: int = 128
    ttl_seconds: int = 300
    max_receipt_bytes: int = 262144

    def validate(self):
        for value, low, high in (
            (self.max_active_receipts, 1, 1024),
            (self.ttl_seconds, 60, 900),
            (self.max_receipt_bytes, 1024, 524288),
        ):
            if type(value) is not int or not low <= value <= high:
                raise ValueError("Read receipt settings exceed supported resource bounds")
