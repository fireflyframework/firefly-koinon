# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Composing applications can require current authority before private callback delivery."""

from abc import ABC, abstractmethod
from typing import Any


class CallbackDeliveryAccess(ABC):
    @abstractmethod
    async def authorize(self, claim: dict[str, Any]) -> None: ...
