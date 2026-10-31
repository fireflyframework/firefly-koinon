# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Managed callbacks retain their exact originating execution authority."""

import json
from uuid import UUID

import sqlalchemy as sa
from flyquery.core.services.callbacks.access import CallbackDeliveryAccess
from flyquery.core.services.callbacks.admission import CallbackWorkAdmission
from pydantic import ValidationError
from pyfly.container import service
from pyfly.context.conditions import conditional_on_property
from pyfly.context.consumer_context import PRIVATE_CONSUMER_CONTEXT
from pyfly.data.relational.datasource_registry import DataSourceRegistry
from pyfly.data.transaction import Isolation, Propagation, TransactionTemplate
from pyfly.security.context import SecurityContext
from pyfly.security.context_holder import SecurityContextHolder

from koinon.workers.admission import WorkAdmission
from koinon.workers.execution import IngestionExecution, IngestionExecutionAuthority, unavailable


@service(name="operations.callback_authority")
@conditional_on_property("koinon.knowledge.enabled", having_value="true", match_if_missing=True)
class ManagedCallbackAccess(CallbackDeliveryAccess):
    def __init__(self, datasources: DataSourceRegistry, authority: IngestionExecutionAuthority):
        self.datasources, self.authority = datasources, authority

    async def authorize(self, claim):
        source = self.datasources.get("structured")
        jobs = sa.table(
            "flyquery_ingest_jobs",
            sa.column("id", sa.Uuid),
            sa.column("tenant_id", sa.String),
            sa.column("workspace_id", sa.Uuid),
            sa.column("request_json", sa.JSON),
            sa.column("status", sa.String),
            sa.column("attempts", sa.Integer),
        )
        async with TransactionTemplate(
            source,
            propagation=Propagation.REQUIRES_NEW,
            isolation=Isolation.SERIALIZABLE,
            read_only=True,
            read_from_primary=True,
        ).transaction() as unit:
            assert unit is not None
            row = (
                (
                    await unit.resource.execute(
                        sa.select(
                            jobs.c.tenant_id,
                            jobs.c.workspace_id,
                            jobs.c.request_json,
                            jobs.c.status,
                            jobs.c.attempts,
                        ).where(
                            jobs.c.id == claim["ingest_job_id"],
                            jobs.c.tenant_id == claim["tenant_id"],
                            jobs.c.workspace_id == UUID(str(claim["workspace_id"])),
                        )
                    )
                )
                .mappings()
                .one_or_none()
            )
        if row is None:
            raise unavailable()
        private = row["request_json"]
        payload = claim["payload_json"]
        if isinstance(private, str):
            private = json.loads(private)
        if isinstance(payload, str):
            payload = json.loads(payload)
        try:
            value = IngestionExecution.model_validate((private or {}).get(PRIVATE_CONSUMER_CONTEXT))
        except (ValidationError, ValueError, TypeError):
            raise unavailable() from None
        if (value.domain, value.tenant_id, value.native_workspace_id) != (
            "structured",
            row["tenant_id"],
            str(row["workspace_id"]),
        ) or (payload.get("attempts"), payload.get("status")) != (row["attempts"], row["status"]):
            raise unavailable()
        issuer, _, subject = value.subject.partition("|")
        attributes = {"iss": issuer, "sub": subject}
        if value.token_id:
            attributes["koinon_token_id"] = value.token_id
        with SecurityContextHolder.using(SecurityContext(user_id=subject, attributes=attributes)):
            await self.authority.validate(value)


@service(name="operations.callback_work_admission")
@conditional_on_property("koinon.knowledge.enabled", having_value="true", match_if_missing=True)
class ManagedCallbackWorkAdmission(CallbackWorkAdmission):
    def __init__(self, admission: WorkAdmission):
        self.admission = admission

    def admit(self):
        return self.admission.hold("callback")
