# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Fixed primary policy snapshots and a fresh release check protect passive observations."""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import TypeVar

from pyfly.container import service
from pyfly.data.transaction import Isolation, Propagation, TransactionTemplate
from pyfly.kernel import ServiceUnavailableException

from koinon.catalog.errors import AccessDenied
from koinon.platform.authority import PlatformAccess
from koinon.platform.diagnostics import PlatformDiagnostics
from koinon.platform.dtos import PlatformHealth, SystemInformation
from koinon.platform.information import PlatformInformation
from koinon.platform.ports import PlatformReader
from koinon.security.authority import PRIMARY_POLICY_UNIT

T = TypeVar("T")


@service(name="platform.reader")
class PlatformService(PlatformReader):
    def __init__(
        self, access: PlatformAccess, diagnostics: PlatformDiagnostics, information: PlatformInformation
    ):
        self.access, self.diagnostics, self.information = access, diagnostics, information

    @staticmethod
    def _snapshot():
        return TransactionTemplate(
            "primary",
            name=PRIMARY_POLICY_UNIT,
            propagation=Propagation.REQUIRES_NEW,
            isolation=Isolation.SERIALIZABLE,
            read_only=True,
            read_from_primary=True,
        ).transaction()

    async def _read(self, subject: str, tenant_id: str, operation: Callable[[], Awaitable[T]]) -> T:
        try:
            async with asyncio.timeout(6):
                async with self._snapshot():
                    before = await self.access.resolve(subject, tenant_id)
                    result = await operation()
                async with self._snapshot():
                    after = await self.access.resolve(subject, tenant_id)
                if before != after:
                    raise AccessDenied(
                        "Administrator access changed; reload the selected context",
                        code="PLATFORM_AUTHORITY_CHANGED",
                    )
                return result
        except AccessDenied:
            raise
        except Exception:
            raise ServiceUnavailableException(
                "Platform observations are unavailable; try again", code="PLATFORM_OBSERVATION_UNAVAILABLE"
            ) from None

    async def health(self, subject: str, tenant_id: str) -> PlatformHealth:
        async def observe():
            values = await self.diagnostics.observe(subject, tenant_id)
            return PlatformHealth(tenant_id=tenant_id, checked_at=datetime.now(UTC), components=values)

        return await self._read(subject, tenant_id, observe)

    async def system_information(self, subject: str, tenant_id: str) -> SystemInformation:
        async def observe():
            return self.information.read(tenant_id)

        return await self._read(subject, tenant_id, observe)
