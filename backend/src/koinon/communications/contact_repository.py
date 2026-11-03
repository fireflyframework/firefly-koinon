# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from pyfly.container import repository
from pyfly.data.relational.sqlalchemy import Repository
from sqlalchemy import select

from koinon.communications.contact_entities import OperatorContactRecord


@repository(name="communications.operator_contacts")
class OperatorContactRepository(Repository[OperatorContactRecord, str]):
    async def bound_candidates(self, tenant_id: str, subject: str) -> list[OperatorContactRecord]:
        return list(
            await self._require_session().scalars(
                select(OperatorContactRecord)
                .where(
                    OperatorContactRecord.tenant_id == tenant_id,
                    OperatorContactRecord.canonical_subject == subject,
                )
                .order_by(OperatorContactRecord.id)
                .limit(2)
            )
        )
