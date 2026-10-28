# Copyright 2026 Firefly Software Foundation & Firefly Software Solutions Inc.
# SPDX-License-Identifier: Apache-2.0
"""Canonical authorization precedes every exact native lineage lookup."""

from dataclasses import asdict
from uuid import UUID

from pydantic import ValidationError
from pyfly.container import Provider, service
from pyfly.data.relational.datasource_registry import NoSuchDataSourceError
from pyfly.kernel import InvalidRequestException, ServiceUnavailableException

from koinon.catalog.errors import AccessDenied, InvalidHierarchy
from koinon.knowledge.entities import DomainBinding
from koinon.knowledge.lineage.dtos import SnapshotLineage
from koinon.knowledge.lineage.ports import StructuredSnapshotLineagePort
from koinon.knowledge.provenance.dtos import TableProvenance, TableSnapshotPage, TableSnapshotSummary
from koinon.knowledge.service import KnowledgeFacade


@service
class TableProvenanceService:
    def __init__(self, knowledge: KnowledgeFacade, lineage: Provider[StructuredSnapshotLineagePort | None]):
        self.knowledge = knowledge
        self.lineage = lineage

    def _reader(self) -> StructuredSnapshotLineagePort:
        reader = self.lineage.get()
        if reader is None:
            raise ServiceUnavailableException(
                "Structured version provenance is not configured", code="PROVENANCE_UNAVAILABLE"
            )
        return reader

    async def _bindings(
        self, subject: str, tenant_id: str, dataset_id: str, table_id: str
    ) -> tuple[DomainBinding, DomainBinding]:
        dataset = (await self.knowledge._chain(subject, tenant_id, dataset_id))[0]
        table = (await self.knowledge._chain(subject, tenant_id, table_id))[0]
        if dataset.kind != "dataset" or table.kind != "table":
            raise InvalidHierarchy("Choose a dataset and one of its tables", code="INVALID_TABLE")
        if table.parent_id != dataset.id:
            raise AccessDenied("The table is unavailable in this dataset", code="INVALID_TABLE_SCOPE")
        dataset_binding = await self.knowledge.binding(tenant_id, dataset_id, "structured", entry=dataset)
        table_binding = await self.knowledge.binding(tenant_id, table_id, "structured", entry=table)
        if dataset_binding.native_workspace_id != table_binding.native_workspace_id:
            raise AccessDenied(
                "Native lineage scope disagrees with catalog", code="PROVENANCE_SCOPE_MISMATCH"
            )
        return dataset_binding, table_binding

    @staticmethod
    def _scope(
        row: SnapshotLineage,
        tenant_id: str,
        dataset: DomainBinding,
        table: DomainBinding,
        snapshot_id: str | None = None,
    ) -> None:
        if (
            row.tenant_id != tenant_id
            or row.workspace_id != dataset.native_workspace_id
            or row.dataset_id != dataset.native_id
            or row.table_id != table.native_id
            or (snapshot_id is not None and row.snapshot_id != snapshot_id)
        ):
            raise AccessDenied("The requested provenance is unavailable", code="PROVENANCE_SCOPE_MISMATCH")

    @staticmethod
    def _detail(row: SnapshotLineage, dataset_id: str, table_id: str) -> TableProvenance:
        values = asdict(row)
        values.pop("tenant_id")
        values.pop("workspace_id")
        values.update(
            native_dataset_id=row.dataset_id,
            native_table_id=row.table_id,
            dataset_id=dataset_id,
            table_id=table_id,
        )
        try:
            return TableProvenance.model_validate(values)
        except ValidationError as error:
            raise ServiceUnavailableException(
                "The recorded provenance is incomplete", code="PROVENANCE_RECORD_INVALID"
            ) from error

    async def snapshot(
        self, subject: str, tenant_id: str, dataset_id: str, table_id: str, snapshot_id: str
    ) -> TableProvenance:
        try:
            requested = str(UUID(snapshot_id))
        except (ValueError, TypeError, AttributeError) as error:
            raise InvalidRequestException("Choose a valid snapshot", code="INVALID_SNAPSHOT") from error
        dataset, table = await self._bindings(subject, tenant_id, dataset_id, table_id)
        try:
            rows = await self._reader().read_snapshots(
                actor=subject,
                tenant_id=tenant_id,
                workspace_id=dataset.native_workspace_id,
                dataset_id=dataset.native_id,
                snapshot_ids=(requested,),
            )
        except NoSuchDataSourceError:
            raise ServiceUnavailableException(
                "Configure the structured datasource to inspect version provenance",
                code="PROVENANCE_UNAVAILABLE",
            ) from None
        if len(rows) != 1:
            raise ServiceUnavailableException(
                "The recorded provenance is incomplete", code="PROVENANCE_RECORD_INVALID"
            )
        self._scope(rows[0], tenant_id, dataset, table, requested)
        return self._detail(rows[0], dataset_id, table_id)

    async def history(
        self,
        subject: str,
        tenant_id: str,
        dataset_id: str,
        table_id: str,
        *,
        page: int = 1,
        page_size: int = 25,
    ) -> TableSnapshotPage:
        if (
            type(page) is not int
            or type(page_size) is not int
            or page < 1
            or not 1 <= page_size <= 100
            or (page - 1) * page_size > 1_000_000
        ):
            raise InvalidRequestException("Choose a valid page and page size up to 100", code="INVALID_PAGE")
        dataset, table = await self._bindings(subject, tenant_id, dataset_id, table_id)
        try:
            result = await self._reader().read_table_history(
                actor=subject,
                tenant_id=tenant_id,
                workspace_id=dataset.native_workspace_id,
                dataset_id=dataset.native_id,
                table_id=table.native_id,
                page=page,
                page_size=page_size,
            )
        except NoSuchDataSourceError:
            raise ServiceUnavailableException(
                "Configure the structured datasource to inspect version history",
                code="PROVENANCE_UNAVAILABLE",
            ) from None
        if (
            type(result.total) is not int
            or result.total < 0
            or result.page != page
            or result.page_size != page_size
            or result.total_pages != (result.total + page_size - 1) // page_size
            or result.has_next != (page * page_size < result.total)
            or result.has_previous != (page > 1)
            or len(result.items) > page_size
            or len(result.items) > max(0, result.total - (page - 1) * page_size)
            or len({row.snapshot_id for row in result.items}) != len(result.items)
        ):
            raise ServiceUnavailableException(
                "Version history changed. Reload it and try again.", code="PROVENANCE_PAGE_INVALID"
            )
        summaries = []
        for row in result.items:
            self._scope(row, tenant_id, dataset, table)
            detail = self._detail(row, dataset_id, table_id)
            summaries.append(
                TableSnapshotSummary.model_validate(
                    detail.model_dump(include=set(TableSnapshotSummary.model_fields))
                )
            )
        return TableSnapshotPage(
            items=tuple(summaries),
            total=result.total,
            page=page,
            page_size=page_size,
            pages=result.total_pages,
            has_next=result.has_next,
            has_previous=result.has_previous,
            current_snapshot_id=result.current_snapshot_id,
        )
