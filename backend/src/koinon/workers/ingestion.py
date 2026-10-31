# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Durable pending discovery is independent of process-local EDA notifications."""

import asyncio
import logging
from datetime import UTC, datetime, timedelta

import sqlalchemy as sa
from pyfly.container import Container, service
from pyfly.context.conditions import conditional_on_property
from pyfly.data.relational.datasource_registry import DataSourceRegistry
from pyfly.data.transaction import Isolation, Propagation, TransactionTemplate
from pyfly.scheduling import scheduled

from koinon.knowledge.adapters import native_scope
from koinon.workers.admission import WorkAdmission
from koinon.workers.execution import IngestionExecutionAuthority

logger = logging.getLogger(__name__)


def pending_statement(domain, now, lease_seconds):
    if domain not in {"canon", "structured"} or not 1 <= lease_seconds <= 86400:
        raise ValueError("Use a declared ingestion domain and bounded lease")
    native = domain == "structured"
    table = sa.table(
        "flyquery_ingest_jobs" if native else "canon_ingest_jobs",
        sa.column("id", sa.Uuid if native else sa.String),
        sa.column("tenant_id", sa.String),
        sa.column("workspace_id", sa.Uuid if native else sa.String),
        sa.column("status", sa.String),
        sa.column("kind", sa.String),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("started_at", sa.DateTime(timezone=True)),
    )
    ready = sa.or_(
        table.c.status == ("PENDING" if native else "queued"),
        sa.and_(
            table.c.status == ("RUNNING" if native else "running"),
            table.c.started_at <= now - timedelta(seconds=lease_seconds),
        ),
    )
    statement = sa.select(table.c.id, table.c.tenant_id, table.c.workspace_id).where(ready)
    if not native:
        statement = statement.where(table.c.kind == "ingest")
    return statement.order_by(table.c.created_at, table.c.id).limit(1)


@service(name="operations.ingestion_drain")
@conditional_on_property("koinon.knowledge.enabled", having_value="true", match_if_missing=True)
@conditional_on_property("koinon.process.role", having_value="worker")
class IngestionDrain:
    def __init__(
        self,
        datasources: DataSourceRegistry,
        container: Container,
        authority: IngestionExecutionAuthority,
        admission: WorkAdmission,
    ):
        self.datasources, self.container, self.authority = datasources, container, authority
        self.admission = admission

    @scheduled(fixed_delay=timedelta(seconds=1))
    async def tick(self):
        # One immediately processed job per domain; a claimed lease never waits in a local batch.
        async with asyncio.TaskGroup() as tasks:
            for domain in ("canon", "structured"):
                tasks.create_task(self._one(domain))

    async def _one(self, domain):
        async with self.admission.hold("document" if domain == "canon" else "structured"):
            await self._execute_one(domain)

    async def _execute_one(self, domain):
        from flycanon.config import CanonSettings
        from flycanon.core.services.sources.async_ingest_service import AsyncIngestService
        from flyquery.config import FlyquerySettings
        from flyquery.core.services.ingestion.workers import IngestWorker

        kind = AsyncIngestService if domain == "canon" else IngestWorker
        if not self.container.contains_type(kind):
            return
        if domain == "canon":
            canon = self.container.resolve(CanonSettings)
            lease, timeout = canon.ingest_timeout_s, canon.worker_handler_timeout_s
        else:
            structured = self.container.resolve(FlyquerySettings)
            lease, timeout = structured.processing_lease_s, structured.ingest_handler_timeout_s
        if not timeout >= 1 or not timeout + 30 <= lease <= 86400:
            raise ValueError("The ingestion lease must cover its handler timeout and 30-second commit margin")
        source = self.datasources.get(domain + "_admin")
        try:
            async with TransactionTemplate(
                source,
                propagation=Propagation.REQUIRES_NEW,
                isolation=Isolation.SERIALIZABLE,
                read_only=True,
                read_from_primary=True,
            ).transaction() as unit:
                assert unit is not None
                row = (
                    (await unit.resource.execute(pending_statement(domain, datetime.now(UTC), lease)))
                    .mappings()
                    .one_or_none()
                )
            if row is None:
                return
            worker = self.container.resolve(kind)
            async with asyncio.timeout(timeout):
                with native_scope(
                    domain, row["tenant_id"], str(row["workspace_id"]), "system:ingest-discovery"
                ):

                    def admission(job, claim):
                        return self.authority.admit(domain, job, claim)

                    if domain == "canon":
                        await worker.process(str(row["id"]), admission=admission)
                    else:
                        await worker.process(
                            row["id"], row["tenant_id"], str(row["workspace_id"]), admission=admission
                        )
        except Exception as error:
            logger.warning(
                "Durable ingestion remains pending",
                extra={
                    "domain": domain,
                    "error_code": str(getattr(error, "code", None) or "INGEST_WORKER_RETRY")[:64],
                    "error_type": type(error).__name__,
                },
            )
