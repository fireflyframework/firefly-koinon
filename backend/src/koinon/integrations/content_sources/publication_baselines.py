# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Retain canonical reservation evidence before a native source operation can publish."""

import json
from dataclasses import asdict, dataclass

from pyfly.kernel import ConflictException
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from koinon.catalog.entities import CatalogEntry
from koinon.integrations.content_sources.import_entities import SourceImportAttempt
from koinon.integrations.content_sources.publication_entities import (
    SourcePublicationBaseline,
    SourcePublicationTarget,
)
from koinon.knowledge.bulk.dataset_dtos import DatasetReservation
from koinon.knowledge.bulk.entities import BulkItem, BulkTableReservation
from koinon.knowledge.bulk.ports import SourceIntakeAdmission, SourcePublicationBinding
from koinon.knowledge.entities import DomainBinding


def conflict():
    return ConflictException("The retained publication baseline changed", code="SOURCE_PUBLICATION_CONFLICT")


@dataclass(frozen=True, slots=True)
class CanonicalPublicationPin:
    catalog_id: str
    tenant_id: str
    workspace_id: str
    project_id: str
    role: str
    disposition: str
    parent_id: str | None
    kind: str
    mutation_revision: int
    status: str
    native_domain: str | None
    native_workspace_id: str | None
    native_id: str | None
    native_version_id: str | None
    native_snapshot_id: str | None

    @classmethod
    def retained(cls, row: SourcePublicationTarget):
        return cls(**{name: getattr(row, name) for name in cls.__dataclass_fields__})


class SourcePublicationBaselines:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _committed_header(self, attempt, receipt):
        header = await self.session.scalar(
            select(SourcePublicationBaseline)
            .where(
                SourcePublicationBaseline.attempt_id == attempt.id,
                SourcePublicationBaseline.tenant_id == attempt.tenant_id,
            )
            .with_for_update()
        )
        if (
            header is None
            or header.descriptor_json is None
            or not header.descriptor_sha256
            or receipt.source_attempt_id != attempt.id
            or receipt.source_publication_sha256 != header.descriptor_sha256
            or receipt.sha256 != attempt.sha256
            or receipt.size_bytes != attempt.size_bytes
        ):
            raise conflict()
        return header

    async def open(self, attempt, receipt) -> tuple[CanonicalPublicationPin, ...]:
        header = await self._committed_header(attempt, receipt)
        if header.acknowledgement_json is not None:
            raise conflict()
        pins = await self.verify_before_publication(header)
        await self.session.execute(
            text("SELECT public.koinon_open_source_publication(:attempt,CAST(:receipt AS jsonb))"),
            {"attempt": attempt.id, "receipt": json.dumps(asdict(receipt))},
        )
        return pins

    async def acknowledge(self, attempt, receipt) -> str:
        header = await self._committed_header(attempt, receipt)
        encoded = json.loads(json.dumps(asdict(receipt)))
        if header.acknowledgement_json is not None:
            if header.acknowledgement_json["native_receipt"] != encoded or not header.acknowledgement_sha256:
                raise conflict()
            return header.acknowledgement_sha256
        await self.session.flush()
        vector = list(
            (
                await self.session.scalars(
                    select(
                        func.koinon_publication_current(
                            SourcePublicationTarget.attempt_id,
                            SourcePublicationTarget.catalog_id,
                        )
                    )
                    .where(SourcePublicationTarget.attempt_id == attempt.id)
                    .order_by(SourcePublicationTarget.catalog_id)
                )
            ).all()
        )
        if header.descriptor_json is None:
            raise conflict()
        targets = header.descriptor_json["targets"]
        if len(vector) != len(targets) or any(
            current is None
            or current["catalog_id"] != target["pin"]["catalog_id"]
            or current["mutation_revision"] != target["pin"]["mutation_revision"] + len(target["writes"])
            for current, target in zip(vector, targets, strict=True)
        ):
            raise conflict()
        header.acknowledgement_json = {
            "schema": "koinon.source-publication-acknowledgement.v1",
            "attempt_id": attempt.id,
            "descriptor_sha256": header.descriptor_sha256,
            "native_receipt": encoded,
            "transition_vector": vector,
            "live_vector": [
                value for value in vector if value["disposition"] != "remove" and value["role"] != "old_index"
            ],
        }
        await self.session.flush()
        await self.session.refresh(header, attribute_names=["acknowledgement_sha256"])
        if not header.acknowledgement_sha256:
            raise conflict()
        return header.acknowledgement_sha256

    async def _pins(self, attempt_id):
        return tuple(
            CanonicalPublicationPin.retained(row)
            for row in (
                await self.session.scalars(
                    select(SourcePublicationTarget)
                    .where(
                        SourcePublicationTarget.attempt_id == attempt_id,
                    )
                    .order_by(SourcePublicationTarget.catalog_id)
                    .limit(37)
                )
            ).all()
        )

    async def previous(self, admission, origin):
        """Lock and verify the last acknowledged live vector before reserving a successor."""
        return await self.current_origin(
            admission.tenant_id, admission.mapping_id, admission.destination[:2], origin
        )

    async def current_origin(self, tenant, mapping_id, destination, origin):
        """Compare current canonical state with immutable acknowledged publication evidence."""
        revision = origin.published_local_revision
        if not isinstance(revision, str) or not revision.startswith("cpv1:"):
            raise conflict()
        header = await self.session.scalar(
            select(SourcePublicationBaseline).where(
                SourcePublicationBaseline.tenant_id == tenant,
                SourcePublicationBaseline.mapping_id == mapping_id,
                SourcePublicationBaseline.object_id == origin.id,
                SourcePublicationBaseline.acknowledgement_sha256 == revision[5:],
            )
        )
        if header is None or not header.acknowledgement_json:
            raise conflict()
        acknowledgement = header.acknowledgement_json
        receipt = acknowledgement["native_receipt"]
        expected_version = (
            receipt["source_version_id"] if receipt["domain"] == "canon" else receipt["file_version_id"]
        )
        live = acknowledgement["live_vector"]
        if (
            not 2 <= len(live) <= 19
            or origin.published_native_version_id != expected_version
            or origin.published_sha256 != receipt["sha256"]
            or (header.workspace_id, header.project_id) != destination
            or {pin["catalog_id"] for pin in live if pin["role"] in {"source", "asset"}}
            != {header.source_id, header.asset_id}
        ):
            raise conflict()
        identifiers = sorted(pin["catalog_id"] for pin in live)
        locked = list(
            await self.session.scalars(
                select(CatalogEntry.id)
                .where(CatalogEntry.tenant_id == tenant, CatalogEntry.id.in_(identifiers))
                .order_by(CatalogEntry.id)
                .with_for_update()
            )
        )
        if locked != identifiers:
            raise conflict()
        for pin in live:
            current = await self.session.scalar(
                select(func.koinon_publication_current(header.attempt_id, pin["catalog_id"]))
            )
            if current != pin:
                raise conflict()
        return header

    async def pin_existing_targets(self, header, previous, *, members=()):
        """Copy only the acknowledged live predecessor; database checks INSERT provenance."""
        if (
            header.previous_attempt_id != previous.attempt_id
            or not previous.acknowledgement_json
            or header.descriptor_json is not None
            or header.producer_kind not in {"replace_document", "replace_dataset"}
        ):
            raise conflict()
        plans = {member.catalog_table_id: member for member in members}
        for pin in previous.acknowledgement_json["live_vector"]:
            retained = dict(pin)
            retained["disposition"] = plans[pin["catalog_id"]].action if pin["role"] == "member" else "retain"
            if pin["role"] == "new_index":
                retained["role"] = "old_index"
            self.session.add(SourcePublicationTarget(attempt_id=header.attempt_id, **retained))
        await self.session.flush()

    async def verify_before_publication(self, header) -> tuple[CanonicalPublicationPin, ...]:
        pins = await self._pins(header.attempt_id)
        bound = (
            2
            if header.producer_kind.endswith("document")
            else 19
            if header.producer_kind == "initial_dataset"
            else 36
        )
        if not pins or len(pins) > bound:
            raise conflict()
        current = list(
            (
                await self.session.scalars(
                    select(
                        func.koinon_publication_current(
                            SourcePublicationTarget.attempt_id,
                            SourcePublicationTarget.catalog_id,
                        )
                    )
                    .where(SourcePublicationTarget.attempt_id == header.attempt_id)
                    .order_by(SourcePublicationTarget.catalog_id)
                )
            ).all()
        )
        if current != [asdict(pin) for pin in pins]:
            raise conflict()
        return pins

    async def freeze(self, attempt, admission, item, *, members=()) -> SourcePublicationBinding:
        header = await self.session.scalar(
            select(SourcePublicationBaseline)
            .where(
                SourcePublicationBaseline.attempt_id == attempt.id,
                SourcePublicationBaseline.tenant_id == admission.tenant_id,
            )
            .with_for_update()
        )
        if (
            header is None
            or header.producer_kind not in {"initial_document", "initial_dataset"}
            or not item.native_workspace_id
            or attempt.intake_item_id != item.id
        ):
            raise conflict()
        pins = await self.verify_before_publication(header)
        values = tuple(pin for pin in admission.items if pin.object_id == attempt.object_id)
        if len(values) != 1:
            raise conflict()
        observed = values[0]
        plans = [member.model_dump(mode="json") for member in members]
        targets = []
        domain = "canon" if item.mode == "document" else "structured"

        def ref(path):
            return {"receipt_field": path}

        for pin in pins:
            binding = {
                "domain": domain,
                "native_workspace_id": ref("native_workspace_id"),
                "native_id": ref("native_source_id" if pin.role == "source" else "native_asset_id"),
                "native_version_id": None,
                "native_snapshot_id": None,
            }
            if domain == "canon":
                binding.update(
                    native_version_id=ref("source_version_id"), native_snapshot_id=ref("extraction_id")
                )
            elif pin.role == "new_index":
                binding.update(native_id=ref("native_file_id"), native_version_id=ref("native_file_id"))
            elif pin.role == "member":
                matching = [member for member in plans if member["catalog_table_id"] == pin.catalog_id]
                if len(matching) != 1:
                    raise conflict()
                ordinal = matching[0]["ordinal"]
                binding.update(
                    native_id=ref(f"tables.{ordinal}.table_id"),
                    native_version_id=ref("native_file_id"),
                    native_snapshot_id=ref(f"tables.{ordinal}.snapshot_id"),
                )
            targets.append(
                {
                    "pin": asdict(pin),
                    "writes": [{"action": "update", "fields": {"status": "ready"}}],
                    "binding": binding,
                }
            )
        identity = {
            key: getattr(header, key)
            for key in (
                "attempt_id",
                "tenant_id",
                "workspace_id",
                "project_id",
                "mapping_id",
                "object_id",
                "source_id",
                "asset_id",
                "producer_kind",
                "previous_attempt_id",
            )
        }
        identity.update(generation=attempt.generation, mapping_revision=attempt.mapping_revision)
        descriptor = {
            "schema": "koinon.source-publication-descriptor.v1",
            "identity": identity,
            "producer": {"intake_item_id": attempt.intake_item_id, "content_operation_id": None},
            "observation": {
                "run_id": admission.run_id,
                "work_id": observed.work_id,
                "observation_id": observed.observation_id,
            },
            "content": {
                "remote_version": attempt.remote_version,
                "sha256": attempt.sha256,
                "size_bytes": attempt.size_bytes,
            },
            "previous_acknowledgement_sha256": None,
            "native": {
                "domain": domain,
                "workspace_id": item.native_workspace_id,
                "operation_id": "upload:" + item.source_id if item.mode == "document" else item.id,
                "expected_heads": None,
            },
            "targets": targets,
            "members": plans,
        }
        if header.descriptor_json is None:
            header.descriptor_json = descriptor
            await self.session.flush()
            await self.session.refresh(header, attribute_names=["descriptor_sha256"])
        elif header.descriptor_json != descriptor:
            raise conflict()
        if not header.descriptor_sha256:
            raise conflict()
        return SourcePublicationBinding(attempt.id, header.descriptor_sha256)

    async def freeze_replacement(self, attempt, admission) -> SourcePublicationBinding:
        header = await self.session.scalar(
            select(SourcePublicationBaseline)
            .where(
                SourcePublicationBaseline.attempt_id == attempt.id,
                SourcePublicationBaseline.tenant_id == admission.tenant_id,
            )
            .with_for_update()
        )
        if (
            header is None
            or header.producer_kind not in {"replace_document", "replace_dataset"}
            or not attempt.content_operation_id
            or attempt.intake_item_id is not None
            or header.previous_attempt_id is None
        ):
            raise conflict()
        previous = await self.session.get(SourcePublicationBaseline, header.previous_attempt_id)
        operation = await self.session.get(CatalogEntry, attempt.content_operation_id)
        if (
            previous is None
            or not previous.acknowledgement_json
            or not previous.acknowledgement_sha256
            or operation is None
            or operation.tenant_id != admission.tenant_id
            or (
                previous.tenant_id,
                previous.mapping_id,
                previous.object_id,
                previous.source_id,
                previous.asset_id,
            )
            != (header.tenant_id, header.mapping_id, header.object_id, header.source_id, header.asset_id)
        ):
            raise conflict()
        producer = operation.metadata_json.get("_koinon_source_replacement")
        if not isinstance(producer, dict) or producer.get("attempt_id") != attempt.id:
            raise conflict()
        observed = tuple(pin for pin in admission.items if pin.object_id == attempt.object_id)
        if len(observed) != 1:
            raise conflict()
        observed = observed[0]
        pins = await self.verify_before_publication(header)
        metadata = dict(
            (
                await self.session.execute(
                    select(CatalogEntry.id, CatalogEntry.metadata_json).where(
                        CatalogEntry.tenant_id == admission.tenant_id,
                        CatalogEntry.id.in_([pin.catalog_id for pin in pins]),
                    )
                )
            ).all()
        )
        if len(metadata) != len(pins):
            raise conflict()
        domain = "canon" if header.producer_kind == "replace_document" else "structured"
        native = previous.acknowledgement_json["native_receipt"]
        members = producer["members"]
        targets = []

        def ref(path):
            return {"receipt_field": path}

        for pin in pins:
            binding = dict(
                domain=domain,
                native_workspace_id=ref("native_workspace_id"),
                native_id=ref("native_source_id" if pin.role == "source" else "native_asset_id"),
                native_version_id=None,
                native_snapshot_id=None,
            )
            fields: dict[str, object] = {"status": "ready"}
            if pin.role in {"source", "asset"}:
                fields["metadata"] = {
                    **metadata[pin.catalog_id],
                    "sha256": attempt.sha256,
                    "bytes": attempt.size_bytes,
                    "latest_content_version_id": attempt.content_operation_id,
                }
                if domain == "canon":
                    binding.update(
                        native_version_id=ref("source_version_id"), native_snapshot_id=ref("extraction_id")
                    )
            elif pin.role == "new_index":
                binding.update(native_id=ref("native_file_id"), native_version_id=ref("native_file_id"))
            elif pin.role == "old_index" or pin.disposition == "remove":
                binding = {
                    "domain": pin.native_domain,
                    **{
                        key: getattr(pin, key)
                        for key in (
                            "native_workspace_id",
                            "native_id",
                            "native_version_id",
                            "native_snapshot_id",
                        )
                    },
                }
                fields = {"status": "archived"}
            else:
                matching = [member for member in members if member["catalog_table_id"] == pin.catalog_id]
                if len(matching) != 1 or matching[0]["action"] == "remove":
                    raise conflict()
                member = matching[0]
                fields["metadata"] = {**metadata[pin.catalog_id], "snapshot_id": member["snapshot_id"]}
                binding.update(
                    native_id=ref(f"tables.{member['ordinal']}.table_id"),
                    native_version_id=ref("native_file_id"),
                    native_snapshot_id=ref(f"tables.{member['ordinal']}.snapshot_id"),
                )
            targets.append(
                {
                    "pin": asdict(pin),
                    "binding": binding,
                    "writes": [] if pin.role == "old_index" else [{"action": "update", "fields": fields}],
                }
            )
        identity = {
            key: getattr(header, key)
            for key in (
                "attempt_id",
                "tenant_id",
                "workspace_id",
                "project_id",
                "mapping_id",
                "object_id",
                "source_id",
                "asset_id",
                "producer_kind",
                "previous_attempt_id",
            )
        }
        identity.update(generation=attempt.generation, mapping_revision=attempt.mapping_revision)
        descriptor = {
            "schema": "koinon.source-publication-descriptor.v1",
            "identity": identity,
            "producer": {"intake_item_id": None, "content_operation_id": attempt.content_operation_id},
            "observation": {
                "run_id": admission.run_id,
                "work_id": observed.work_id,
                "observation_id": observed.observation_id,
            },
            "content": {
                "remote_version": attempt.remote_version,
                "sha256": attempt.sha256,
                "size_bytes": attempt.size_bytes,
            },
            "previous_acknowledgement_sha256": previous.acknowledgement_sha256,
            "native": {
                "domain": domain,
                "workspace_id": native["native_workspace_id"],
                "operation_id": attempt.content_operation_id,
                "expected_heads": {
                    "baseline_sha256": producer["baseline_sha256"],
                    "source_version_id": native["source_version_id"],
                    "extraction_id": native["extraction_id"],
                    "native_file_id": native["native_file_id"],
                    "tables": [
                        {key: table[key] for key in ("catalog_table_id", "table_id", "snapshot_id")}
                        for table in native["tables"]
                    ],
                },
            },
            "targets": targets,
            "members": members,
        }
        if header.descriptor_json is None:
            header.descriptor_json = descriptor
            await self.session.flush()
            await self.session.refresh(header, attribute_names=["descriptor_sha256"])
        elif header.descriptor_json != descriptor:
            raise conflict()
        if not header.descriptor_sha256:
            raise conflict()
        return SourcePublicationBinding(attempt.id, header.descriptor_sha256)

    async def pin_created_targets(
        self, attempt: SourceImportAttempt, admission: SourceIntakeAdmission, item: BulkItem
    ) -> tuple[CanonicalPublicationPin, ...]:
        if (
            attempt.tenant_id != admission.tenant_id
            or attempt.mapping_id != admission.mapping_id
            or attempt.mapping_revision != admission.mapping_revision
            or attempt.intake_item_id != item.id
            or (attempt.source_id, attempt.asset_id) != (item.source_id, item.asset_id)
            or item.mode not in {"document", "dataset"}
            or self.session.get_transaction() is None
        ):
            raise conflict()
        if await self.session.get(SourcePublicationBaseline, attempt.id) is not None:
            # Reservation replay reads its original batch; it cannot manufacture replacement pins.
            raise conflict()
        header = SourcePublicationBaseline(
            attempt_id=attempt.id,
            tenant_id=attempt.tenant_id,
            workspace_id=admission.destination[0],
            project_id=admission.destination[1],
            mapping_id=attempt.mapping_id,
            object_id=attempt.object_id,
            source_id=attempt.source_id,
            asset_id=attempt.asset_id,
            producer_kind="initial_" + item.mode,
        )
        self.session.add(header)
        await self.session.flush()
        targets = {
            item.source_id: ("source", admission.destination[2], "source"),
            item.asset_id: ("asset", item.source_id, item.mode),
        }
        if item.mode == "dataset":
            reservation = DatasetReservation.stored(item.reservation_json)
            targets[reservation.catalog_file_version_id] = ("new_index", item.asset_id, "index_version")
        return await self._created(header, targets)

    async def pin_members(self, attempt: SourceImportAttempt, identifiers: tuple[str, ...]) -> None:
        header = await self.session.scalar(
            select(SourcePublicationBaseline)
            .where(
                SourcePublicationBaseline.attempt_id == attempt.id,
                SourcePublicationBaseline.tenant_id == attempt.tenant_id,
            )
            .with_for_update()
        )
        if header is None or header.producer_kind != "initial_dataset" or header.descriptor_json is not None:
            raise conflict()
        reserved = tuple(
            (
                await self.session.scalars(
                    select(BulkTableReservation.catalog_table_id)
                    .where(
                        BulkTableReservation.item_id == attempt.intake_item_id,
                    )
                    .order_by(BulkTableReservation.ordinal)
                    .limit(17)
                )
            ).all()
        )
        if (
            not 1 <= len(reserved) <= 16
            or reserved != identifiers
            or len(set(identifiers)) != len(identifiers)
        ):
            raise conflict()
        retained = list(
            (
                await self.session.scalars(
                    select(SourcePublicationTarget)
                    .where(
                        SourcePublicationTarget.attempt_id == attempt.id,
                        SourcePublicationTarget.role == "member",
                    )
                    .order_by(SourcePublicationTarget.catalog_id)
                )
            ).all()
        )
        if retained:
            if {pin.catalog_id for pin in retained} != set(identifiers):
                raise conflict()
            return
        await self._created(
            header, {identifier: ("member", header.asset_id, "table") for identifier in identifiers}
        )

    async def _created(self, header, targets) -> tuple[CanonicalPublicationPin, ...]:
        domain = "canon" if header.producer_kind.endswith("document") else "structured"
        rows = (
            await self.session.execute(
                select(CatalogEntry, DomainBinding)
                .outerjoin(
                    DomainBinding,
                    (DomainBinding.tenant_id == CatalogEntry.tenant_id)
                    & (DomainBinding.catalog_id == CatalogEntry.id)
                    & (DomainBinding.domain == domain),
                )
                .where(CatalogEntry.tenant_id == header.tenant_id, CatalogEntry.id.in_(sorted(targets)))
                .order_by(CatalogEntry.id)
                .execution_options(populate_existing=True)
            )
        ).all()
        if len(rows) != len(targets):
            raise conflict()
        result = []
        for row, binding in rows:
            role, parent, kind = targets[row.id]
            if (row.workspace_id, row.project_id, row.parent_id, row.kind, row.status) != (
                header.workspace_id,
                header.project_id,
                parent,
                kind,
                "pending",
            ) or binding is not None:
                raise conflict()
            pin = CanonicalPublicationPin(
                catalog_id=row.id,
                tenant_id=header.tenant_id,
                workspace_id=header.workspace_id,
                project_id=header.project_id,
                role=role,
                disposition="add",
                parent_id=row.parent_id,
                kind=row.kind,
                mutation_revision=row.mutation_revision,
                status=row.status,
                native_domain=None,
                native_workspace_id=None,
                native_id=None,
                native_version_id=None,
                native_snapshot_id=None,
            )
            self.session.add(SourcePublicationTarget(attempt_id=header.attempt_id, **asdict(pin)))
            result.append(pin)
        # PostgreSQL checks actual same-transaction INSERT evidence and exact reservations independently.
        await self.session.flush()
        return tuple(result)
