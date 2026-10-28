# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Reconcile only sealed native commits; never initiate a knowledge write."""

import logging
from datetime import timedelta

from pyfly.container import service
from pyfly.data.relational.datasource_registry import DataSourceRegistry
from pyfly.data.transaction import infrastructure_unit
from pyfly.scheduling import scheduled
from sqlalchemy import select

from koinon.knowledge.curated.entities import KnowledgeIntentRow
from koinon.knowledge.curated.intents import KnowledgeIntents

logger = logging.getLogger(__name__)


@service(name="knowledge.curated.reconciliation")
class CuratedReconciliation:
    def __init__(self, intents: KnowledgeIntents, datasources: DataSourceRegistry):
        self.intents, self.datasources = intents, datasources
        self.cursor = None

    @scheduled(fixed_delay=timedelta(seconds=30))
    async def tick(self):
        if "canon" not in self.datasources.names():
            return
        statement = select(
            KnowledgeIntentRow.id,
            KnowledgeIntentRow.subject,
            KnowledgeIntentRow.tenant_id,
            KnowledgeIntentRow.created_at,
        ).where(KnowledgeIntentRow.status.in_(("committing", "unresolved")))
        if self.cursor is not None:
            created, identifier = self.cursor
            statement = statement.where(
                (KnowledgeIntentRow.created_at > created)
                | ((KnowledgeIntentRow.created_at == created) & (KnowledgeIntentRow.id > identifier))
            )
        async with infrastructure_unit(self.datasources.get("primary"), read_only=True) as session:
            rows = list(
                (
                    await session.execute(
                        statement.order_by(KnowledgeIntentRow.created_at, KnowledgeIntentRow.id).limit(25)
                    )
                ).all()
            )
        self.cursor = (rows[-1].created_at, rows[-1].id) if rows else None
        for row in rows:
            try:
                await self.intents.reconcile(row.subject, row.tenant_id, row.id)
            except Exception as error:
                logger.warning(
                    "Committed knowledge acknowledgement remains pending",
                    extra={"operation_id": row.id, "code": getattr(error, "code", "KNOWLEDGE_ACK_PENDING")},
                )
