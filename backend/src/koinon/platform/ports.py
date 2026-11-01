# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""One authenticated reader serves API, browser projection and MCP."""

from abc import ABC, abstractmethod

from koinon.platform.dtos import PlatformHealth, SystemInformation


class PlatformReader(ABC):
    @abstractmethod
    async def health(self, subject: str, tenant_id: str) -> PlatformHealth: ...

    @abstractmethod
    async def system_information(self, subject: str, tenant_id: str) -> SystemInformation: ...
