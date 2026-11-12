# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Source identity is bound before initial intake becomes visible."""

import asyncio
import hashlib
import json
from dataclasses import asdict
from datetime import UTC, datetime

from pyfly.container import repository
from pyfly.data.relational.sqlalchemy import Repository
from pyfly.kernel import ConflictException
from sqlalchemy import cast, or_, select, update
from sqlalchemy.dialects.postgresql import JSONB

from koinon.integrations.content_sources.entities import PersonalSourceConnection
from koinon.integrations.content_sources.import_entities import SourceImportAttempt
from koinon.integrations.content_sources.mapping_entities import SourceMapping, SourceObject
from koinon.integrations.content_sources.publication_baselines import SourcePublicationBaselines
from koinon.integrations.content_sources.publication_entities import SourcePublicationBaseline
from koinon.integrations.content_sources.read_authority import source_authority
from koinon.integrations.content_sources.sync_entities import (
    SourceFolderBinding,
    SourceImportedAsset,
    SourceImportedVersion,
    SourceMappingPolicy,
    SourceSyncObservation,
    SourceSyncRun,
    SourceSyncState,
    SourceSyncWork,
)
from koinon.knowledge.bulk.entities import BulkBatch, BulkItem
from koinon.knowledge.bulk.ports import (
    NativeCommit,
    SourceIntakeAdmission,
    SourceIntakeGuard,
    SourceIntakeItem,
    SourcePublicationFence,
)
from koinon.knowledge.bulk.queue import BulkLease


def _denied():
    return ConflictException("The source intake authority changed", code="SOURCE_PUBLICATION_DENIED")


def retained_admission(value: object) -> SourceIntakeAdmission:
    try:
        if not isinstance(value, dict):
            raise ValueError
        data = dict(value)
        data["items"] = tuple(SourceIntakeItem(**item) for item in data["items"])
        data["destination"] = tuple(data["destination"])
        admission = SourceIntakeAdmission(**data)
        if (
            not 1 <= len(admission.items) <= 100
            or len(admission.destination) != 3
            or len({item.object_id for item in admission.items}) != len(admission.items)
            or any(
                type(number) is not int or not 1 <= number <= 2147483647
                for number in (
                    admission.mapping_revision,
                    admission.connection_revision,
                    *(item.generation for item in admission.items),
                    *(item.page_sequence for item in admission.items),
                )
            )
            or any(
                not isinstance(identifier, str) or not identifier or len(identifier) > 2048
                for identifier in (
                    admission.tenant_id,
                    admission.owner,
                    admission.mapping_id,
                    admission.run_id,
                    *admission.destination,
                    *(part for item in admission.items for part in (item.object_id, item.remote_version)),
                    *(part for item in admission.items for part in (item.observation_id, item.work_id)),
                )
            )
            or any(
                type(item.item_sequence) is not int or not 0 <= item.item_sequence < 100
                for item in admission.items
            )
            or any(
                len(item.event_sha256) != 64 or any(c not in "0123456789abcdef" for c in item.event_sha256)
                for item in admission.items
            )
        ):
            raise ValueError
        return admission
    except (TypeError, KeyError, ValueError):
        raise _denied() from None


@repository(name="content_sources.intake")
class SourceSyncIntake(Repository[SourceImportAttempt, str], SourceIntakeGuard, SourcePublicationFence):
    async def _fence(self, admission: SourceIntakeAdmission, *, committed: bool = False):
        admission = retained_admission(asdict(admission))
        session = self._require_session()
        connection = await session.scalar(
            select(PersonalSourceConnection)
            .join(SourceMapping, SourceMapping.connection_id == PersonalSourceConnection.id)
            .where(
                SourceMapping.id == admission.mapping_id,
                SourceMapping.tenant_id == admission.tenant_id,
                SourceMapping.owner == admission.owner,
                PersonalSourceConnection.owner == admission.owner,
                PersonalSourceConnection.tenant_id == admission.tenant_id,
            )
            .with_for_update(of=PersonalSourceConnection)
            .execution_options(populate_existing=True)
        )
        mapping = await session.scalar(
            select(SourceMapping)
            .where(
                SourceMapping.id == admission.mapping_id,
                SourceMapping.tenant_id == admission.tenant_id,
                SourceMapping.owner == admission.owner,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if connection is None or mapping is None:
            raise _denied()
        objects = list(
            (
                await session.scalars(
                    select(SourceObject)
                    .where(
                        SourceObject.tenant_id == admission.tenant_id,
                        SourceObject.mapping_id == admission.mapping_id,
                        SourceObject.id.in_([item.object_id for item in admission.items]),
                    )
                    .order_by(SourceObject.id)
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
            ).all()
        )
        if len(objects) != len(admission.items):
            raise _denied()
        run = await session.scalar(
            select(SourceSyncRun)
            .where(
                SourceSyncRun.id == admission.run_id,
                SourceSyncRun.tenant_id == admission.tenant_id,
                SourceSyncRun.mapping_id == admission.mapping_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if (
            run is None
            or run.mapping_revision != admission.mapping_revision
            or run.connection_revision != admission.connection_revision
        ):
            raise _denied()
        if not committed:
            current = await session.get(SourceSyncState, mapping.id)
            policy = await session.get(SourceMappingPolicy, run.policy_id)
            if (
                mapping.status not in {"active", "paused"}
                or mapping.revision != admission.mapping_revision
                or connection.status != "connected"
                or connection.secret_ciphertext is None
                or connection.refresh_operation is not None
                or connection.revision != admission.connection_revision
                or current is None
                or current.accepted_policy_id != run.policy_id
                or policy is None
                or policy.accepted_at is None
                or policy.authority_sha256 != source_authority(connection)[1]
                or run.status not in {"queued", "running", "reconciling"}
                or run.cancel_requested_at is not None
            ):
                raise _denied()
        expected = {item.object_id: item for item in admission.items}
        for item in objects:
            pin = expected[item.id]
            observation = await session.get(SourceSyncObservation, pin.observation_id)
            if (
                observation is None
                or (
                    observation.tenant_id,
                    observation.mapping_id,
                    observation.run_id,
                    observation.object_id,
                    observation.generation,
                    observation.remote_version,
                    observation.work_id,
                    observation.page_sequence,
                    observation.item_sequence,
                    observation.event_sha256,
                )
                != (
                    admission.tenant_id,
                    admission.mapping_id,
                    admission.run_id,
                    pin.object_id,
                    pin.generation,
                    pin.remote_version,
                    pin.work_id,
                    pin.page_sequence,
                    pin.item_sequence,
                    pin.event_sha256,
                )
                or observation.page_sequence > run.page_sequence
            ):
                raise _denied()
            if not committed:
                unresolved = await session.scalar(
                    select(SourceImportAttempt.id)
                    .join(
                        BulkItem,
                        BulkItem.id == SourceImportAttempt.intake_item_id,
                    )
                    .where(
                        SourceImportAttempt.tenant_id == admission.tenant_id,
                        SourceImportAttempt.mapping_id == admission.mapping_id,
                        SourceImportAttempt.object_id == pin.object_id,
                        SourceImportAttempt.generation != pin.generation,
                        SourceImportAttempt.receipt_json.is_(None),
                        BulkItem.status.in_(("running", "reconciling", "queued")),
                    )
                    .limit(1)
                )
                if unresolved is not None:
                    raise _denied()
                if (
                    item.mapping_revision != admission.mapping_revision
                    or item.generation != pin.generation
                    or item.remote_version != pin.remote_version
                    or item.state not in {"pending", "imported"}
                ):
                    raise _denied()
                later = await session.scalar(
                    select(SourceSyncObservation.id)
                    .where(
                        SourceSyncObservation.run_id == run.id,
                        SourceSyncObservation.object_id == pin.object_id,
                        or_(
                            SourceSyncObservation.page_sequence > pin.page_sequence,
                            (SourceSyncObservation.page_sequence == pin.page_sequence)
                            & (SourceSyncObservation.item_sequence > pin.item_sequence),
                        ),
                    )
                    .limit(1)
                )
                if later is not None:
                    raise _denied()
        if admission.destination[:2] != (mapping.workspace_id, mapping.project_id):
            raise _denied()
        if admission.destination[2] != mapping.parent_id:
            binding = await session.scalar(
                select(SourceFolderBinding).where(
                    SourceFolderBinding.tenant_id == admission.tenant_id,
                    SourceFolderBinding.mapping_id == mapping.id,
                    SourceFolderBinding.local_folder_id == admission.destination[2],
                )
            )
            if binding is None:
                raise _denied()
        return mapping, {item.id: item for item in objects}, run

    async def admit(self, admission: SourceIntakeAdmission) -> None:
        mapping, _, _ = await self._fence(admission)
        session = self._require_session()
        state = await session.get(SourceSyncState, mapping.id)
        if mapping.status != "active" or state is None or not state.enabled:
            raise _denied()
        session.info.setdefault("source_intake_admissions", {})[id(admission)] = (
            admission,
            asyncio.current_task(),
            session.get_transaction(),
        )

    async def bind(self, admission: SourceIntakeAdmission, ordinal: int, item: BulkItem) -> None:
        session = self._require_session()
        observed = session.info.get("source_intake_admissions", {}).get(id(admission))
        if (
            observed is None
            or observed[0] is not admission
            or observed[1] is not asyncio.current_task()
            or observed[2] is not session.get_transaction()
            or observed[2] is None
            or not 0 <= ordinal < len(admission.items)
            or item.ordinal != ordinal
        ):
            raise _denied()
        pin = admission.items[ordinal]
        mapping = await session.get(SourceMapping, admission.mapping_id)
        origin = await session.get(SourceObject, pin.object_id)
        work = await session.scalar(
            select(SourceSyncWork).where(
                SourceSyncWork.tenant_id == admission.tenant_id,
                SourceSyncWork.mapping_id == admission.mapping_id,
                SourceSyncWork.object_id == pin.object_id,
                SourceSyncWork.generation == pin.generation,
                SourceSyncWork.id == pin.work_id,
            )
        )
        if mapping is None or origin is None or work is None or work.attempt_id is not None:
            raise _denied()
        identifier = hashlib.sha256(
            json.dumps([admission.tenant_id, pin.object_id, pin.generation], separators=(",", ":")).encode()
        ).hexdigest()
        attempt = SourceImportAttempt(
            id=identifier,
            tenant_id=admission.tenant_id,
            mapping_id=mapping.id,
            mapping_revision=admission.mapping_revision,
            object_id=origin.id,
            generation=pin.generation,
            intake_item_id=item.id,
            provider=mapping.provider,
            external_subject=mapping.external_subject,
            external_tenant=mapping.external_tenant,
            drive_id=mapping.drive_id,
            remote_item_id=origin.item_id,
            remote_version=pin.remote_version,
            source_id=item.source_id,
            asset_id=item.asset_id,
            sha256=item.sha256,
            size_bytes=item.size_bytes,
        )
        session.add(attempt)
        await session.flush()
        session.add(
            SourceImportedAsset(
                asset_id=item.asset_id,
                tenant_id=admission.tenant_id,
                source_id=item.source_id,
                initial_attempt_id=attempt.id,
            )
        )
        work.attempt_id, work.status = attempt.id, "processing"
        await session.flush()
        await SourcePublicationBaselines(session).pin_created_targets(attempt, admission, item)

    async def _resolve(self, lease: BulkLease, *, committed: bool = False):
        session = self._require_session()
        attempt = await session.scalar(
            select(SourceImportAttempt).where(
                SourceImportAttempt.tenant_id == lease.tenant_id,
                SourceImportAttempt.intake_item_id == lease.item_id,
            )
        )
        marker = await session.get(SourceImportedAsset, lease.asset_id)
        batch = (
            await session.execute(
                select(
                    BulkBatch.tenant_id,
                    BulkBatch.subject,
                    BulkBatch.request_json["_source_admission"].label("source_admission"),
                ).where(BulkBatch.id == lease.batch_id)
            )
        ).one_or_none()
        payload = batch.source_admission if batch else None
        if attempt is None and marker is None and payload is None:
            return None
        admission = retained_admission(payload)
        if (
            attempt is None
            or marker is None
            or batch is None
            or batch.tenant_id != lease.tenant_id
            or batch.subject != lease.subject
            or admission.tenant_id != lease.tenant_id
            or admission.owner != lease.subject
            or admission.mapping_id != attempt.mapping_id
            or (attempt.source_id, attempt.asset_id, attempt.sha256, attempt.size_bytes)
            != (lease.source_id, lease.asset_id, lease.sha256, lease.size_bytes)
            or marker.initial_attempt_id != attempt.id
        ):
            raise _denied()
        item = await session.get(BulkItem, lease.item_id)
        if item is None or not 0 <= item.ordinal < len(admission.items):
            raise _denied()
        pin = admission.items[item.ordinal]
        if (pin.object_id, pin.generation, pin.remote_version) != (
            attempt.object_id,
            attempt.generation,
            attempt.remote_version,
        ):
            raise _denied()
        mapping, objects, run = await self._fence(admission, committed=committed)
        work = await session.scalar(
            select(SourceSyncWork)
            .where(
                SourceSyncWork.id == pin.work_id,
                SourceSyncWork.tenant_id == admission.tenant_id,
                SourceSyncWork.mapping_id == mapping.id,
                SourceSyncWork.object_id == pin.object_id,
                SourceSyncWork.generation == pin.generation,
                SourceSyncWork.attempt_id == attempt.id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        attempt = await session.scalar(
            select(SourceImportAttempt)
            .where(SourceImportAttempt.id == attempt.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if attempt is None or work is None:
            raise _denied()
        return attempt, objects[pin.object_id], run, mapping, work

    async def check(self, lease: BulkLease) -> None:
        await self._resolve(lease)

    async def reconcile(self, lease: BulkLease) -> None:
        await self._receipt_identity(lease)

    async def committed(self, lease: BulkLease, receipt: NativeCommit) -> None:
        await self._committed(lease, receipt, publish=True)

    async def settle(self, lease: BulkLease, receipt: NativeCommit) -> None:
        resolved = await self._receipt_identity(lease)
        if resolved is None:
            return
        attempt, work_id = resolved
        session = self._require_session()
        encoded = json.loads(json.dumps(asdict(receipt)))
        baseline = (
            await session.execute(
                select(
                    SourcePublicationBaseline.descriptor_sha256,
                    SourcePublicationBaseline.acknowledgement_json.is_not(None).label("acknowledged"),
                    (SourcePublicationBaseline.acknowledgement_json["native_receipt"] == encoded).label(
                        "ack_same"
                    ),
                ).where(
                    SourcePublicationBaseline.attempt_id == attempt.id,
                    SourcePublicationBaseline.tenant_id == lease.tenant_id,
                )
            )
        ).one_or_none()
        version = receipt.source_version_id if receipt.domain == "canon" else receipt.file_version_id
        if (
            baseline is None
            or not baseline.descriptor_sha256
            or receipt.source_attempt_id != attempt.id
            or receipt.source_publication_sha256 != baseline.descriptor_sha256
            or baseline.acknowledged and not baseline.ack_same
            or receipt.sha256 != lease.sha256
            or receipt.size_bytes != lease.size_bytes
            or not version
            or not receipt.native_workspace_id
            or not receipt.native_source_id
            or not receipt.native_asset_id
        ):
            raise _denied()
        stored = cast(SourceImportAttempt.receipt_json, JSONB)
        state = (
            await session.execute(
                select(
                    SourceImportAttempt.receipt_json.is_(None).label("missing"),
                    (stored == encoded).label("same"),
                ).where(SourceImportAttempt.id == attempt.id)
            )
        ).one()
        if not state.missing and not state.same:
            raise _denied()
        if state.missing:
            await session.execute(
                update(SourceImportAttempt)
                .where(
                    SourceImportAttempt.id == attempt.id,
                )
                .values(receipt_json=encoded, committed_at=datetime.now(UTC))
            )
        if not baseline.acknowledged:
            await session.execute(
                update(SourceSyncWork)
                .where(SourceSyncWork.id == work_id)
                .values(
                    status="conflict",
                    error_code="SOURCE_PUBLICATION_NOT_ACKNOWLEDGED",
                )
            )

    async def _receipt_identity(self, lease: BulkLease):
        """Correlate retained coordinates without loading source content or current credentials."""
        session = self._require_session()
        attempt = (
            await session.execute(
                select(
                    SourceImportAttempt.id,
                    SourceImportAttempt.mapping_id,
                    SourceImportAttempt.mapping_revision,
                    SourceImportAttempt.object_id,
                    SourceImportAttempt.generation,
                    SourceImportAttempt.remote_version,
                    SourceImportAttempt.source_id,
                    SourceImportAttempt.asset_id,
                    SourceImportAttempt.sha256,
                    SourceImportAttempt.size_bytes,
                ).where(
                    SourceImportAttempt.tenant_id == lease.tenant_id,
                    SourceImportAttempt.intake_item_id == lease.item_id,
                )
            )
        ).one_or_none()
        marker = await session.scalar(
            select(SourceImportedAsset.initial_attempt_id).where(
                SourceImportedAsset.asset_id == lease.asset_id,
                SourceImportedAsset.source_id == lease.source_id,
                SourceImportedAsset.tenant_id == lease.tenant_id,
            )
        )
        batch = (
            await session.execute(
                select(
                    BulkBatch.tenant_id,
                    BulkBatch.subject,
                    BulkBatch.request_json["_source_admission"].label("admission"),
                ).where(BulkBatch.id == lease.batch_id)
            )
        ).one_or_none()
        payload = batch.admission if batch else None
        if attempt is None and marker is None and payload is None:
            return None
        admission = retained_admission(payload)
        if (
            attempt is None
            or marker != attempt.id
            or batch is None
            or (batch.tenant_id, batch.subject) != (lease.tenant_id, lease.subject)
            or (admission.tenant_id, admission.owner) != (lease.tenant_id, lease.subject)
            or (admission.mapping_id, admission.mapping_revision)
            != (attempt.mapping_id, attempt.mapping_revision)
            or (attempt.source_id, attempt.asset_id, attempt.sha256, attempt.size_bytes)
            != (lease.source_id, lease.asset_id, lease.sha256, lease.size_bytes)
        ):
            raise _denied()
        ordinal = await session.scalar(
            select(BulkItem.ordinal).where(
                BulkItem.id == lease.item_id,
                BulkItem.batch_id == lease.batch_id,
            )
        )
        if ordinal is None or not 0 <= ordinal < len(admission.items):
            raise _denied()
        pin = admission.items[ordinal]
        if (pin.object_id, pin.generation, pin.remote_version) != (
            attempt.object_id,
            attempt.generation,
            attempt.remote_version,
        ):
            raise _denied()
        connection_id = await session.scalar(
            select(PersonalSourceConnection.id)
            .join(
                SourceMapping,
                SourceMapping.connection_id == PersonalSourceConnection.id,
            )
            .where(
                SourceMapping.id == admission.mapping_id,
                SourceMapping.tenant_id == admission.tenant_id,
                SourceMapping.owner == admission.owner,
                PersonalSourceConnection.owner == admission.owner,
                PersonalSourceConnection.tenant_id == admission.tenant_id,
            )
            .with_for_update(of=PersonalSourceConnection)
        )
        mapping = (
            await session.execute(
                select(
                    SourceMapping.id,
                    SourceMapping.workspace_id,
                    SourceMapping.project_id,
                    SourceMapping.parent_id,
                )
                .where(
                    SourceMapping.id == admission.mapping_id,
                    SourceMapping.tenant_id == admission.tenant_id,
                    SourceMapping.owner == admission.owner,
                )
                .with_for_update()
            )
        ).one_or_none()
        if connection_id is None or mapping is None:
            raise _denied()
        objects = list(
            (
                await session.scalars(
                    select(SourceObject.id)
                    .where(
                        SourceObject.tenant_id == admission.tenant_id,
                        SourceObject.mapping_id == admission.mapping_id,
                        SourceObject.id.in_([item.object_id for item in admission.items]),
                    )
                    .order_by(SourceObject.id)
                    .with_for_update()
                )
            ).all()
        )
        run = (
            await session.execute(
                select(
                    SourceSyncRun.mapping_revision,
                    SourceSyncRun.connection_revision,
                    SourceSyncRun.page_sequence,
                )
                .where(
                    SourceSyncRun.id == admission.run_id,
                    SourceSyncRun.tenant_id == admission.tenant_id,
                    SourceSyncRun.mapping_id == admission.mapping_id,
                )
                .with_for_update()
            )
        ).one_or_none()
        if (
            len(objects) != len(admission.items)
            or run is None
            or run.mapping_revision != admission.mapping_revision
            or run.connection_revision != admission.connection_revision
        ):
            raise _denied()
        for retained in admission.items:
            observation = await session.scalar(
                select(SourceSyncObservation.id).where(
                    SourceSyncObservation.id == retained.observation_id,
                    SourceSyncObservation.tenant_id == admission.tenant_id,
                    SourceSyncObservation.mapping_id == admission.mapping_id,
                    SourceSyncObservation.run_id == admission.run_id,
                    SourceSyncObservation.object_id == retained.object_id,
                    SourceSyncObservation.generation == retained.generation,
                    SourceSyncObservation.remote_version == retained.remote_version,
                    SourceSyncObservation.work_id == retained.work_id,
                    SourceSyncObservation.page_sequence == retained.page_sequence,
                    SourceSyncObservation.item_sequence == retained.item_sequence,
                    SourceSyncObservation.event_sha256 == retained.event_sha256,
                    SourceSyncObservation.page_sequence <= run.page_sequence,
                )
            )
            if observation is None:
                raise _denied()
        if admission.destination[:2] != (mapping.workspace_id, mapping.project_id):
            raise _denied()
        if (
            admission.destination[2] != mapping.parent_id
            and await session.scalar(
                select(
                    SourceFolderBinding.local_folder_id,
                ).where(
                    SourceFolderBinding.tenant_id == admission.tenant_id,
                    SourceFolderBinding.mapping_id == mapping.id,
                    SourceFolderBinding.local_folder_id == admission.destination[2],
                )
            )
            is None
        ):
            raise _denied()
        work_id = await session.scalar(
            select(SourceSyncWork.id)
            .where(
                SourceSyncWork.id == pin.work_id,
                SourceSyncWork.tenant_id == admission.tenant_id,
                SourceSyncWork.mapping_id == mapping.id,
                SourceSyncWork.object_id == pin.object_id,
                SourceSyncWork.generation == pin.generation,
                SourceSyncWork.attempt_id == attempt.id,
            )
            .with_for_update()
        )
        locked_attempt = await session.scalar(
            select(SourceImportAttempt.id)
            .where(
                SourceImportAttempt.id == attempt.id,
            )
            .with_for_update()
        )
        if work_id is None or locked_attempt is None:
            raise _denied()
        return attempt, work_id

    async def _committed(self, lease: BulkLease, receipt: NativeCommit, *, publish: bool) -> None:
        resolved = await self._resolve(lease, committed=True)
        if resolved is None:
            return
        await self._record_receipt(resolved, receipt, publish=publish)

    async def resolve_replacement(self, admission, execution, *, committed=False):
        mapping, objects, run = await self._fence(admission, committed=committed)
        session = self._require_session()
        if len(admission.items) != 1:
            raise _denied()
        pin = admission.items[0]
        attempt = await session.get(SourceImportAttempt, execution.attempt_id)
        work = await session.get(SourceSyncWork, pin.work_id)
        if (
            attempt is None
            or work is None
            or attempt.intake_item_id is not None
            or attempt.content_operation_id != execution.content_operation_id
            or (
                attempt.tenant_id,
                attempt.mapping_id,
                attempt.mapping_revision,
                attempt.object_id,
                attempt.generation,
                attempt.remote_version,
            )
            != (
                admission.tenant_id,
                admission.mapping_id,
                admission.mapping_revision,
                pin.object_id,
                pin.generation,
                pin.remote_version,
            )
            or (work.tenant_id, work.mapping_id, work.object_id, work.generation, work.attempt_id)
            != (admission.tenant_id, admission.mapping_id, pin.object_id, pin.generation, attempt.id)
        ):
            raise _denied()
        return attempt, objects[pin.object_id], run, mapping, work

    async def committed_replacement(self, admission, execution, receipt, *, publish=True):
        resolved = await self.resolve_replacement(admission, execution, committed=True)
        await self._record_receipt(resolved, receipt, publish=publish)

    async def _record_receipt(self, resolved, receipt, *, publish):
        attempt, origin, run, mapping, work = resolved
        session = self._require_session()
        encoded = json.loads(json.dumps(asdict(receipt)))
        retained_receipt = (
            {**encoded, "operation_id": attempt.content_operation_id}
            if attempt.content_operation_id is not None
            else encoded
        )
        # Structured reader identities keep the canonical index ID; native_file_id is separate evidence.
        version = receipt.source_version_id if receipt.domain == "canon" else receipt.file_version_id
        if (
            not version
            or receipt.sha256 != attempt.sha256
            or receipt.size_bytes != attempt.size_bytes
            or not receipt.native_asset_id
            or not receipt.native_workspace_id
            or not receipt.native_source_id
        ):
            raise _denied()
        if attempt.receipt_json is not None:
            if attempt.receipt_json != retained_receipt:
                raise _denied()
        else:
            attempt.receipt_json, attempt.committed_at = retained_receipt, datetime.now(UTC)
            await session.flush()
        if not publish:
            # A native receipt records completed storage work; it grants no published read authority.
            baseline = await session.get(SourcePublicationBaseline, attempt.id)
            if baseline is None or baseline.acknowledgement_json is None:
                work.status, work.error_code = "conflict", "SOURCE_PUBLICATION_NOT_ACKNOWLEDGED"
                await session.flush()
            return
        imported = await session.get(SourceImportedVersion, attempt.id)
        if imported is None:
            session.add(
                SourceImportedVersion(
                    attempt_id=attempt.id,
                    tenant_id=attempt.tenant_id,
                    source_id=attempt.source_id,
                    asset_id=attempt.asset_id,
                    domain=receipt.domain,
                    native_workspace_id=receipt.native_workspace_id,
                    native_source_id=receipt.native_source_id,
                    native_asset_id=receipt.native_asset_id,
                    native_version_id=version,
                    extraction_id=receipt.extraction_id,
                )
            )
        elif (
            imported.tenant_id,
            imported.source_id,
            imported.asset_id,
            imported.domain,
            imported.native_workspace_id,
            imported.native_source_id,
            imported.native_asset_id,
            imported.native_version_id,
            imported.extraction_id,
        ) != (
            attempt.tenant_id,
            attempt.source_id,
            attempt.asset_id,
            receipt.domain,
            receipt.native_workspace_id,
            receipt.native_source_id,
            receipt.native_asset_id,
            version,
            receipt.extraction_id,
        ):
            raise _denied()
        if (
            publish
            and run.cancel_requested_at is None
            and run.status in {"running", "reconciling"}
            and mapping.status in {"active", "paused"}
            and mapping.revision == attempt.mapping_revision
            and origin.generation == attempt.generation
            and origin.mapping_revision == attempt.mapping_revision
            and origin.remote_version == attempt.remote_version
            and origin.state in {"pending", "imported"}
        ):
            baseline = await session.get(SourcePublicationBaseline, attempt.id)
            if (
                baseline is None
                or baseline.acknowledgement_json is None
                or not baseline.acknowledgement_sha256
                or baseline.acknowledgement_json.get("native_receipt") != encoded
                or baseline.descriptor_sha256 != receipt.source_publication_sha256
                or attempt.id != receipt.source_attempt_id
            ):
                raise _denied()
            origin.state = "imported"
            origin.published_native_version_id, origin.published_sha256 = version, receipt.sha256
            origin.published_local_revision = "cpv1:" + baseline.acknowledgement_sha256
            origin.updated_at = datetime.now(UTC)
        work.status, work.error_code = "imported", None
        await session.flush()
