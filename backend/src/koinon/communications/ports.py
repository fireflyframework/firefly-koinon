# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import datetime
from typing import Protocol, runtime_checkable


@runtime_checkable
class AccountEventRecorder(Protocol):
    async def security_changed(
        self,
        actor: str,
        owner: str,
        tenant_id: str,
        subtype: str,
        resource_id: str,
        label: str,
        *,
        scopes: list[str] | None = None,
        expires_at: datetime | None = None,
        workspace_id: str | None = None,
    ) -> None: ...


@runtime_checkable
class CommunicationIdentityObserver(Protocol):
    async def observe_login(self, context) -> None: ...


@runtime_checkable
class WelcomeAdmissionPort(Protocol):
    async def admit(self, owner: str, tenant_id: str): ...
