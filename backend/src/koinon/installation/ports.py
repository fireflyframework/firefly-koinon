# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Only native operator orchestration uses this mutation boundary."""

from typing import Protocol

from pydantic import SecretStr

from koinon.installation.authority import InstallationPermit
from koinon.installation.dtos import AgentInstallation, ConnectionInstallation, ProviderInstallation


class OperatorWritePorts(Protocol):
    async def provider(
        self, permit: InstallationPermit, value: ProviderInstallation, secret: SecretStr | None
    ) -> dict: ...
    async def connection(self, permit: InstallationPermit, value: ConnectionInstallation) -> dict: ...
    async def agent(self, permit: InstallationPermit, value: AgentInstallation) -> dict: ...
