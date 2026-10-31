# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from abc import ABC, abstractmethod

from koinon.evidence.dtos import SourceReference


class ExternalReadReceiptPort(ABC):
    @abstractmethod
    async def resolve(
        self, subject: str, tenant_id: str, receipt_ids: tuple[str, ...]
    ) -> tuple[tuple[SourceReference, ...], tuple[str, ...]]: ...
