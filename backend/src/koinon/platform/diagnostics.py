# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Passive health uses existing native readers and never the storage roundtrip probe."""

import asyncio

from pyfly.container import component as managed_component
from pyfly.core import Config

from koinon.catalog.errors import AccessDenied
from koinon.communications.readiness import EmailReadiness
from koinon.operations.service import OperationsService
from koinon.platform.dtos import HealthComponent, HealthComponentId
from koinon.platform.mappers import component, counts
from koinon.platform.native import PlatformNativeObservations
from koinon.platform.repositories import PlatformRepository, StatusWindow

_DATABASES: dict[str, HealthComponentId] = {
    "primary": "database-primary",
    "canon": "database-documents",
    "canon_admin": "database-documents-control",
    "structured": "database-structured",
    "structured_admin": "database-structured-control",
}


@managed_component(name="platform.diagnostics")
class PlatformDiagnostics:
    def __init__(
        self,
        operations: OperationsService,
        records: PlatformRepository,
        native: PlatformNativeObservations,
        readiness: EmailReadiness,
        config: Config,
    ):
        self.operations, self.records, self.native, self.readiness, self.config = (
            operations,
            records,
            native,
            readiness,
            config,
        )

    async def observe(self, subject: str, tenant_id: str) -> list[HealthComponent]:
        results = await self._databases()
        enabled = self.config.get("koinon.knowledge.enabled", True) is True
        for domain in ("documents", "structured"):
            storage_id: HealthComponentId = (
                "storage-documents" if domain == "documents" else "storage-structured"
            )
            results.append(
                component(
                    storage_id,
                    configured=enabled,
                    status="unknown" if enabled else "disabled",
                    basis="configuration",
                    reason="STORAGE_NOT_PROBED" if enabled else "MODULE_DISABLED",
                    remediation="review_configuration",
                )
            )
            if not enabled:
                disabled: tuple[HealthComponentId, ...] = (
                    ("indexes-documents", "ingestion-documents")
                    if domain == "documents"
                    else ("indexes-structured", "ingestion-structured")
                )
                for identifier in disabled:
                    results.append(
                        component(
                            identifier,
                            configured=False,
                            status="disabled",
                            basis="configuration",
                            reason="MODULE_DISABLED",
                            remediation="none",
                        )
                    )
                continue
            results.append(await self._indexes(subject, tenant_id, domain))
            results.append(await self._ingestion(subject, tenant_id, domain))
        configured = await self.records.model_default_configured(tenant_id)
        results.append(
            component(
                "model-configuration",
                configured=configured,
                basis="configuration",
                status="unknown" if configured else "failed",
                reason="MODEL_CONFIGURATION_PRESENT" if configured else "MODEL_CONFIGURATION_INCOMPLETE",
                remediation="review_configuration",
            )
        )
        try:
            mail = self.readiness.observe()
            results.append(
                component(
                    "communications",
                    configured=mail.state != "disabled",
                    basis="configuration",
                    status="disabled"
                    if mail.state == "disabled"
                    else "failed"
                    if mail.state != "ready"
                    else "unknown",
                    reason="COMMUNICATIONS_DISABLED"
                    if mail.state == "disabled"
                    else "COMMUNICATIONS_CONFIGURED"
                    if mail.state == "ready"
                    else "COMMUNICATIONS_INCOMPLETE",
                    remediation="review_communications",
                )
            )
        except AccessDenied:
            raise
        except Exception:
            results.append(component("communications", remediation="review_communications"))
        results.append(component("workers", reason="WORKER_LIVENESS_UNKNOWN", remediation="review_worker"))
        return results

    async def _databases(self) -> list[HealthComponent]:
        sources = {value.name: value for value in self.operations.sources.datasources()}
        try:
            if len(self.operations.sources.all_datasources()) > 10:
                raise ValueError("Datasource observation bound exceeded")
            async with asyncio.timeout(2):
                observation = await self.operations.health.health()
            details = observation.details.get("datasources", {})
        except AccessDenied:
            raise
        except Exception:
            observation, details = None, {}
        results = []
        for name, identifier in _DATABASES.items():
            source = sources.get(name)
            if source is None:
                results.append(component(identifier, configured=False, remediation="review_configuration"))
                continue
            status = (
                details.get(source.qualified_name, {}).get("status", "UNKNOWN")
                if details
                else observation.status
                if observation
                else "UNKNOWN"
            )
            if status != "UP":
                results.append(
                    component(
                        identifier,
                        status="failed" if status == "DOWN" else "unknown",
                        reason="DATABASE_UNAVAILABLE",
                        remediation="review_configuration",
                    )
                )
                continue
            policy = await self.operations._role_policy(source)
            valid = policy.get("available")
            results.append(
                component(
                    identifier,
                    status="passed" if valid is True else "failed" if valid is False else "unknown",
                    basis="observed",
                    reason="DATABASE_OK"
                    if valid is True
                    else "RUNTIME_ROLE_UNSAFE"
                    if valid is False
                    else "RUNTIME_ROLE_UNVERIFIED",
                    remediation="none" if valid is True else "review_configuration",
                    coverage="complete",
                )
            )
        return results

    async def _ingestion(self, subject: str, tenant_id: str, domain: str) -> HealthComponent:
        identifier: HealthComponentId = (
            "ingestion-documents" if domain == "documents" else "ingestion-structured"
        )
        try:
            async with asyncio.timeout(2):
                window = await self.native.ingestion(subject, tenant_id, domain)
            failed = counts(window).observed_failed > 0
            return component(
                identifier,
                status="failed" if failed else "unknown",
                basis="observed",
                reason="INGESTION_FAILURES" if failed else "INGESTION_STATE_OBSERVED",
                remediation="review_ingestion",
                window=window,
            )
        except AccessDenied:
            raise
        except Exception:
            async with asyncio.timeout(2):
                window = await self.records.catalog_states(
                    tenant_id, "document" if domain == "documents" else "dataset"
                )
            return component(
                identifier,
                reason="OBSERVATION_UNAVAILABLE",
                remediation="review_ingestion",
                window=StatusWindow(window.states, False),
            )

    async def _indexes(self, subject: str, tenant_id: str, domain: str) -> HealthComponent:
        identifier: HealthComponentId = "indexes-documents" if domain == "documents" else "indexes-structured"
        try:
            async with asyncio.timeout(2):
                targets, complete = await self.records.index_targets(tenant_id)
                selected = tuple(row for row in targets if row.domain == domain)
                window = StatusWindow(tuple(row.status for row in selected), complete)
                if not selected:
                    return component(
                        identifier, reason="NO_INDEXES", remediation="review_indexes", window=window
                    )
                work = counts(window)
                pending = work.observed_pending > 0 or work.observed_running > 0
                valid = complete and not pending and await self.native.indexes(subject, tenant_id, selected)
            return component(
                identifier,
                status="passed" if valid else "failed" if complete and not pending else "unknown",
                basis="observed",
                reason="INDEXES_VERIFIED" if valid else "INDEXES_INCOMPLETE",
                remediation="none" if valid else "review_indexes",
                window=window,
            )
        except AccessDenied:
            raise
        except Exception:
            return component(identifier, reason="INDEXES_NOT_PROBED", remediation="review_indexes")
