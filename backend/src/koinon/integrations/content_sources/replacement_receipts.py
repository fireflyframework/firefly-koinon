# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Exact source replacement receipt correlation without protected metadata hydration."""

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime

from pyfly.kernel import ConflictException
from sqlalchemy import cast, func, select, update
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from koinon.catalog.entities import CatalogEntry, Membership, Tenant
from koinon.integrations.content_sources.entities import PersonalSourceConnection
from koinon.integrations.content_sources.import_entities import SourceImportAttempt
from koinon.integrations.content_sources.mapping_entities import SourceMapping, SourceObject
from koinon.integrations.content_sources.publication_entities import (
    SourcePublicationBaseline,
    SourcePublicationTarget,
)
from koinon.integrations.content_sources.sync_entities import (
    SourceSyncObservation,
    SourceSyncRun,
    SourceSyncWork,
)
from koinon.integrations.content_sources.sync_runs import SourceRunLease
from koinon.jobs.entities import Job
from koinon.knowledge.bulk.ports import NativeCommit, SourceIntakeAdmission


def changed():
    return ConflictException(
        "The retained source receipt identity changed", code="SOURCE_REPLACEMENT_CHANGED"
    )


@dataclass(frozen=True, slots=True)
class ReplacementReceiptIdentity:
    id: str
    content_operation_id: str
    source_id: str
    asset_id: str
    sha256: str
    size_bytes: int
    domain: str
    descriptor_sha256: str
    native_workspace_id: str
    native_source_id: str
    native_asset_id: str
    native_file_id: str | None
    tables: tuple[tuple[str, str, str], ...]
    acknowledged: bool

    def matches(self, receipt: NativeCommit) -> bool:
        return (
            receipt.source_attempt_id,
            receipt.source_publication_sha256,
            receipt.domain,
            receipt.native_workspace_id,
            receipt.native_source_id,
            receipt.native_asset_id,
            receipt.sha256,
            receipt.size_bytes,
        ) == (
            self.id,
            self.descriptor_sha256,
            self.domain,
            self.native_workspace_id,
            self.native_source_id,
            self.native_asset_id,
            self.sha256,
            self.size_bytes,
        ) and (
            self.domain == "canon"
            and bool(receipt.source_version_id and receipt.extraction_id)
            and not receipt.tables
            and receipt.native_file_id is None
            or self.domain == "structured"
            and receipt.file_version_id == self.content_operation_id
            and receipt.native_file_id == self.native_file_id
            and tuple((table.catalog_table_id, table.table_id, table.snapshot_id) for table in receipt.tables)
            == self.tables
        )


class ReplacementReceipts:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def capture(
        self, admission: SourceIntakeAdmission, execution: SourceRunLease
    ) -> ReplacementReceiptIdentity | None:
        """Lock retained producer coordinates; expiry and lost permission grant no publication."""
        if len(admission.items) != 1:
            raise changed()
        pin = admission.items[0]
        session = self.session
        await session.scalar(select(Tenant.id).where(Tenant.id == admission.tenant_id).with_for_update())
        await session.execute(
            select(Membership.id)
            .where(
                Membership.tenant_id == admission.tenant_id,
                Membership.subject == admission.owner,
            )
            .order_by(Membership.id)
            .with_for_update(read=True)
        )
        await session.execute(
            select(CatalogEntry.id)
            .where(
                CatalogEntry.tenant_id == admission.tenant_id,
                CatalogEntry.id.in_(admission.destination),
            )
            .order_by(CatalogEntry.id)
            .with_for_update(read=True)
        )
        connection = await session.scalar(
            select(PersonalSourceConnection.id)
            .join(SourceMapping, SourceMapping.connection_id == PersonalSourceConnection.id)
            .where(
                SourceMapping.id == admission.mapping_id,
                SourceMapping.tenant_id == admission.tenant_id,
                SourceMapping.owner == admission.owner,
                PersonalSourceConnection.tenant_id == admission.tenant_id,
                PersonalSourceConnection.owner == admission.owner,
            )
            .with_for_update(of=PersonalSourceConnection)
        )
        mapping = await session.scalar(
            select(SourceMapping.id)
            .where(
                SourceMapping.id == admission.mapping_id,
                SourceMapping.tenant_id == admission.tenant_id,
                SourceMapping.owner == admission.owner,
                SourceMapping.connection_id == connection,
            )
            .with_for_update()
        )
        origin = await session.scalar(
            select(SourceObject.id)
            .where(
                SourceObject.id == pin.object_id,
                SourceObject.tenant_id == admission.tenant_id,
                SourceObject.mapping_id == mapping,
            )
            .with_for_update()
        )
        run = (
            await session.execute(
                select(
                    SourceSyncRun.id,
                    SourceSyncRun.page_sequence,
                )
                .where(
                    SourceSyncRun.id == execution.run_id,
                    SourceSyncRun.id == admission.run_id,
                    SourceSyncRun.tenant_id == execution.tenant_id,
                    SourceSyncRun.tenant_id == admission.tenant_id,
                    SourceSyncRun.mapping_id == execution.mapping_id,
                    SourceSyncRun.mapping_id == mapping,
                    SourceSyncRun.job_id == execution.job_id,
                    SourceSyncRun.policy_id == execution.policy_id,
                    SourceSyncRun.mapping_revision == execution.mapping_revision,
                    SourceSyncRun.mapping_revision == admission.mapping_revision,
                    SourceSyncRun.connection_revision == execution.connection_revision,
                    SourceSyncRun.connection_revision == admission.connection_revision,
                )
                .with_for_update()
            )
        ).one_or_none()
        if (
            connection is None
            or mapping is None
            or origin is None
            or run is None
            or execution.owner != admission.owner
        ):
            raise changed()
        observed = await session.scalar(
            select(SourceSyncObservation.id).where(
                SourceSyncObservation.id == pin.observation_id,
                SourceSyncObservation.tenant_id == admission.tenant_id,
                SourceSyncObservation.mapping_id == mapping,
                SourceSyncObservation.run_id == run.id,
                SourceSyncObservation.object_id == origin,
                SourceSyncObservation.generation == pin.generation,
                SourceSyncObservation.work_id == pin.work_id,
                SourceSyncObservation.remote_version == pin.remote_version,
                SourceSyncObservation.page_sequence == pin.page_sequence,
                SourceSyncObservation.item_sequence == pin.item_sequence,
                SourceSyncObservation.event_sha256 == pin.event_sha256,
                SourceSyncObservation.page_sequence <= run.page_sequence,
            )
        )
        work = (
            await session.execute(
                select(SourceSyncWork.id, SourceSyncWork.attempt_id)
                .where(
                    SourceSyncWork.id == pin.work_id,
                    SourceSyncWork.tenant_id == admission.tenant_id,
                    SourceSyncWork.mapping_id == mapping,
                    SourceSyncWork.object_id == origin,
                    SourceSyncWork.generation == pin.generation,
                    SourceSyncWork.remote_version == pin.remote_version,
                    SourceSyncWork.event_sha256 == pin.event_sha256,
                )
                .with_for_update()
            )
        ).one_or_none()
        if observed is None or work is None:
            raise changed()
        identity = None
        if work.attempt_id is not None:
            identity = await self._attempt(admission, work.attempt_id)
        # Job is last: a superseded worker never borrows the successor's receipt-only execution.
        job = await session.scalar(
            select(Job.id)
            .where(
                Job.id == execution.job_id,
                Job.tenant_id == admission.tenant_id,
                Job.resource_id == mapping,
                Job.kind == "content.source.reconcile",
                Job.worker_id == execution.worker_id,
                Job.attempts == execution.attempt,
            )
            .with_for_update()
        )
        if job is None:
            raise changed()
        return identity

    async def _attempt(self, admission, attempt_id):
        pin = admission.items[0]
        attempt = SourceImportAttempt
        header = SourcePublicationBaseline
        descriptor = header.descriptor_json
        marker = CatalogEntry.metadata_json["_koinon_source_replacement"]
        fields = [
            attempt.id,
            attempt.content_operation_id,
            attempt.source_id,
            attempt.asset_id,
            attempt.sha256,
            attempt.size_bytes,
            header.descriptor_sha256,
            header.producer_kind,
            header.acknowledgement_json.is_not(None).label("acknowledged"),
            descriptor["native"]["domain"].as_string().label("domain"),
            descriptor["native"]["workspace_id"].as_string().label("native_workspace_id"),
            marker["native_file_id"].as_string().label("native_file_id"),
            func.jsonb_array_length(cast(descriptor["members"], JSONB)).label("member_count"),
        ]
        for index in range(32):
            for field in ("action", "catalog_table_id", "table_id", "snapshot_id"):
                fields.append(descriptor["members"][index][field].as_string().label(f"m{index}_{field}"))
        row = (
            (
                await self.session.execute(
                    select(*fields)
                    .join(header, header.attempt_id == attempt.id)
                    .join(CatalogEntry, CatalogEntry.id == attempt.content_operation_id)
                    .where(
                        attempt.id == attempt_id,
                        attempt.tenant_id == admission.tenant_id,
                        attempt.mapping_id == admission.mapping_id,
                        attempt.mapping_revision == admission.mapping_revision,
                        attempt.object_id == pin.object_id,
                        attempt.generation == pin.generation,
                        attempt.remote_version == pin.remote_version,
                        attempt.intake_item_id.is_(None),
                        header.tenant_id == attempt.tenant_id,
                        header.mapping_id == attempt.mapping_id,
                        header.object_id == attempt.object_id,
                        header.source_id == attempt.source_id,
                        header.asset_id == attempt.asset_id,
                        header.workspace_id == admission.destination[0],
                        header.project_id == admission.destination[1],
                        header.descriptor_sha256.is_not(None),
                        descriptor["observation"]["run_id"].as_string() == admission.run_id,
                        descriptor["observation"]["work_id"].as_string() == pin.work_id,
                        descriptor["observation"]["observation_id"].as_string() == pin.observation_id,
                        descriptor["producer"]["content_operation_id"].as_string()
                        == attempt.content_operation_id,
                        CatalogEntry.tenant_id == admission.tenant_id,
                    )
                    .with_for_update(of=(attempt, header))
                )
            )
            .mappings()
            .one_or_none()
        )
        if (
            row is None
            or row["domain"] not in {"canon", "structured"}
            or row["producer_kind"] != ("replace_document" if row["domain"] == "canon" else "replace_dataset")
        ):
            raise changed()
        targets = (
            (
                await self.session.execute(
                    select(
                        SourcePublicationTarget.role,
                        SourcePublicationTarget.catalog_id,
                        SourcePublicationTarget.parent_id,
                        SourcePublicationTarget.native_domain,
                        SourcePublicationTarget.native_workspace_id,
                        SourcePublicationTarget.native_id,
                    )
                    .where(
                        SourcePublicationTarget.attempt_id == attempt_id,
                        SourcePublicationTarget.tenant_id == admission.tenant_id,
                        SourcePublicationTarget.role.in_(("source", "asset")),
                    )
                    .order_by(SourcePublicationTarget.catalog_id)
                )
            )
            .mappings()
            .all()
        )
        target = {value["role"]: value for value in targets}
        if (
            len(targets) != 2
            or set(target) != {"source", "asset"}
            or target["source"]["catalog_id"] != row["source_id"]
            or target["asset"]["catalog_id"] != row["asset_id"]
            or target["source"]["parent_id"] != admission.destination[2]
            or any(
                not value["native_id"]
                or value["native_domain"] != row["domain"]
                or value["native_workspace_id"] != row["native_workspace_id"]
                for value in targets
            )
            or type(row["member_count"]) is not int
            or not 0 <= row["member_count"] <= 32
        ):
            raise changed()
        members = tuple(
            tuple(row[f"m{index}_{field}"] for field in ("catalog_table_id", "table_id", "snapshot_id"))
            for index in range(row["member_count"])
            if row[f"m{index}_action"] != "remove"
        )
        if row["domain"] == "structured" and (not row["native_file_id"] or not 1 <= len(members) <= 16):
            raise changed()
        if row["domain"] == "canon" and members:
            raise changed()
        return ReplacementReceiptIdentity(
            row["id"],
            row["content_operation_id"],
            row["source_id"],
            row["asset_id"],
            row["sha256"],
            row["size_bytes"],
            row["domain"],
            row["descriptor_sha256"],
            row["native_workspace_id"],
            target["source"]["native_id"],
            target["asset"]["native_id"],
            row["native_file_id"],
            members,
            row["acknowledged"],
        )

    async def record(self, admission, execution, expected, receipt, *, audit):
        identity = await self.capture(admission, execution)
        if identity is None or identity != expected or not identity.matches(receipt):
            raise changed()
        encoded = json.loads(json.dumps(asdict(receipt)))
        retained = {**encoded, "operation_id": identity.content_operation_id}
        row = (
            await self.session.execute(
                select(
                    SourceImportAttempt.receipt_json.is_(None).label("missing"),
                    (cast(SourceImportAttempt.receipt_json, JSONB) == retained).label("same"),
                    (SourcePublicationBaseline.acknowledgement_json["native_receipt"] == encoded).label(
                        "ack_same"
                    ),
                )
                .join(
                    SourcePublicationBaseline, SourcePublicationBaseline.attempt_id == SourceImportAttempt.id
                )
                .where(SourceImportAttempt.id == identity.id)
            )
        ).one()
        if identity.acknowledged:
            if not row.same or not row.ack_same:
                raise changed()
            return "acknowledged"
        if not row.missing and not row.same:
            raise changed()
        if row.missing:
            await self.session.execute(
                update(SourceImportAttempt)
                .where(
                    SourceImportAttempt.id == identity.id,
                    SourceImportAttempt.receipt_json.is_(None),
                )
                .values(receipt_json=retained, committed_at=datetime.now(UTC))
            )
            await audit(
                admission.owner,
                admission.tenant_id,
                "knowledge.source.receipt_recorded",
                identity.content_operation_id,
                {"attempt_id": identity.id},
            )
        await self.session.execute(
            update(SourceSyncWork)
            .where(
                SourceSyncWork.id == admission.items[0].work_id,
                SourceSyncWork.attempt_id == identity.id,
            )
            .values(status="conflict", error_code="SOURCE_PUBLICATION_NOT_ACKNOWLEDGED")
        )
        await self.session.flush()
        return "conflict"
