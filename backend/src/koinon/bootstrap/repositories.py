# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime
from typing import cast

from pyfly.container import repository
from pyfly.data.relational.sqlalchemy import Repository
from sqlalchemy import func, select, update
from sqlalchemy.engine import CursorResult

from koinon.bootstrap.entities import BootstrapIdentityGrant


@repository(name="bootstrap.identity_grants")
class BootstrapGrantRepository(Repository[BootstrapIdentityGrant, str]):
    async def clock(self) -> datetime:
        value = await self._require_session().scalar(select(func.current_timestamp()))
        if isinstance(value, str):
            value = datetime.fromisoformat(value)
        if not isinstance(value, datetime):
            raise RuntimeError("Bootstrap database clock unavailable")
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value

    async def pending(
        self, issuer: str, client_id: str, tid: str, oid: str, now: datetime
    ) -> list[BootstrapIdentityGrant]:
        return list(
            await self._require_session().scalars(
                select(BootstrapIdentityGrant)
                .where(
                    BootstrapIdentityGrant.canonical_issuer == issuer,
                    BootstrapIdentityGrant.native_client_id == client_id,
                    BootstrapIdentityGrant.entra_tenant_id == tid,
                    BootstrapIdentityGrant.object_id == oid,
                    BootstrapIdentityGrant.consumed_at.is_(None),
                    BootstrapIdentityGrant.expires_at > now,
                )
                .order_by(BootstrapIdentityGrant.tenant_id, BootstrapIdentityGrant.id)
                .limit(101)
                .with_for_update()
            )
        )

    async def activate(
        self, row: BootstrapIdentityGrant, subject: str, membership_id: str, now: datetime
    ) -> None:
        result = await self._require_session().execute(
            update(BootstrapIdentityGrant)
            .where(
                BootstrapIdentityGrant.id == row.id,
                BootstrapIdentityGrant.consumed_at.is_(None),
                BootstrapIdentityGrant.expires_at > now,
            )
            .values(consumed_at=now, consumed_subject=subject, membership_id=membership_id)
        )
        if cast(CursorResult, result).rowcount != 1:
            raise RuntimeError("Bootstrap enrollment changed before activation")
