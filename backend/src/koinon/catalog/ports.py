# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol, runtime_checkable

from koinon.catalog.entities import Membership


@dataclass(frozen=True, slots=True)
class ManagedMembership:
    id: str
    subject: str
    tenant_id: str
    workspace_id: str | None
    role: str
    active: bool
    created_at: datetime
    source_id: str
    source_name: str
    expires_at: datetime
    managed: bool = True
    origin: str = "corporate"


MembershipRecord = Membership | ManagedMembership


@runtime_checkable
class ManagedMembershipReader(Protocol):
    async def load_managed_memberships(self, subject: str) -> list[ManagedMembership]: ...

    async def effective_membership_page(self, tenant_id: str, **filters) -> dict: ...

    def effective_membership_rows(self) -> Any: ...


@runtime_checkable
class MembershipEventRecorder(Protocol):
    async def membership_changed(
        self, actor: str, member: Membership, before: tuple[bool, str] | None
    ) -> None: ...
