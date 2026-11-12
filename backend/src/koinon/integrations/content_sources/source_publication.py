# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""One-use canonical writes confined to an exact source publication transaction."""

import asyncio
import json
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass, field, replace
from datetime import UTC, datetime
from types import SimpleNamespace

from pyfly.container import Provider, service
from pyfly.kernel import ConflictException
from sqlalchemy import cast, func, literal, select
from sqlalchemy.dialects.postgresql import JSONB, JSONPATH
from sqlalchemy.orm import aliased

from koinon.catalog.entities import CatalogEntry
from koinon.integrations.content_sources.dtos import Account, RemoteItem, SourceScope
from koinon.integrations.content_sources.import_entities import SourceImportAttempt
from koinon.integrations.content_sources.lifecycle import _no_remote_unit
from koinon.integrations.content_sources.mapping_ancestry import FolderAncestry
from koinon.integrations.content_sources.mapping_dtos import MappingReviewInput
from koinon.integrations.content_sources.mapping_preview import (
    available_extensions,
    import_choice,
    source_name_key,
)
from koinon.integrations.content_sources.mapping_service import SourceMappings
from koinon.integrations.content_sources.publication_baselines import SourcePublicationBaselines
from koinon.integrations.content_sources.publication_entities import (
    SourcePublicationBaseline,
    SourcePublicationTarget,
)
from koinon.integrations.content_sources.reader_access import _OperationToken
from koinon.integrations.content_sources.sync_entities import (
    SourceFolderBinding,
    SourceFolderPublication,
    SourceImportedVersion,
    SourceMappingPolicy,
    SourceSyncObservation,
    SourceSyncRun,
    SourceSyncWork,
)
from koinon.integrations.content_sources.sync_intake import SourceSyncIntake, retained_admission
from koinon.integrations.content_sources.sync_runs import (
    SourceReplacementAcknowledgementExecution,
    SourceReplacementExecution,
    SourceRunLease,
    SourceRunRepository,
)
from koinon.jobs.entities import Job
from koinon.knowledge.bulk.authority import BulkAuthority
from koinon.knowledge.bulk.dataset_dtos import DatasetReservation
from koinon.knowledge.bulk.entities import BulkBatch, BulkItem, BulkTableReservation
from koinon.knowledge.bulk.ports import (
    NativeCommit,
    SourceIntakeAdmission,
    SourceIntakeWriter,
    SourcePublicationBinding,
)
from koinon.knowledge.bulk.queue import BulkLease
from koinon.knowledge.bulk.repositories import BulkRepository
from koinon.knowledge.lineage.service import NativeStructuredLineage
from koinon.security.authority import primary_authority

_REGISTRY = "source_publication_permits"
_FENCES = "source_publication_fences"
_REPLACEMENT_EXECUTIONS = (SourceReplacementExecution, SourceReplacementAcknowledgementExecution)


def _denied():
    return ConflictException("Source publication authority changed", code="SOURCE_PUBLICATION_DENIED")


def _changes(value: dict) -> str:
    try:
        encoded = json.dumps(
            value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")
        )
        if not isinstance(value, dict) or len(encoded.encode()) > 262144:
            raise ValueError
        return encoded
    except (TypeError, ValueError):
        raise _denied() from None


def observed_item(event: dict) -> RemoteItem:
    try:
        data = dict(event["item"])
        data["scope"] = SourceScope(Account(**data["scope"]["account"]), data["scope"]["drive_id"])
        data["parents"] = tuple(data["parents"])
        return RemoteItem(**data)
    except (ValueError, TypeError, KeyError):
        raise _denied() from None


@dataclass(frozen=True, slots=True)
class SourceWriteOperation:
    action: str
    target: str
    parent: str | None
    changes: dict = field(repr=False, compare=False)
    expected_revision: int | None = None
    changes_json: str = field(init=False, repr=False)

    def __post_init__(self):
        if self.action not in {"create", "update", "merge_latest", "move"} or not self.target:
            raise _denied()
        if self.action != "create" and (
            type(self.expected_revision) is not int or self.expected_revision < 1
        ):
            raise _denied()
        if self.action == "create" and self.expected_revision is not None:
            raise _denied()
        object.__setattr__(self, "changes_json", _changes(self.changes))


class _Permit:
    __slots__ = ("issuer", "task", "session", "transaction", "admission", "operations", "consumed", "active")

    def __init__(self, issuer, session, admission, operations):
        self.issuer, self.task, self.session = issuer, asyncio.current_task(), session
        self.transaction, self.admission = session.get_transaction(), admission
        self.operations = {(value.action, value.target): value for value in operations}
        self.consumed = {}
        self.active = True


def _active(permit, session):
    if (
        not isinstance(permit, _Permit)
        or session.info.get(_REGISTRY, {}).get(id(permit)) is not permit
        or permit.session is not session
        or permit.task is not asyncio.current_task()
        or not permit.active
        or permit.transaction is None
        or permit.transaction is not session.get_transaction()
        or not permit.transaction.is_active
    ):
        raise _denied()
    return permit


def consume_write(permit, session, *, actor, tenant, action, target, parent, changes):
    permit = _active(permit, session)
    operation = permit.operations.pop((action, target), None)
    try:
        encoded = _changes(changes)
    except Exception:
        permit.active = False
        raise
    if (
        operation is None
        or actor != permit.admission.owner
        or tenant != permit.admission.tenant_id
        or parent != operation.parent
        or encoded != operation.changes_json
    ):
        permit.active = False
        raise _denied()
    permit.consumed[(action, target)] = operation
    return operation


def publication_target(permit, session, target):
    """Only an exact pending write may request the non-content publication projection."""
    permit = _active(permit, session)
    targets = [
        operation
        for (_, identifier), operation in {**permit.operations, **permit.consumed}.items()
        if identifier == target
    ]
    if not targets:
        raise _denied()
    return permit.admission, targets[0]


def invalidate_write(permit, session):
    if (
        isinstance(permit, _Permit)
        and session.info.get(_REGISTRY, {}).get(id(permit)) is permit
        and permit.session is session
        and permit.task is asyncio.current_task()
    ):
        permit.active = False


@service(name="content_sources.publication_writer")
class SourcePublicationWriter(SourceIntakeWriter):
    def __init__(
        self,
        intake: SourceSyncIntake,
        authority: BulkAuthority,
        mappings: Provider[SourceMappings | None] | None = None,
        lineage: Provider[NativeStructuredLineage | None] | None = None,
    ):
        self.intake, self.authority = intake, authority
        self.mappings = mappings
        self.lineage = lineage
        self._preparations = {}

    @asynccontextmanager
    async def structured_producer(self, admission, *, execution, operation, publication):
        from koinon.integrations.content_sources.source_structured import StructuredSourceProducer

        if isinstance(execution, SourceReplacementAcknowledgementExecution):
            raise _denied()
        lineage = self.lineage.get() if self.lineage is not None else None
        if lineage is not None and isinstance(execution, SourceReplacementExecution):
            async with publication() as current:
                if current != admission:
                    raise _denied()
                self.require_fence(current)
                attempt, header = await self.replacement_attempt(admission, execution)
                stored = await self.intake._require_session().get(CatalogEntry, attempt.content_operation_id)
                marker = stored.metadata_json.get("_koinon_source_replacement", {}) if stored else {}
                indexes = [
                    target["pin"]["catalog_id"] for target in header.descriptor_json["targets"]
                    if target["pin"]["role"] == "new_index"
                ]
                if (
                    stored is None
                    or header.producer_kind != "replace_dataset"
                    or header.descriptor_json["native"]["domain"] != "structured"
                    or len(indexes) != 1
                    or marker.get("attempt_id") != attempt.id
                    or marker.get("previous_attempt_id") != header.previous_attempt_id
                    or marker.get("native_workspace_id") != header.descriptor_json["native"]["workspace_id"]
                    or (
                        str(operation.operation_id), operation.tenant_id, operation.actor,
                        str(operation.workspace_id), str(operation.dataset_id), str(operation.file_id),
                        operation.catalog_source_id, operation.catalog_dataset_id,
                        operation.catalog_file_version_id, operation.filename, operation.sha256,
                        operation.size_bytes,
                    ) != (
                        attempt.content_operation_id, admission.tenant_id, admission.owner,
                        marker.get("native_workspace_id"), marker.get("native_dataset_id"),
                        marker.get("native_file_id"), attempt.source_id, attempt.asset_id,
                        indexes[0], stored.name, attempt.sha256, attempt.size_bytes,
                    )
                ):
                    raise _denied()
                producer = StructuredSourceProducer(
                    self, admission, execution, operation, publication, lineage, attempt.id
                )
            try:
                yield producer
            finally:
                producer.close()
            return
        if lineage is None or not isinstance(execution, BulkLease) or execution.mode != "dataset":
            raise _denied()
        async with publication() as current:
            if current != admission:
                raise _denied()
            self.require_fence(current)
            resolved = await self.intake._resolve(execution)
            item = await self.intake._require_session().get(BulkItem, execution.item_id)
            if resolved is None or item is None:
                raise _denied()
            reservation = DatasetReservation.stored(item.reservation_json)
            if (
                str(operation.operation_id),
                operation.tenant_id,
                operation.actor,
                str(operation.workspace_id),
                str(operation.dataset_id),
                str(operation.file_id),
                operation.catalog_source_id,
                operation.catalog_dataset_id,
                operation.catalog_file_version_id,
                operation.filename,
                operation.sha256,
                operation.size_bytes,
            ) != (
                item.id,
                admission.tenant_id,
                admission.owner,
                item.native_workspace_id,
                str(reservation.native_dataset_id),
                str(reservation.native_file_id),
                item.source_id,
                item.asset_id,
                reservation.catalog_file_version_id,
                item.filename,
                item.sha256,
                item.size_bytes,
            ):
                raise _denied()
            producer = StructuredSourceProducer(
                self, admission, execution, operation, publication, lineage, resolved[0].id
            )
        try:
            yield producer
        finally:
            producer.close()

    @staticmethod
    def is_run_execution(execution: object) -> bool:
        return isinstance(execution, SourceRunLease)

    async def pin_table_targets(self, admission, execution, identifiers):
        self.require_fence(admission)
        resolved = await self.intake._resolve(execution)
        if resolved is None:
            raise _denied()
        await SourcePublicationBaselines(self.intake._require_session()).pin_members(resolved[0], identifiers)

    async def freeze_publication(self, admission, *, execution, members=()):
        self.require_fence(admission)
        if isinstance(execution, SourceReplacementAcknowledgementExecution):
            raise _denied()
        if isinstance(execution, SourceReplacementExecution):
            attempt, header = await self.replacement_attempt(admission, execution)
            from koinon.knowledge.bulk.structured_dtos import ReplacementMemberPlan

            if (
                not isinstance(header.descriptor_json, dict)
                or not 1 <= len(members) <= 32
                or any(not isinstance(member, ReplacementMemberPlan) for member in members)
                or [member.model_dump(mode="json", by_alias=True) for member in members]
                != header.descriptor_json.get("members")
            ):
                raise _denied()
            return SourcePublicationBinding(attempt.id, header.descriptor_sha256)
        resolved = await self.intake._resolve(execution)
        session = self.intake._require_session()
        item = await session.get(BulkItem, execution.item_id)
        if resolved is None or item is None:
            raise _denied()
        return await SourcePublicationBaselines(session).freeze(resolved[0], admission, item, members=members)

    async def admission_for(self, execution: BulkLease) -> SourceIntakeAdmission | None:
        _no_remote_unit()
        async with primary_authority(read_only=False, fresh=True):
            records = self.authority.records
            await records.authority_lock(execution.tenant_id, execution.subject, execution.token_id)
            if not await records.source_owned(execution.tenant_id, execution.item_id):
                return None
            if execution.token_id is not None:
                raise _denied()
            # Safe immutable producer correlation precedes provider checks; no filename/body is hydrated.
            if await self.intake._resolve(execution, committed=True) is None:
                raise _denied()
            payload = await self.intake._require_session().scalar(
                select(
                    BulkBatch.request_json["_source_admission"],
                ).where(
                    BulkBatch.id == execution.batch_id,
                    BulkBatch.tenant_id == execution.tenant_id,
                    BulkBatch.subject == execution.subject,
                )
            )
            return retained_admission(payload)

    async def replay_publication(self, admission, execution, receipt) -> bool:
        _no_remote_unit()
        await self.authority.catalog._refresh_managed_memberships(admission.owner)
        async with primary_authority(read_only=False, fresh=True):
            await self.authority.source_destination(admission)
            resolved = await self.intake._resolve(execution, committed=True)
            if resolved is None:
                raise _denied()
            session = self.intake._require_session()
            attempt = resolved[0]
            baseline = await session.get(SourcePublicationBaseline, attempt.id)
            if baseline is None or baseline.acknowledgement_json is None:
                return False
            encoded = json.loads(json.dumps(asdict(receipt)))
            item = await session.get(BulkItem, execution.item_id)
            job = await session.get(Job, execution.job_id)
            version = await session.get(SourceImportedVersion, attempt.id)
            if (
                attempt.receipt_json != encoded
                or baseline.acknowledgement_json.get("native_receipt") != encoded
                or receipt.source_attempt_id != attempt.id
                or receipt.source_publication_sha256 != baseline.descriptor_sha256
                or not baseline.acknowledgement_sha256
                or version is None
                or item is None
                or job is None
                or item.receipt_json != encoded
                or item.status != "succeeded"
                or item.job_id != execution.job_id
                or item.batch_id != execution.batch_id
                or item.native_id != receipt.native_asset_id
                or (
                    version.tenant_id,
                    version.source_id,
                    version.asset_id,
                    version.domain,
                    version.native_workspace_id,
                    version.native_source_id,
                    version.native_asset_id,
                    version.native_version_id,
                    version.extraction_id,
                )
                != (
                    attempt.tenant_id,
                    attempt.source_id,
                    attempt.asset_id,
                    receipt.domain,
                    receipt.native_workspace_id,
                    receipt.native_source_id,
                    receipt.native_asset_id,
                    receipt.source_version_id if receipt.domain == "canon" else receipt.file_version_id,
                    receipt.extraction_id,
                )
                or job.status != "succeeded"
                or job.kind != "knowledge.bulk.intake"
                or job.tenant_id != admission.tenant_id
                or job.resource_id != item.asset_id
                or job.attempts != execution.attempt
                or job.worker_id is not None
                or job.lease_until is not None
                or job.payload != {"batch_id": execution.batch_id, "item_id": item.id}
                or job.result
                != {
                    "batch_id": execution.batch_id,
                    "item_id": item.id,
                    "source_id": item.source_id,
                    "asset_id": item.asset_id,
                }
            ):
                raise _denied()
            return True

    @staticmethod
    def creation_operations(entries: tuple) -> tuple:
        return tuple(
            operation
            for identifier, parent, values in entries
            for operation in (
                SourceWriteOperation("create", identifier, parent, values),
                SourceWriteOperation("update", identifier, parent, {"status": "pending"}, 1),
            )
        )

    def require_fence(self, admission):
        session = self.intake._require_session()
        observed = session.info.get(_FENCES, {}).get(id(admission))
        if (
            observed is None
            or observed[0] is not self
            or observed[1] is not admission
            or observed[2] is not asyncio.current_task()
            or observed[3] is not session.get_transaction()
            or not observed[3].is_active
        ):
            raise _denied()

    async def validate_intake(self, admission, manifest):
        """Initial bytes may only enter the accepted format and exact observed file identity."""
        self.require_fence(admission)
        session = self.intake._require_session()
        if len(admission.items) != 1 or len(manifest) != 1:
            raise _denied()
        pin, item = admission.items[0], manifest[0]
        run = await session.get(SourceSyncRun, admission.run_id)
        policy = await session.get(SourceMappingPolicy, run.policy_id)
        observation = await session.get(SourceSyncObservation, pin.observation_id)
        work = await session.get(SourceSyncWork, pin.work_id)
        try:
            request = MappingReviewInput.model_validate(policy.policy_json["request"])
            remote = observed_item(observation.event_json)
            choice = import_choice(remote, request, available_extensions(request.mode))
        except (ValueError, TypeError, KeyError):
            raise _denied() from None
        if (
            work.status != "admitted"
            or work.attempt_id is not None
            or remote.kind != "file"
            or item.mode != request.mode
            or item.filename != choice.filename
            or choice.reason is not None
            or (
                choice.export_mime is None
                and remote.size_bytes is not None
                and item.size_bytes != remote.size_bytes
            )
            or await session.scalar(
                select(SourceImportAttempt.id)
                .where(
                    SourceImportAttempt.tenant_id == admission.tenant_id,
                    SourceImportAttempt.object_id == pin.object_id,
                )
                .limit(1)
            )
            is not None
        ):
            raise _denied()

    async def _execution(self, admission, execution, *, lock_job):
        """Validate only the exact producer; the Job is the final acquired lock."""
        session = self.intake._require_session()
        if isinstance(execution, _REPLACEMENT_EXECUTIONS):
            deadline = await self._execution(admission, execution.run_lease, lock_job=False)
            await self.replacement_attempt(admission, execution)
            if lock_job:
                deadline = await self._execution(admission, execution.run_lease, lock_job=True)
            return deadline
        if isinstance(execution, SourceRunLease):
            if (
                execution.tenant_id,
                execution.owner,
                execution.mapping_id,
                execution.run_id,
                execution.mapping_revision,
                execution.connection_revision,
            ) != (
                admission.tenant_id,
                admission.owner,
                admission.mapping_id,
                admission.run_id,
                admission.mapping_revision,
                admission.connection_revision,
            ):
                raise _denied()
            _, _, job = await SourceRunRepository(session=session).fenced(
                execution, publication=True, lock_job=lock_job
            )
            return job.lease_until
        if not isinstance(execution, BulkLease) or execution.token_id is not None:
            raise _denied()
        records = BulkRepository(session=session)
        resolved = await self.intake._resolve(execution)
        if resolved is None:
            raise _denied()
        attempt, _, run, _, work = resolved
        batch = (
            await session.execute(
                select(
                    BulkBatch.id,
                    BulkBatch.cancelled,
                    BulkBatch.workspace_id,
                    BulkBatch.project_id,
                    BulkBatch.parent_id,
                    BulkBatch.request_json["_source_admission"].label("source_admission"),
                ).where(BulkBatch.id == execution.batch_id)
            )
        ).one_or_none()
        if (
            batch is None
            or batch.source_admission != json.loads(json.dumps(asdict(admission)))
            or len(admission.items) != 1
            or admission.items[0].work_id != work.id
            or admission.items[0].object_id != attempt.object_id
            or run.id != admission.run_id
            or (execution.tenant_id, execution.subject) != (admission.tenant_id, admission.owner)
        ):
            raise _denied()
        if lock_job:
            job, item, batch = await records.fenced(
                execution.tenant_id, execution.item_id, execution.worker_id, execution.attempt
            )
        else:
            item = await records.item(execution.batch_id, execution.item_id)
            job = await session.scalar(
                select(Job).where(Job.id == execution.job_id).execution_options(populate_existing=True)
            )
        if (
            item is None
            or job is None
            or batch.cancelled
            or item.status != "running"
            or job.status != "running"
            or job.kind != "knowledge.bulk.intake"
            or job.tenant_id != admission.tenant_id
            or job.resource_id != item.asset_id
            or job.payload != {"batch_id": batch.id, "item_id": item.id}
            or job.worker_id != execution.worker_id
            or job.attempts != execution.attempt
            or job.lease_until is None
            or job.lease_until <= datetime.now(UTC)
            or item.job_id != execution.job_id
            or job.id != execution.job_id
            or (batch.workspace_id, batch.project_id, batch.parent_id) != admission.destination
            or (
                execution.destination.workspace_id,
                execution.destination.project_id,
                execution.destination.parent_id,
            )
            != admission.destination
            or (item.source_id, item.asset_id, item.sha256, item.size_bytes, item.mode)
            != (
                execution.source_id,
                execution.asset_id,
                execution.sha256,
                execution.size_bytes,
                execution.mode,
            )
        ):
            raise _denied()
        return job.lease_until

    async def replacement_attempt(self, admission, execution):
        session = self.intake._require_session()
        if len(admission.items) != 1:
            raise _denied()
        pin = admission.items[0]
        attempt = await session.get(SourceImportAttempt, execution.attempt_id)
        work = await session.get(SourceSyncWork, pin.work_id)
        header = await session.get(SourcePublicationBaseline, execution.attempt_id)
        operation = await session.get(CatalogEntry, execution.content_operation_id)
        if (
            attempt is None
            or work is None
            or header is None
            or operation is None
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
            or (
                work.tenant_id,
                work.mapping_id,
                work.object_id,
                work.generation,
                work.attempt_id,
            )
            != (
                admission.tenant_id,
                admission.mapping_id,
                pin.object_id,
                pin.generation,
                attempt.id,
            )
            or (header.tenant_id, header.mapping_id, header.object_id, header.source_id, header.asset_id)
            != (attempt.tenant_id, attempt.mapping_id, attempt.object_id, attempt.source_id, attempt.asset_id)
            or header.producer_kind not in {"replace_document", "replace_dataset"}
            or not header.previous_attempt_id
            or not header.descriptor_sha256
            or header.acknowledgement_json is not None
            or operation.tenant_id != admission.tenant_id
            or operation.metadata_json.get("_koinon_source_replacement", {}).get("attempt_id") != attempt.id
        ):
            raise _denied()
        if isinstance(execution, SourceReplacementAcknowledgementExecution):
            if (
                type(execution.receipt) is not NativeCommit
                or (work.status, work.error_code) != ("conflict", "SOURCE_PUBLICATION_NOT_ACKNOWLEDGED")
                or attempt.receipt_json != {
                    **json.loads(json.dumps(asdict(execution.receipt))),
                    "operation_id": execution.content_operation_id,
                }
                or execution.receipt.source_attempt_id != attempt.id
                or execution.receipt.source_publication_sha256 != header.descriptor_sha256
            ):
                raise _denied()
        elif (
            type(execution) is not SourceReplacementExecution
            or work.status != "processing"
            or attempt.receipt_json is not None
        ):
            raise _denied()
        return attempt, header

    async def _fresh(self, admission: SourceIntakeAdmission, execution):
        _no_remote_unit()
        mappings = self.mappings.get() if self.mappings is not None else None
        if mappings is None:
            raise _denied()
        await self.authority.catalog._refresh_managed_memberships(admission.owner)
        async with primary_authority(read_only=False, fresh=True):
            await self.authority.source_destination(admission)
            mapping, objects, run = await self.intake._fence(admission)
            await self._execution(admission, execution, lock_job=False)
            session = self.intake._require_session()
            policy = await session.get(SourceMappingPolicy, run.policy_id)
            if policy is None:
                raise _denied()
            mapping_snapshot = SimpleNamespace(
                **{
                    key: getattr(mapping, key)
                    for key in (
                        "provider",
                        "external_subject",
                        "external_tenant",
                        "connection_id",
                        "drive_id",
                        "root_id",
                    )
                }
            )
            policy_snapshot = SimpleNamespace(
                **{
                    key: getattr(policy, key)
                    for key in (
                        "id",
                        "policy_sha256",
                        "authority_sha256",
                        "root_ancestry_json",
                        "policy_json",
                    )
                }
            )
            expected = []
            for pin in admission.items:
                observation = await session.get(SourceSyncObservation, pin.observation_id)
                if observation is None:
                    raise _denied()
                expected.append((objects[pin.object_id].item_id, pin.remote_version, observation.event_json))
        await mappings.remote_capture(admission.owner, admission.tenant_id, mapping_snapshot, policy_snapshot)
        account = Account(
            mapping_snapshot.provider, mapping_snapshot.external_subject, mapping_snapshot.external_tenant
        )
        grant = await mappings.connections.read_grant(
            admission.owner, admission.tenant_id, mapping_snapshot.connection_id, account
        )
        if grant.revision != admission.connection_revision:
            raise _denied()
        scope = SourceScope(account, mapping_snapshot.drive_id)
        slots = asyncio.Semaphore(4)

        async def check(item_id, version, event):
            prior = event.get("item", {})
            async with (
                slots,
                mappings.browser._source(scope, _OperationToken(account, grant.token)) as adapter,
            ):
                current = (
                    await adapter.get_item(item_id)
                    if prior.get("kind") == "folder"
                    else await adapter.check_access(item_id)
                )
            if (
                current.scope != scope
                or current.item_id != item_id
                or current.version != version
                or current.kind not in {"file", "folder"}
                or any(
                    getattr(current, key) != prior.get(key)
                    for key in ("name", "kind", "mime_type", "size_bytes")
                )
                or current.parents != tuple(prior.get("parents", ()))
                or len(current.parents) != 1
            ):
                raise _denied()
            selected_file = current.item_id == mapping_snapshot.root_id and current.kind == "file"
            return current.parents[0], tuple(event.get("ancestry", ())), selected_file, current.version

        paths = []
        failures = []

        async def completed(value):
            try:
                paths.append(await check(*value))
            except Exception as error:
                failures.append(error)

        async with asyncio.TaskGroup() as tasks:
            for value in expected:
                tasks.create_task(completed(value))
        if failures:
            raise failures[0]
        async with mappings.browser._source(scope, _OperationToken(account, grant.token)) as adapter:
            proof = await FolderAncestry(adapter, scope, max_roots=101, max_depth=256).capture(
                (mapping_snapshot.root_id, *(path[0] for path in paths))
            )
        if (
            (mapping_snapshot.root_id, *proof.ancestors(mapping_snapshot.root_id))
            != tuple(policy_snapshot.root_ancestry_json)
            or proof.root_kind(mapping_snapshot.root_id)
            != policy_snapshot.policy_json.get("root_kind", "folder")
        ):
            raise _denied()
        for parent, expected_path, selected_file, version in paths:
            if selected_file:
                root_node = next(node for node in proof.nodes if node.id == mapping_snapshot.root_id)
                if (
                    expected_path
                    or root_node.kind != "file"
                    or root_node.parent != parent
                    or root_node.version != version
                ):
                    raise _denied()
                continue
            reverse = (parent, *proof.ancestors(parent))
            if mapping_snapshot.root_id not in reverse:
                raise _denied()
            actual = tuple(reversed(reverse[: reverse.index(mapping_snapshot.root_id) + 1]))
            if actual != expected_path:
                raise _denied()
        await mappings.connections.confirm_read_grant(
            admission.owner, admission.tenant_id, mapping_snapshot.connection_id, grant
        )

    @asynccontextmanager
    async def prepare(self, admission: SourceIntakeAdmission, *, execution=None):
        """Fresh remote proof is scoped to one subsequent local fence in this exact task."""
        if id(admission) in self._preparations or not isinstance(
            execution, (SourceRunLease, *_REPLACEMENT_EXECUTIONS, BulkLease)
        ):
            raise _denied()
        await self._fresh(admission, execution)
        self._preparations[id(admission)] = (admission, asyncio.current_task(), execution)
        try:
            yield
        finally:
            self._preparations.pop(id(admission), None)

    @asynccontextmanager
    async def fence(self, admission: SourceIntakeAdmission):
        """Caller prepares fresh remote proof first and owns the enclosing primary unit."""
        session = self.intake._require_session()
        prepared = self._preparations.pop(id(admission), None)
        if (
            session.get_transaction() is None
            or prepared is None
            or prepared[0] is not admission
            or prepared[1] is not asyncio.current_task()
        ):
            raise _denied()
        await self.authority.source_destination(admission)
        await self.intake._fence(admission)
        await self._execution(admission, prepared[2], lock_job=False)
        if isinstance(prepared[2], _REPLACEMENT_EXECUTIONS):
            execution = prepared[2]
            _, baseline = await self.replacement_attempt(admission, execution)
            identifiers = list(
                await session.scalars(
                    select(SourcePublicationTarget.catalog_id)
                    .where(SourcePublicationTarget.attempt_id == execution.attempt_id)
                    .order_by(SourcePublicationTarget.catalog_id)
                    .limit(37)
                )
            )
            if not identifiers or len(identifiers) > 36:
                raise _denied()
            locked = list(
                await session.scalars(
                    select(CatalogEntry.id)
                    .where(
                        CatalogEntry.tenant_id == admission.tenant_id,
                        CatalogEntry.id.in_(identifiers),
                    )
                    .order_by(CatalogEntry.id)
                    .with_for_update()
                )
            )
            if locked != identifiers:
                raise _denied()
            await SourcePublicationBaselines(session).verify_before_publication(baseline)
        if isinstance(prepared[2], BulkLease):
            # Queue checks lock the Job. Hold every preexisting canonical target first.
            execution = prepared[2]
            identifiers = {execution.source_id, execution.asset_id}
            if execution.mode == "dataset":
                reserved = await session.scalar(
                    select(BulkItem.reservation_json["catalog_file_version_id"].as_string()).where(
                        BulkItem.id == execution.item_id, BulkItem.batch_id == execution.batch_id
                    )
                )
                tables = list(
                    await session.scalars(
                        select(BulkTableReservation.catalog_table_id)
                        .where(BulkTableReservation.item_id == execution.item_id)
                        .limit(17)
                    )
                )
                if not reserved or len(tables) > 16:
                    raise _denied()
                identifiers.update((reserved, *tables))
            locked = list(
                await session.scalars(
                    select(CatalogEntry.id)
                    .where(
                        CatalogEntry.tenant_id == admission.tenant_id,
                        CatalogEntry.id.in_(sorted(identifiers)),
                    )
                    .order_by(CatalogEntry.id)
                    .with_for_update()
                )
            )
            if set(locked) != identifiers:
                raise _denied()
            resolved = await self.intake._resolve(execution)
            if resolved is None:
                raise _denied()
            baseline = await session.get(SourcePublicationBaseline, resolved[0].id)
            if baseline is None or baseline.acknowledgement_json is not None:
                raise _denied()
            await SourcePublicationBaselines(session).verify_before_publication(baseline)
        identity = (
            self,
            admission,
            asyncio.current_task(),
            session.get_transaction(),
            prepared[2],
            {
                "opened": False,
                "written": False,
                "invalid": False,
                "completion": None,
                "completion_verified": False,
            },
        )
        fences = session.info.setdefault(_FENCES, {})
        if fences:
            raise _denied()
        fences[id(admission)] = identity
        try:
            yield
            state = identity[5]
            if state["invalid"] or state["opened"] and not state["written"]:
                raise _denied()
            if state["completion"] is None:
                await self._execution(admission, prepared[2], lock_job=True)
            else:
                if not state["completion_verified"]:
                    raise _denied()
                await self._completed(admission, state["completion"])
        finally:
            fences.pop(id(admission), None)

    @asynccontextmanager
    async def open(self, admission: SourceIntakeAdmission, operations: tuple[SourceWriteOperation, ...]):
        session = self.intake._require_session()
        observed = session.info.get(_FENCES, {}).get(id(admission))
        if (
            observed is None
            or observed[0] is not self
            or observed[1] is not admission
            or observed[2] is not asyncio.current_task()
            or observed[3] is not session.get_transaction()
            or observed[5]["opened"]
            or not 1 <= len(operations) <= 100
            or len({(value.action, value.target) for value in operations}) != len(operations)
        ):
            raise _denied()
        replacement = observed[4] if isinstance(observed[4], _REPLACEMENT_EXECUTIONS) else None
        if replacement is not None:
            _, header = await self.replacement_attempt(admission, replacement)
            planned = tuple(
                SourceWriteOperation(
                    write["action"],
                    target["pin"]["catalog_id"],
                    target["pin"]["parent_id"],
                    write["fields"],
                    target["pin"]["mutation_revision"] + offset,
                )
                for target in header.descriptor_json["targets"]
                for offset, write in enumerate(target["writes"])
            )
            if operations != planned:
                raise _denied()
        observed[5]["opened"] = True
        attempts = (
            await session.execute(
                select(
                    SourceImportAttempt.source_id,
                    SourceImportAttempt.asset_id,
                    SourceImportAttempt.content_operation_id,
                    SourceImportAttempt.receipt_json["file_version_id"].as_string(),
                    func.jsonb_path_query_array(
                        cast(SourceImportAttempt.receipt_json, JSONB),
                        cast("$.tables[*].catalog_table_id", JSONPATH),
                    ),
                ).where(
                    SourceImportAttempt.tenant_id == admission.tenant_id,
                    SourceImportAttempt.mapping_id == admission.mapping_id,
                    SourceImportAttempt.object_id.in_([value.object_id for value in admission.items]),
                    *([SourceImportAttempt.id == replacement.attempt_id] if replacement is not None else []),
                )
            )
        ).all()
        folders = (
            await session.scalars(
                select(SourceFolderBinding.local_folder_id)
                .join(
                    SourceFolderPublication,
                    (SourceFolderPublication.tenant_id == SourceFolderBinding.tenant_id)
                    & (SourceFolderPublication.mapping_id == SourceFolderBinding.mapping_id)
                    & (SourceFolderPublication.local_folder_id == SourceFolderBinding.local_folder_id),
                )
                .where(
                    SourceFolderBinding.tenant_id == admission.tenant_id,
                    SourceFolderBinding.mapping_id == admission.mapping_id,
                    SourceFolderPublication.object_id.in_(
                        [] if replacement is not None else [value.object_id for value in admission.items]
                    ),
                )
            )
        ).all()
        bound = {identifier for row in attempts for identifier in row[:4] if identifier} | set(folders)
        bound.update(
            identifier for row in attempts for identifier in (row[4] or []) if isinstance(identifier, str)
        )
        if isinstance(observed[4], _REPLACEMENT_EXECUTIONS):
            bound.update(
                await session.scalars(
                    select(SourcePublicationTarget.catalog_id)
                    .where(
                        SourcePublicationTarget.attempt_id == observed[4].attempt_id,
                        SourcePublicationTarget.tenant_id == admission.tenant_id,
                    )
                    .limit(37)
                )
            )
        if isinstance(observed[4], BulkLease) and observed[4].mode == "dataset":
            reserved_versions = await session.scalars(
                select(BulkItem.reservation_json["catalog_file_version_id"].as_string())
                .join(SourceImportAttempt, SourceImportAttempt.intake_item_id == BulkItem.id)
                .where(
                    SourceImportAttempt.tenant_id == admission.tenant_id,
                    SourceImportAttempt.mapping_id == admission.mapping_id,
                    SourceImportAttempt.object_id.in_([value.object_id for value in admission.items]),
                )
            )
            reserved_tables = await session.scalars(
                select(BulkTableReservation.catalog_table_id)
                .join(SourceImportAttempt, SourceImportAttempt.intake_item_id == BulkTableReservation.item_id)
                .where(
                    SourceImportAttempt.tenant_id == admission.tenant_id,
                    SourceImportAttempt.mapping_id == admission.mapping_id,
                    SourceImportAttempt.object_id.in_([value.object_id for value in admission.items]),
                )
            )
            bound.update(identifier for identifier in (*reserved_versions, *reserved_tables) if identifier)
        creates = {value.target for value in operations if value.action == "create"}
        allowed_parents = bound | creates | {admission.destination[2]}
        identifiers = {value.target for value in operations}
        for operation in operations:
            if operation.action != "move":
                continue
            if operation.changes != {"parent_id": admission.destination[2]} or operation.target not in bound:
                raise _denied()
            await self.authority.source_destination(
                replace(
                    admission,
                    destination=(*admission.destination[:2], operation.parent),
                )
            )
            child = aliased(CatalogEntry)
            tree = (
                select(CatalogEntry.id, literal(0).label("depth"))
                .where(
                    CatalogEntry.tenant_id == admission.tenant_id,
                    CatalogEntry.id == operation.target,
                )
                .cte("source_moving_tree", recursive=True)
            )
            tree = tree.union_all(
                select(child.id, tree.c.depth + 1)
                .join(
                    tree,
                    child.parent_id == tree.c.id,
                )
                .where(child.tenant_id == admission.tenant_id, tree.c.depth < 16)
            )
            descendants = (await session.execute(select(tree.c.id, tree.c.depth).limit(4097))).all()
            if (
                len(descendants) > 4096
                or len({row.id for row in descendants}) != len(descendants)
                or any(row.id not in bound or row.depth >= 16 for row in descendants)
            ):
                raise _denied()
            identifiers.update(row.id for row in descendants)
        rows = (
            await session.execute(
                select(
                    CatalogEntry.id,
                    CatalogEntry.parent_id,
                    CatalogEntry.workspace_id,
                    CatalogEntry.project_id,
                    CatalogEntry.mutation_revision,
                    CatalogEntry.name,
                    CatalogEntry.kind,
                )
                .where(
                    CatalogEntry.tenant_id == admission.tenant_id, CatalogEntry.id.in_(sorted(identifiers))
                )
                .order_by(CatalogEntry.id)
                .with_for_update()
            )
        ).all()
        existing = {row.id: SimpleNamespace(**row._asdict()) for row in rows}
        for operation in operations:
            row = existing.get(operation.target)
            if operation.parent not in allowed_parents and operation.action != "move":
                raise _denied()
            if operation.action == "create":
                if row is not None:
                    raise _denied()
                existing[operation.target] = SimpleNamespace(
                    id=operation.target,
                    parent_id=operation.parent,
                    workspace_id=admission.destination[0],
                    project_id=admission.destination[1],
                    mutation_revision=1,
                    name=operation.changes.get("name"),
                    kind=operation.changes.get("kind"),
                )
            elif (
                operation.target not in bound | creates
                or row is None
                or row.mutation_revision != operation.expected_revision
                or row.parent_id != operation.parent
                or (row.workspace_id, row.project_id) != admission.destination[:2]
            ):
                raise _denied()
            else:
                row.mutation_revision += 1
                if operation.action == "move":
                    row.parent_id = operation.changes["parent_id"]
                if "name" in operation.changes:
                    row.name = operation.changes["name"]
        namespace = {
            identifier: row
            for identifier, row in existing.items()
            if row.kind in {"collection", "corpus", "source"}
        }
        if namespace:
            # The already-held tenant lock serializes user and source namespace mutations.
            siblings = (
                await session.execute(
                    select(CatalogEntry.id, CatalogEntry.parent_id, CatalogEntry.name)
                    .where(
                        CatalogEntry.tenant_id == admission.tenant_id,
                        CatalogEntry.parent_id.in_({row.parent_id for row in namespace.values()}),
                        CatalogEntry.id.not_in(namespace),
                    )
                    .limit(100001)
                )
            ).all()
            if len(siblings) > 100000:
                raise _denied()
            occupied = {(row.parent_id, source_name_key(row.name)) for row in siblings}
            for row in namespace.values():
                if not isinstance(row.name, str) or not row.name.strip():
                    raise _denied()
                key = (row.parent_id, source_name_key(row.name))
                if key in occupied:
                    raise _denied()
                occupied.add(key)
        await self._execution(admission, observed[4], lock_job=True)
        permit = _Permit(self, session, admission, operations)
        session.info.setdefault(_REGISTRY, {})[id(permit)] = permit
        try:
            yield permit
            _active(permit, session)
            if permit.operations:
                raise _denied()
            await self._execution(admission, observed[4], lock_job=True)
            observed[5]["written"] = True
        finally:
            permit.active = False
            permit.operations.clear()
            permit.consumed.clear()
            session.info[_REGISTRY].pop(id(permit), None)

    async def publication_plan(self, admission, execution, receipt):
        """Project only identities and revisions of this exact initial intake reservation."""
        self.require_fence(admission)
        session = self.intake._require_session()
        item = await session.get(BulkItem, execution.item_id)
        batch = await session.get(BulkBatch, execution.batch_id)
        if (
            item is None
            or batch is None
            or receipt.sha256 != item.sha256
            or receipt.size_bytes != item.size_bytes
        ):
            raise _denied()
        await self.authority.source_item(admission, batch, item)
        if receipt.domain != ("canon" if item.mode == "document" else "structured") or (
            receipt.native_workspace_id != item.native_workspace_id
            or not receipt.native_source_id
            or not receipt.native_asset_id
        ):
            raise _denied()
        targets = {
            item.source_id: (admission.destination[2], "source"),
            item.asset_id: (item.source_id, item.mode),
        }
        if item.mode == "dataset":
            from koinon.knowledge.bulk.dataset_dtos import DatasetReservation

            reservation = DatasetReservation.stored(item.reservation_json)
            tables = await BulkRepository(session=session).table_reservations(item.id)
            if (
                receipt.file_version_id != reservation.catalog_file_version_id
                or receipt.native_file_id != str(reservation.native_file_id)
                or receipt.native_asset_id != str(reservation.native_dataset_id)
                or not tables
                or len(tables) != len(receipt.tables)
                or any(
                    (row.catalog_table_id, row.table_id, row.snapshot_id)
                    != (table.catalog_table_id, table.table_id, table.snapshot_id)
                    for row, table in zip(tables, receipt.tables, strict=True)
                )
            ):
                raise _denied()
            targets[reservation.catalog_file_version_id] = (item.asset_id, "index_version")
            targets.update({table.catalog_table_id: (item.asset_id, "table") for table in receipt.tables})
        elif not receipt.source_version_id or not receipt.extraction_id or receipt.tables:
            raise _denied()
        resolved = await self.intake._resolve(execution)
        if resolved is None:
            raise _denied()
        pins = await SourcePublicationBaselines(session).open(resolved[0], receipt)
        revisions = {pin.catalog_id: pin.mutation_revision for pin in pins}
        if set(revisions) != set(targets):
            raise _denied()
        rows = (
            await session.execute(
                select(
                    CatalogEntry.id,
                    CatalogEntry.parent_id,
                    CatalogEntry.kind,
                    CatalogEntry.workspace_id,
                    CatalogEntry.project_id,
                    CatalogEntry.status,
                    CatalogEntry.mutation_revision,
                )
                .where(CatalogEntry.tenant_id == admission.tenant_id, CatalogEntry.id.in_(sorted(targets)))
                .order_by(CatalogEntry.id)
                .with_for_update()
            )
        ).all()
        if len(rows) != len(targets) or any(
            (row.parent_id, row.kind) != targets[row.id]
            or row.status != "pending"
            or (row.workspace_id, row.project_id) != admission.destination[:2]
            for row in rows
        ):
            raise _denied()
        entries = tuple(SimpleNamespace(**row._asdict()) for row in rows)
        return entries, tuple(
            SourceWriteOperation("update", row.id, row.parent_id, {"status": "ready"}, revisions[row.id])
            for row in rows
        )

    @asynccontextmanager
    async def completion(self, admission, execution, receipt):
        """One live execution may transition to its exact terminal receipt in this unit."""
        self.require_fence(admission)
        session = self.intake._require_session()
        fence = session.info[_FENCES][id(admission)]
        state = fence[5]
        if (
            state["invalid"]
            or not state["written"]
            or state["completion"] is not None
            or session.info.get(_REGISTRY)
            or execution is not fence[4]
            or not isinstance(execution, (BulkLease, *_REPLACEMENT_EXECUTIONS))
            or not isinstance(receipt, NativeCommit)
            or (
                isinstance(execution, SourceReplacementAcknowledgementExecution)
                and execution.receipt != receipt
            )
        ):
            state["invalid"] = True
            raise _denied()
        try:
            deadline = await self._execution(admission, execution, lock_job=True)
            resolved = (
                await self.intake.resolve_replacement(admission, execution)
                if isinstance(execution, _REPLACEMENT_EXECUTIONS)
                else await self.intake._resolve(execution)
            )
            if resolved is None:
                raise _denied()
            await SourcePublicationBaselines(session).acknowledge(resolved[0], receipt)
            record = (
                self,
                admission,
                asyncio.current_task(),
                session.get_transaction(),
                execution,
                receipt,
                deadline,
            )
            state["completion"] = record
            yield
            if state["invalid"]:
                raise _denied()
            await session.flush()
            await self._completed(admission, record)
            state["completion_verified"] = True
        except BaseException:
            state["invalid"] = True
            raise

    async def _completed(self, admission, record):
        self.require_fence(admission)
        session = self.intake._require_session()
        if (
            record[0] is not self
            or record[1] is not admission
            or record[2] is not asyncio.current_task()
            or record[3] is not session.get_transaction()
            or record[6] is None
            or record[6] <= datetime.now(UTC)
        ):
            raise _denied()
        lease, receipt = record[4:6]
        await self.authority.source_destination(admission)
        if isinstance(lease, _REPLACEMENT_EXECUTIONS):
            await self._replacement_completed(admission, lease, receipt)
            return
        resolved = await self.intake._resolve(lease)
        if resolved is None:
            raise _denied()
        attempt, origin, _, _, work = resolved
        version = await session.get(SourceImportedVersion, attempt.id)
        item = await session.get(BulkItem, lease.item_id, populate_existing=True)
        job = await session.get(Job, lease.job_id, populate_existing=True)
        batch = await session.get(BulkBatch, lease.batch_id, populate_existing=True)
        encoded = json.loads(json.dumps(asdict(receipt)))
        native_version = receipt.source_version_id if receipt.domain == "canon" else receipt.file_version_id
        if (
            version is None
            or item is None
            or job is None
            or batch is None
            or batch.cancelled
            or attempt.receipt_json != encoded
            or item.receipt_json != encoded
            or item.status != "succeeded"
            or item.error_code is not None
            or item.job_id != lease.job_id
            or item.native_id != receipt.native_asset_id
            or item.native_workspace_id != receipt.native_workspace_id
            or (item.source_id, item.asset_id, item.sha256, item.size_bytes, item.mode)
            != (lease.source_id, lease.asset_id, lease.sha256, lease.size_bytes, lease.mode)
            or job.status != "succeeded"
            or job.kind != "knowledge.bulk.intake"
            or job.tenant_id != admission.tenant_id
            or job.resource_id != item.asset_id
            or job.payload != {"batch_id": batch.id, "item_id": item.id}
            or job.result
            != {
                "batch_id": batch.id,
                "item_id": item.id,
                "source_id": item.source_id,
                "asset_id": item.asset_id,
            }
            or job.attempts != lease.attempt
            or job.worker_id is not None
            or job.lease_until is not None
            or job.progress != 100
            or work.status != "imported"
            or work.error_code is not None
            or batch.request_json.get("_source_admission") != json.loads(json.dumps(asdict(admission)))
            or (
                batch.tenant_id,
                batch.subject,
                batch.token_id,
                batch.workspace_id,
                batch.project_id,
                batch.parent_id,
            )
            != (admission.tenant_id, admission.owner, None, *admission.destination)
            or (
                version.tenant_id,
                version.source_id,
                version.asset_id,
                version.domain,
                version.native_workspace_id,
                version.native_source_id,
                version.native_asset_id,
                version.native_version_id,
                version.extraction_id,
            )
            != (
                admission.tenant_id,
                lease.source_id,
                lease.asset_id,
                receipt.domain,
                receipt.native_workspace_id,
                receipt.native_source_id,
                receipt.native_asset_id,
                native_version,
                receipt.extraction_id,
            )
            or origin.state != "imported"
            or origin.published_native_version_id != native_version
            or origin.published_sha256 != receipt.sha256
        ):
            raise _denied()

    async def _replacement_completed(self, admission, execution, receipt):
        session = self.intake._require_session()
        attempt, origin, _, _, work = await self.intake.resolve_replacement(admission, execution)
        await SourceRunRepository(session=session).fenced(execution.run_lease, publication=True)
        baseline = await session.get(SourcePublicationBaseline, attempt.id)
        version = await session.get(SourceImportedVersion, attempt.id)
        encoded = json.loads(json.dumps(asdict(receipt)))
        native_version = receipt.source_version_id if receipt.domain == "canon" else receipt.file_version_id
        if (
            baseline is None
            or baseline.acknowledgement_json is None
            or baseline.acknowledgement_json.get("native_receipt") != encoded
            or attempt.receipt_json != {**encoded, "operation_id": execution.content_operation_id}
            or attempt.committed_at is None
            or receipt.source_attempt_id != attempt.id
            or receipt.source_publication_sha256 != baseline.descriptor_sha256
            or work.status != "imported"
            or work.error_code is not None
            or origin.state != "imported"
            or origin.published_sha256 != receipt.sha256
            or origin.published_native_version_id != native_version
            or origin.published_local_revision != "cpv1:" + baseline.acknowledgement_sha256
            or version is None
            or (
                version.tenant_id,
                version.source_id,
                version.asset_id,
                version.domain,
                version.native_workspace_id,
                version.native_source_id,
                version.native_asset_id,
                version.native_version_id,
                version.extraction_id,
            )
            != (
                admission.tenant_id,
                attempt.source_id,
                attempt.asset_id,
                receipt.domain,
                receipt.native_workspace_id,
                receipt.native_source_id,
                receipt.native_asset_id,
                native_version,
                receipt.extraction_id,
            )
        ):
            raise _denied()


@dataclass(frozen=True, slots=True)
class PublicationState:
    id: str
    mutation_revision: int
    status: str
    latest_content_version_id: str | None


async def publication_state(permit, session, target: str) -> PublicationState:
    admission, _ = publication_target(permit, session, target)
    row = (
        await session.execute(
            select(
                CatalogEntry.id,
                CatalogEntry.mutation_revision,
                CatalogEntry.status,
                CatalogEntry.metadata_json["latest_content_version_id"].as_string(),
            ).where(CatalogEntry.id == target, CatalogEntry.tenant_id == admission.tenant_id)
        )
    ).one_or_none()
    if row is None:
        raise _denied()
    return PublicationState(*row)
