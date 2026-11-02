# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from pyfly.container import repository
from pyfly.data.relational.sqlalchemy import Repository
from sqlalchemy import select

from koinon.communications.entities import OutboxRecord
from koinon.communications.recovery_entities import WelcomeRecoveryRecord


@repository(name="communications.welcome_recoveries")
class WelcomeRecoveryRepository(Repository[WelcomeRecoveryRecord, str]):
    async def original_snapshot(self, identifier):
        return await self._require_session().scalar(
            select(OutboxRecord)
            .where(OutboxRecord.id == identifier)
            .execution_options(populate_existing=True)
        )
