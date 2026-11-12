# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Replace retained originals under an exact source execution and publication baseline."""

import asyncio
import hashlib
import hmac
import json
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Literal
from uuid import UUID, uuid4

from pyfly.container import Provider, service
from pyfly.kernel import ConflictException, ServiceUnavailableException
from sqlalchemy import select, text

from koinon.catalog.entities import CatalogEntry
from koinon.catalog.errors import AccessDenied
from koinon.integrations.content_sources.errors import SourceError
from koinon.integrations.content_sources.import_entities import SourceImportAttempt
from koinon.integrations.content_sources.lifecycle import _no_remote_unit
from koinon.integrations.content_sources.mapping_dtos import MappingReviewInput
from koinon.integrations.content_sources.mapping_preview import available_extensions, import_choice
from koinon.integrations.content_sources.mapping_service import SourceMappings
from koinon.integrations.content_sources.publication_baselines import SourcePublicationBaselines
from koinon.integrations.content_sources.publication_entities import SourcePublicationBaseline
from koinon.integrations.content_sources.reader_access import _OperationToken
from koinon.integrations.content_sources.replacement_receipts import ReplacementReceipts
from koinon.integrations.content_sources.settings import ContentSourceSettings
from koinon.integrations.content_sources.source_publication import (
    SourcePublicationWriter,
    SourceWriteOperation,
    observed_item,
)
from koinon.integrations.content_sources.sync_entities import (
    SourceMappingPolicy,
    SourceSyncObservation,
    SourceSyncRun,
    SourceSyncWork,
)
from koinon.integrations.content_sources.sync_files import _FileSink
from koinon.integrations.content_sources.sync_runs import (
    SourceReplacementAcknowledgementExecution,
    SourceReplacementExecution,
    SourceRunLease,
    SourceRunRepository,
)
from koinon.knowledge.bulk.ports import NativeCommit, NativeObservation, SourceIntakeAdmission
from koinon.knowledge.bulk.service import FileBatches
from koinon.knowledge.bulk.structured_pipeline import StructuredBulkPipeline
from koinon.knowledge.content import ContentUpdates
from koinon.security.authority import primary_authority


def changed():
    return ConflictException("The source replacement identity changed", code="SOURCE_REPLACEMENT_CHANGED")


@dataclass(frozen=True, slots=True)
class SourceReplacementResult:
    outcome: Literal["acknowledged", "conflict", "unresolved"]
    operation_id: str | None
    attempt_id: str | None

    def __post_init__(self):
        if (self.operation_id is None) != (self.attempt_id is None):
            raise ValueError("Replacement operation and attempt identities must remain paired")
        if self.outcome == "acknowledged" and self.attempt_id is None:
            raise ValueError("Acknowledgement requires an exact retained attempt")


@service(name="content_sources.replacements")
class SourceReplacements:
    def __init__(
        self,
        writer: SourcePublicationWriter,
        mappings: SourceMappings,
        updates: Provider[ContentUpdates | None],
        files: Provider[FileBatches | None],
        settings: ContentSourceSettings | None = None,
        structured: Provider[StructuredBulkPipeline | None] | None = None,
    ):
        self.writer, self.mappings, self.updates, self.files = writer, mappings, updates, files
        self.settings = settings or ContentSourceSettings()
        self.structured = structured

    @staticmethod
    def dataset_baseline(previous, policy_id):
        from koinon.knowledge.bulk.structured_dtos import DatasetReplacementBaseline

        receipt = previous.acknowledgement_json["native_receipt"]
        plans = {
            member["catalog_table_id"]: member for member in previous.descriptor_json["members"]
            if member.get("action") != "remove"
        }
        if (
            receipt["domain"] != "structured"
            or set(plans) != {member["catalog_table_id"] for member in receipt["tables"]}
            or len(plans) != len(receipt["tables"])
            or any(
                (plans[member["catalog_table_id"]]["table_id"],
                 plans[member["catalog_table_id"]]["snapshot_id"])
                != (member["table_id"], member["snapshot_id"])
                for member in receipt["tables"]
            )
        ):
            raise changed()
        revision = "cpv1:" + previous.acknowledgement_sha256
        return DatasetReplacementBaseline.model_validate({
            "dataset_id": receipt["native_asset_id"], "catalog_dataset_id": previous.asset_id,
            "source_attempt_id": previous.attempt_id, "imported_version_id": previous.attempt_id,
            "catalog_file_version_id": receipt["file_version_id"], "policy_id": policy_id,
            "local_revision": revision,
            "source_generation": previous.descriptor_json["identity"]["generation"],
            "policy_revision": previous.descriptor_json["identity"]["mapping_revision"],
            "sha256": receipt["sha256"], "native_file_id": receipt["native_file_id"],
            "members": [{
                **{key: member[key] for key in ("table_id", "catalog_table_id", "snapshot_id")},
                "member_key": plans[member["catalog_table_id"]]["member_key"],
                "source_file_id": receipt["native_file_id"], "local_revision": revision,
                "sha256": receipt["sha256"],
            } for member in receipt["tables"]],
        })

    @staticmethod
    async def discover(filename, content, settings):
        """Read the complete bounded member manifest without model calls or native writes."""
        from flyquery.core.services.ingestion.compression import decompress_to_temp
        from flyquery.core.services.ingestion.format_detect import detect_format
        from flyquery.core.services.ingestion.reader import TableExtractionRules
        from flyquery.core.services.ingestion.reader_factory import get_reader
        from flyquery.core.services.ingestion.resources import resource_scope

        from koinon.knowledge.bulk.structured_dtos import SourceReplacementDiscovery

        _no_remote_unit()
        file_format, compression = detect_format(filename, content[:8192])
        with resource_scope(settings), TemporaryDirectory(
            prefix="koinon-source-discovery-", dir=settings.ingest_scratch_root
        ) as directory:
            path = Path(directory) / "original"
            path.write_bytes(content)
            unpacked = None
            try:
                if compression != "none":
                    unpacked = await decompress_to_temp(str(path), compression)
                reader = get_reader(file_format=file_format, compression="none")
                proposed = tuple(await reader.enumerate_tables(unpacked or str(path), TableExtractionRules()))
                return SourceReplacementDiscovery.capture(
                    filename=filename, file_format=file_format, compression=compression,
                    content_sha256=hashlib.sha256(content).hexdigest(), proposed=proposed,
                )
            finally:
                if unpacked is not None:
                    Path(unpacked).unlink(missing_ok=True)

    @asynccontextmanager
    async def publication(self, admission, execution):
        if isinstance(execution, SourceReplacementAcknowledgementExecution):
            raise changed()
        async with self._publication(admission, execution):
            yield admission

    @asynccontextmanager
    async def _publication(self, admission, execution):
        async with (
            self.writer.prepare(admission, execution=execution),
            primary_authority(read_only=False, fresh=True),
            self.writer.fence(admission),
        ):
            yield admission

    async def _locate(self, admission, execution):
        """Local identity precedes any native receipt lookup or provider call."""
        await self.writer.authority.catalog._refresh_managed_memberships(admission.owner)
        async with primary_authority(read_only=False, fresh=True):
            await self.writer.authority.source_destination(admission)
            _, _, _ = await self.writer.intake._fence(admission, committed=True)
            session = self.writer.intake._require_session()
            await SourceRunRepository(session=session).fenced(execution)
            work = await session.get(SourceSyncWork, admission.items[0].work_id)
            if work is None:
                raise changed()
            if work.attempt_id is None:
                return None
            attempt = await session.get(SourceImportAttempt, work.attempt_id)
            header = await session.get(SourcePublicationBaseline, work.attempt_id)
            if (
                attempt is None
                or header is None
                or attempt.intake_item_id is not None
                or not attempt.content_operation_id
                or header.descriptor_json is None
                or (attempt.tenant_id, attempt.mapping_id, attempt.object_id, attempt.generation)
                != (
                    admission.tenant_id,
                    admission.mapping_id,
                    admission.items[0].object_id,
                    admission.items[0].generation,
                )
            ):
                raise changed()
            return attempt, header

    async def _capture(self, admission, execution, *, retained=None):
        producer = (
            SourceReplacementExecution(execution, retained[0].id, retained[0].content_operation_id)
            if retained is not None else execution
        )
        async with self.publication(admission, producer):
            session = self.writer.intake._require_session()
            mapping, objects, run = await self.writer.intake._fence(admission)
            pin = admission.items[0]
            work = await session.get(SourceSyncWork, pin.work_id)
            policy = await session.get(SourceMappingPolicy, run.policy_id)
            observation = await session.get(SourceSyncObservation, pin.observation_id)
            origin = objects[pin.object_id]
            item = observed_item(observation.event_json)
            selected = MappingReviewInput.model_validate(policy.policy_json["request"])
            choice = import_choice(item, selected, available_extensions(selected.mode))
            if (
                (work.status, work.attempt_id) != (
                    ("processing", retained[0].id) if retained is not None else ("admitted", None)
                )
                or item.kind != "file"
                or item.version != pin.remote_version
                or choice.reason is not None
                or work.expected_local_revision != origin.published_local_revision
                or work.expected_sha256 != origin.published_sha256
            ):
                raise changed()
            previous = await SourcePublicationBaselines(session).previous(admission, origin)
            if retained is not None:
                operation = await session.get(CatalogEntry, retained[0].content_operation_id)
                if (
                    previous.attempt_id != retained[1].previous_attempt_id
                    or operation is None
                    or operation.name != choice.filename
                ):
                    raise changed()
            return mapping.connection_id, item, selected, choice, previous

    async def _download(self, admission, execution, connection, item, choice, files):
        remaining = (execution.expires_at - datetime.now(UTC)).total_seconds() - 10
        if remaining <= 0:
            raise changed()
        grant = await self.mappings.connections.read_grant(
            admission.owner, admission.tenant_id, connection, item.scope.account
        )
        if grant.revision != admission.connection_revision:
            raise changed()
        limit = files.storage.effective_file_limit()
        with (
            files.storage.scratch.reserve(limit),
            TemporaryDirectory(prefix="koinon-source-replacement-") as directory,
        ):
            path = Path(directory) / "original"
            with path.open("xb") as stream:
                sink = _FileSink(stream, limit)
                async with (
                    asyncio.timeout(min(remaining, self.settings.transport_options()["transfer_timeout"])),
                    self.mappings.browser._source(
                        item.scope, _OperationToken(item.scope.account, grant.token)
                    ) as adapter,
                ):
                    receipt = await adapter.download(
                        item, sink, max_bytes=limit, export_mime=choice.export_mime
                    )
            if (
                (receipt.scope, receipt.item_id, receipt.version, receipt.size_bytes, receipt.mime_type)
                != (item.scope, item.item_id, item.version, sink.size, choice.export_mime or item.mime_type)
                or not hmac.compare_digest(receipt.sha256, sink.digest.hexdigest())
                or sink.size < 1
            ):
                raise changed()
            await self.mappings.connections.confirm_read_grant(
                admission.owner, admission.tenant_id, connection, grant
            )
            return path.read_bytes()

    async def _reserve_document(
        self, admission, execution, selected, choice, previous, content, updates, *, dataset=None
    ):
        operation_id = str(dataset[0].operation_id) if dataset else str(uuid4())
        attempt_id = str(uuid4())
        digest = hashlib.sha256(content).hexdigest()
        parent = previous.asset_id if dataset else previous.source_id
        kind = "dataset.replace" if dataset else "document.replace"
        metadata = {"operation": kind, "sha256": digest, "bytes": len(content)}
        members = dataset[2] if dataset else ()
        operations = (
            SourceWriteOperation(
                "create",
                operation_id,
                parent,
                {
                    "kind": "index_version",
                    "name": choice.filename,
                    "description": "",
                    "metadata": metadata,
                },
            ),
            SourceWriteOperation("update", operation_id, parent, {"status": "pending"}, 1),
        )
        for member in members:
            if member.action == "add":
                operations += (
                    SourceWriteOperation("create", member.catalog_table_id, previous.asset_id, {
                        "kind": "table", "name": member.name, "description": "",
                        "metadata": {"snapshot_id": str(member.snapshot_id)},
                    }),
                    SourceWriteOperation("update", member.catalog_table_id, previous.asset_id,
                                         {"status": "pending"}, 1),
                )
        async with self.publication(admission, execution):
            session = self.writer.intake._require_session()
            mapping, objects, _ = await self.writer.intake._fence(admission)
            origin = objects[admission.items[0].object_id]
            work = await session.get(SourceSyncWork, admission.items[0].work_id)
            current = await SourcePublicationBaselines(session).previous(admission, origin)
            if (
                current.attempt_id != previous.attempt_id
                or work.attempt_id is not None
                or work.status != "admitted"
                or current.acknowledgement_json is None
            ):
                raise changed()
            previous_receipt = current.acknowledgement_json["native_receipt"]

            async def admitted(version):
                for member in members:
                    if member.action == "add":
                        await updates.knowledge.catalog.create(
                            admission.owner, admission.tenant_id, kind="table", name=member.name,
                            parent_id=previous.asset_id, metadata={"snapshot_id": str(member.snapshot_id)},
                            _source_write=permit, _source_create_id=member.catalog_table_id,
                        )
                        await updates.knowledge.catalog.update(
                            admission.owner, admission.tenant_id, member.catalog_table_id,
                            {"status": "pending"}, _source_write=permit, _source_parent_id=previous.asset_id,
                        )
                attempt = SourceImportAttempt(
                    id=attempt_id,
                    tenant_id=admission.tenant_id,
                    mapping_id=mapping.id,
                    mapping_revision=admission.mapping_revision,
                    object_id=origin.id,
                    generation=origin.generation,
                    intake_item_id=None,
                    content_operation_id=version.id,
                    provider=mapping.provider,
                    external_subject=mapping.external_subject,
                    external_tenant=mapping.external_tenant,
                    drive_id=mapping.drive_id,
                    remote_item_id=origin.item_id,
                    remote_version=admission.items[0].remote_version,
                    source_id=current.source_id,
                    asset_id=current.asset_id,
                    sha256=digest,
                    size_bytes=len(content),
                )
                session.add(attempt)
                await session.flush()
                header = SourcePublicationBaseline(
                    attempt_id=attempt.id,
                    tenant_id=attempt.tenant_id,
                    workspace_id=admission.destination[0],
                    project_id=admission.destination[1],
                    mapping_id=mapping.id,
                    object_id=origin.id,
                    source_id=current.source_id,
                    asset_id=current.asset_id,
                    producer_kind="replace_dataset" if dataset else "replace_document",
                    previous_attempt_id=current.attempt_id,
                )
                session.add(header)
                await session.flush()
                version.metadata_json = {
                    **version.metadata_json,
                    "_koinon_source_replacement": {
                        "schema": "koinon.source-replacement-producer.v1",
                        "attempt_id": attempt.id,
                        "previous_attempt_id": current.attempt_id,
                        "baseline_sha256": dataset[1] if dataset else None,
                        "native_workspace_id": previous_receipt["native_workspace_id"],
                        "native_dataset_id": str(dataset[0].dataset_id) if dataset else None,
                        "native_file_id": str(dataset[0].file_id) if dataset else None,
                        "previous_index_id": previous_receipt["file_version_id"] if dataset else None,
                        "members": [member.model_dump(mode="json", by_alias=True) for member in members],
                    },
                }
                work.attempt_id, work.status, work.error_code = attempt.id, "processing", None
                await session.flush()
                baselines = SourcePublicationBaselines(session)
                await baselines.pin_existing_targets(header, current, members=members)
                if dataset:
                    targets = {operation_id: ("new_index", previous.asset_id, "index_version")}
                    targets.update({member.catalog_table_id: ("member", previous.asset_id, "table")
                                    for member in members if member.action == "add"})
                    await baselines._created(header, targets)
                await baselines.freeze_replacement(attempt, admission)

            async with self.writer.open(admission, operations) as permit:
                await updates._version(
                    admission.owner,
                    admission.tenant_id,
                    parent,
                    kind,
                    choice.filename,
                    content,
                    _source_admission=admitted,
                    _source_write=permit,
                    _source_create_id=operation_id,
                )
        return SourceReplacementExecution(execution, attempt_id, operation_id)

    async def _dataset_plan(self, admission, execution, selected, choice, previous, content, pipeline):
        from flyquery.core.services.ingestion.reader import ProposedTable

        from koinon.knowledge.bulk.structured_dtos import StructuredOperationIdentity
        from koinon.knowledge.bulk.structured_replacement import discover_members, plan_members

        evidence = await self.discover(choice.filename, content, pipeline.operations.configuration())
        async with self.publication(admission, execution):
            session = self.writer.intake._require_session()
            previous_run = await session.get(SourceSyncRun, previous.descriptor_json["observation"]["run_id"])
            if previous_run is None or previous_run.mapping_id != admission.mapping_id:
                raise changed()
            baseline = self.dataset_baseline(previous, previous_run.policy_id)
            baseline_digest = await session.scalar(
                text("SELECT public.koinon_json_sha256(CAST(:baseline AS jsonb))"),
                {"baseline": baseline.model_dump_json(by_alias=True)},
            )
        operation_id = uuid4()
        identity = StructuredOperationIdentity(
            operation_id=operation_id, tenant_id=admission.tenant_id, actor=admission.owner,
            workspace_id=UUID(previous.acknowledgement_json["native_receipt"]["native_workspace_id"]),
            dataset_id=baseline.dataset_id, file_id=uuid4(), catalog_source_id=previous.source_id,
            catalog_dataset_id=previous.asset_id, catalog_file_version_id=str(operation_id),
            filename=choice.filename, sha256=evidence.content_sha256, size_bytes=len(content),
        )
        proposed = tuple(ProposedTable(**value.model_dump()) for value in evidence.proposed)
        resolution = next((value for value in selected.replacement_resolutions
                           if value.object_id == admission.items[0].object_id), None)
        members = plan_members(
            operation_id, tuple(value.model_dump(mode="json") for value in baseline.members),
            discover_members(evidence.file_format, proposed), resolution=resolution,
            object_id=admission.items[0].object_id, remote_version=admission.items[0].remote_version,
            content_sha256=evidence.content_sha256, baseline_sha256=baseline_digest,
        )
        return identity, baseline_digest, members, baseline, evidence

    async def _dataset_identity(self, admission, attempt, header):
        from koinon.knowledge.bulk.structured_dtos import StructuredOperationIdentity

        async with primary_authority(fresh=True):
            session = self.writer.intake._require_session()
            operation = await session.get(CatalogEntry, attempt.content_operation_id)
            if operation is None or operation.tenant_id != admission.tenant_id:
                raise changed()
            marker = operation.metadata_json.get("_koinon_source_replacement", {})
            if (marker.get("attempt_id"), marker.get("previous_attempt_id")) != (
                attempt.id, header.previous_attempt_id
            ):
                raise changed()
            return StructuredOperationIdentity(
                operation_id=UUID(attempt.content_operation_id), tenant_id=admission.tenant_id,
                actor=admission.owner, workspace_id=UUID(marker["native_workspace_id"]),
                dataset_id=UUID(marker["native_dataset_id"]), file_id=UUID(marker["native_file_id"]),
                catalog_source_id=attempt.source_id, catalog_dataset_id=attempt.asset_id,
                catalog_file_version_id=attempt.content_operation_id, filename=operation.name,
                sha256=attempt.sha256, size_bytes=attempt.size_bytes,
            )

    async def _inspect_dataset(self, admission, attempt, header, pipeline):
        from koinon.knowledge.adapters import native_scope

        identity = await self._dataset_identity(admission, attempt, header)
        with native_scope("structured", admission.tenant_id, str(identity.workspace_id), admission.owner):
            async with pipeline.operations.read() as unit:
                observed = await unit.inspect_receipt(identity)
        if observed.receipt is not None and (
            observed.receipt.source_attempt_id != attempt.id
            or observed.receipt.source_publication_sha256 != header.descriptor_sha256
        ):
            raise changed()
        return identity, observed

    async def _retained_dataset_plan(
        self, admission, execution, attempt, header, previous, choice, content, pipeline
    ):
        from koinon.knowledge.bulk.structured_dtos import ReplacementMemberPlan

        identity = await self._dataset_identity(admission, attempt, header)
        evidence = await self.discover(choice.filename, content, pipeline.operations.configuration())
        producer = SourceReplacementExecution(execution, attempt.id, attempt.content_operation_id)
        async with self.publication(admission, producer):
            session = self.writer.intake._require_session()
            previous_run = await session.get(
                SourceSyncRun, previous.descriptor_json["observation"]["run_id"]
            )
            operation = await session.get(CatalogEntry, attempt.content_operation_id)
            if previous_run is None or previous_run.mapping_id != admission.mapping_id or operation is None:
                raise changed()
            marker = operation.metadata_json.get("_koinon_source_replacement", {})
            values = marker.get("members")
            if (
                not isinstance(values, list)
                or not 1 <= len(values) <= 32
                or values != header.descriptor_json.get("members")
            ):
                raise changed()
            try:
                members = tuple(ReplacementMemberPlan.model_validate(value) for value in values)
            except (ValueError, TypeError):
                raise changed() from None
            baseline = self.dataset_baseline(previous, previous_run.policy_id)
            digest = await session.scalar(
                text("SELECT public.koinon_json_sha256(CAST(:baseline AS jsonb))"),
                {"baseline": baseline.model_dump_json(by_alias=True)},
            )
            if (
                digest != marker.get("baseline_sha256")
                or identity.filename != choice.filename
                or evidence.content_sha256 != identity.sha256
            ):
                raise changed()
        return identity, digest, members, baseline, evidence

    async def _run_dataset(
        self, admission, execution, attempt, header, pipeline, updates, *, plan=None, content=b""
    ):
        from koinon.knowledge.adapters import native_scope

        identity = await self._dataset_identity(admission, attempt, header)
        replacement = SourceReplacementExecution(execution, attempt.id, attempt.content_operation_id)
        with native_scope("structured", admission.tenant_id, str(identity.workspace_id), admission.owner):
            async with self.writer.structured_producer(
                admission, execution=replacement, operation=identity,
                publication=lambda: self.publication(admission, replacement),
            ) as producer:
                if plan is not None:
                    if plan[0] != identity:
                        raise changed()
                    async with updates.knowledge.domains.model_connections(
                        admission.owner, admission.tenant_id, admission.destination[0],
                        roles=("structured.embedding",),
                    ):
                        prepared = await pipeline.prepare_replacement(
                            replacement, identity, content, source_admission=admission,
                            source_producer=producer, baseline=plan[3], baseline_sha256=plan[1],
                            members=plan[2], discovery_evidence=plan[4],
                        )
                        if prepared.status == "admitted":
                            return SourceReplacementResult(
                                "unresolved", attempt.content_operation_id, attempt.id
                            )
                await pipeline.finalize_replacement(
                    replacement, identity, source_admission=admission, source_producer=producer,
                )
        _, observed = await self._inspect_dataset(admission, attempt, header, pipeline)
        if observed.status != "committed" or observed.receipt is None:
            return SourceReplacementResult("unresolved", attempt.content_operation_id, attempt.id)
        return await self._acknowledge(admission, execution, attempt, observed.receipt, updates)

    async def _inspect_document(self, admission, attempt, header, updates, *, retained=None):
        from flycanon.core.services.sources.lineage.dtos import DocumentScope
        from flycanon.core.services.sources.lineage.ports import LineageQuery
        from flycanon.core.services.sources.lineage.service import DocumentLineage

        from koinon.knowledge.adapters import native_scope

        workspace = (
            retained.native_workspace_id if retained is not None
            else header.descriptor_json["native"]["workspace_id"]
        )
        digest = retained.descriptor_sha256 if retained is not None else header.descriptor_sha256
        scope = DocumentScope(admission.tenant_id, workspace, admission.owner)
        with native_scope("canon", admission.tenant_id, workspace, admission.owner):
            lineage = updates.knowledge.domains._resolve(DocumentLineage)
            async with lineage.repository.read() as unit:
                version = await unit.first(
                    LineageQuery(
                        "version",
                        scope,
                        equal={"operation_id": attempt.content_operation_id},
                        projection="intake_receipt",
                    )
                )
                if version is None:
                    return NativeObservation("absent")
                artifact = await unit.one(
                    LineageQuery(
                        "artifact",
                        scope,
                        source_id=version["source_id"],
                        equal={"id": version["artifact_id"]},
                        projection="intake_receipt",
                    )
                )
                binding = version.get("source_publication_json") or {}
                retained_sources = (
                    {retained.native_source_id, retained.native_asset_id} if retained is not None else {
                        target["pin"]["native_id"]
                        for target in header.descriptor_json["targets"]
                        if target["pin"]["role"] in {"source", "asset"}
                    }
                )
                if (
                    version["logical_key"] != attempt.source_id
                    or retained_sources != {version["source_id"]}
                    or (artifact["sha256"], artifact["bytes"]) != (attempt.sha256, attempt.size_bytes)
                    or (binding.get("attempt_id"), binding.get("descriptor_sha256"))
                    != (attempt.id, digest)
                ):
                    raise changed()
                extraction = await unit.first(
                    LineageQuery(
                        "extraction",
                        scope,
                        source_id=version["source_id"],
                        equal={"version_id": version["id"], "purpose": "ingestion"},
                        projection="intake_receipt",
                    )
                )
                if extraction is None:
                    return NativeObservation("admitted")
                return NativeObservation(
                    "committed",
                    NativeCommit(
                        "canon",
                        workspace,
                        version["source_id"],
                        version["source_id"],
                        artifact["sha256"],
                        artifact["bytes"],
                        source_version_id=version["id"],
                        extraction_id=extraction["id"],
                        n_chunks=extraction["n_chunks"],
                        object_key=artifact["object_key"],
                        source_attempt_id=attempt.id,
                        source_publication_sha256=digest,
                    ),
                )

    async def _acknowledge(self, admission, execution, attempt, receipt, updates, *, receipt_only=False):
        from flycanon.core.services.sources.lineage.dtos import DocumentScope
        from flycanon.core.services.sources.lineage.service import DocumentLineage

        from koinon.knowledge.adapters import native_scope

        replacement = (
            SourceReplacementAcknowledgementExecution(
                execution, attempt.id, attempt.content_operation_id, receipt
            )
            if receipt_only
            else SourceReplacementExecution(execution, attempt.id, attempt.content_operation_id)
        )
        async with self._publication(admission, replacement):
            session = self.writer.intake._require_session()
            current, baseline = await self.writer.replacement_attempt(admission, replacement)
            if receipt.domain == "canon":
                with native_scope("canon", admission.tenant_id, receipt.native_workspace_id, admission.owner):
                    lineage = updates.knowledge.domains._resolve(DocumentLineage)
                    head = await lineage.head(
                        DocumentScope(admission.tenant_id, receipt.native_workspace_id, admission.owner),
                        receipt.native_source_id,
                    )
                if head is None or (head["version_id"], head["extraction_id"]) != (
                    receipt.source_version_id, receipt.extraction_id,
                ):
                    raise changed()
            else:
                await self._dataset_head(admission, receipt)
            baselines = SourcePublicationBaselines(session)
            pins = await baselines.open(current, receipt)
            operations = tuple(
                SourceWriteOperation(
                    write["action"],
                    target["pin"]["catalog_id"],
                    target["pin"]["parent_id"],
                    write["fields"],
                    target["pin"]["mutation_revision"] + offset,
                )
                for target in baseline.descriptor_json["targets"]
                for offset, write in enumerate(target["writes"])
            )
            entries = {
                row.id: row
                for row in await session.scalars(
                    select(CatalogEntry).where(
                        CatalogEntry.tenant_id == admission.tenant_id,
                        CatalogEntry.id.in_([pin.catalog_id for pin in pins]),
                    )
                )
            }
            facade = updates.knowledge
            async with self.writer.open(admission, operations) as permit:
                details = {
                    "source_version_id": receipt.source_version_id,
                    "extraction_id": receipt.extraction_id,
                    "n_chunks": receipt.n_chunks,
                    "object_store_key": receipt.object_key,
                }
                for identifier, native in (
                    (attempt.source_id, receipt.native_source_id),
                    (attempt.asset_id, receipt.native_asset_id),
                ):
                    binding = await facade._bind(
                        admission.owner,
                        admission.tenant_id,
                        entries[identifier],
                        receipt.domain,
                        native,
                        receipt.native_workspace_id,
                        details,
                    )
                    binding.details_json = {**binding.details_json, **details}
                    await facade.bindings.save(binding)
                for table in receipt.tables:
                    details = {**asdict(table), "file_id": receipt.native_file_id}
                    binding = await facade._bind(
                        admission.owner, admission.tenant_id, entries[table.catalog_table_id],
                        "structured", table.table_id, receipt.native_workspace_id, details,
                    )
                    binding.details_json = {**binding.details_json, **details}
                    await facade.bindings.save(binding)
                if receipt.domain == "structured":
                    await facade._bind(
                        admission.owner, admission.tenant_id, entries[receipt.file_version_id],
                        "structured", receipt.native_file_id, receipt.native_workspace_id,
                        {"dataset_id": receipt.native_asset_id,
                         "table_ids": [table.catalog_table_id for table in receipt.tables]},
                    )
                for operation in operations:
                    await facade.catalog.update(
                        admission.owner,
                        admission.tenant_id,
                        operation.target,
                        operation.changes,
                        _source_write=permit,
                        _source_parent_id=operation.parent,
                    )
            async with self.writer.completion(admission, replacement, receipt):
                await self.writer.intake.committed_replacement(admission, replacement, receipt)
                await facade.catalog._audit(
                    admission.owner,
                    admission.tenant_id,
                    "knowledge.source.replacement_acknowledged",
                    attempt.content_operation_id,
                    {"attempt_id": attempt.id},
                )
        return SourceReplacementResult("acknowledged", attempt.content_operation_id, attempt.id)

    async def _recover(self, admission, execution, updates):
        """Read a known commit before asking for authority to publish its original baseline."""
        async with primary_authority(read_only=False, fresh=True):
            retained = await ReplacementReceipts(self.writer.intake._require_session()).capture(
                admission, execution
            )
        if retained is None:
            return None
        if retained.domain == "canon":
            observed = await self._inspect_document(admission, retained, None, updates, retained=retained)
        else:
            from koinon.knowledge.adapters import native_scope
            from koinon.knowledge.bulk.structured_repository import SourceStructuredReceiptIdentity

            pipeline = self.structured.get() if self.structured is not None else None
            if pipeline is None:
                raise ServiceUnavailableException("Dataset replacement is unavailable")
            identity = SourceStructuredReceiptIdentity(
                operation_id=UUID(retained.content_operation_id), tenant_id=admission.tenant_id,
                actor=admission.owner, workspace_id=UUID(retained.native_workspace_id),
                dataset_id=UUID(retained.native_asset_id), file_id=UUID(retained.native_file_id),
                catalog_source_id=retained.source_id, catalog_dataset_id=retained.asset_id,
                catalog_file_version_id=retained.content_operation_id,
                sha256=retained.sha256, size_bytes=retained.size_bytes,
                source_attempt_id=retained.id, source_publication_sha256=retained.descriptor_sha256,
            )
            with native_scope(
                "structured", admission.tenant_id, retained.native_workspace_id, admission.owner
            ):
                async with pipeline.operations.read() as unit:
                    observed = await unit.inspect_source_receipt(identity)
        if observed.status != "committed" or observed.receipt is None:
            return None
        if not retained.matches(observed.receipt):
            raise changed()
        async with primary_authority(read_only=False, fresh=True):
            outcome = await ReplacementReceipts(self.writer.intake._require_session()).record(
                admission, execution, retained, observed.receipt, audit=self.writer.authority.catalog._audit
            )
        if not retained.acknowledged:
            try:
                return await self._acknowledge(
                    admission, execution, retained, observed.receipt, updates, receipt_only=True
                )
            except (AccessDenied, ConflictException, SourceError):
                # The independently verified native commit survives; no failed publication writes do.
                pass
        return SourceReplacementResult(outcome, retained.content_operation_id, retained.id)

    async def _dataset_head(self, admission, receipt):
        from flyquery.models.entities.dataset import Dataset
        from flyquery.models.entities.file import File
        from flyquery.models.entities.table import Table

        from koinon.knowledge.adapters import native_scope

        pipeline = self.structured.get() if self.structured is not None else None
        if pipeline is None or not receipt.native_file_id or not receipt.file_version_id:
            raise changed()
        with native_scope("structured", admission.tenant_id, receipt.native_workspace_id, admission.owner):
            async with pipeline.operations.read() as unit:
                session = unit._session
                dataset = await session.get(Dataset, UUID(receipt.native_asset_id))
                original = await session.get(File, UUID(receipt.native_file_id))
                members = (await session.execute(select(
                    Table.id, Table.current_snapshot_id,
                ).where(
                    Table.tenant_id == admission.tenant_id,
                    Table.workspace_id == UUID(receipt.native_workspace_id),
                    Table.dataset_id == UUID(receipt.native_asset_id),
                    Table.source_file_id == UUID(receipt.native_file_id), Table.is_active.is_(True),
                ).order_by(Table.id).limit(17))).all()
                if (
                    dataset is None or dataset.status != "ACTIVE"
                    or original is None or original.status != "PARSED"
                    or original.content_hash_sha256 != receipt.sha256
                    or {(str(row.id), str(row.current_snapshot_id)) for row in members}
                    != {(table.table_id, table.snapshot_id) for table in receipt.tables}
                    or len(members) != len(receipt.tables)
                ):
                    raise changed()

    async def execute(
        self, admission: SourceIntakeAdmission, execution: SourceRunLease
    ) -> SourceReplacementResult:
        _no_remote_unit()
        if (
            not isinstance(admission, SourceIntakeAdmission)
            or not isinstance(execution, SourceRunLease)
            or len(admission.items) != 1
            or (
                execution.tenant_id,
                execution.owner,
                execution.mapping_id,
                execution.run_id,
                execution.mapping_revision,
                execution.connection_revision,
            )
            != (
                admission.tenant_id,
                admission.owner,
                admission.mapping_id,
                admission.run_id,
                admission.mapping_revision,
                admission.connection_revision,
            )
        ):
            raise changed()
        updates, files = self.updates.get(), self.files.get()
        if updates is None or files is None:
            raise ServiceUnavailableException(
                "Source replacement is unavailable", code="SOURCE_INTAKE_REQUIRED"
            )
        recovered = await self._recover(admission, execution, updates)
        if recovered is not None:
            return recovered
        retained = await self._locate(admission, execution)
        if retained is not None:
            attempt, header = retained
            pipeline = self.structured.get() if self.structured is not None else None
            if header.producer_kind == "replace_dataset":
                if pipeline is None:
                    raise ServiceUnavailableException("Dataset replacement is unavailable")
                _, observed = await self._inspect_dataset(admission, attempt, header, pipeline)
            else:
                observed = await self._inspect_document(admission, attempt, header, updates)
            if observed.status == "committed" and observed.receipt is not None:
                if header.acknowledgement_json is not None:
                    if header.acknowledgement_json["native_receipt"] != json.loads(
                        json.dumps(asdict(observed.receipt))
                    ):
                        raise changed()
                    return SourceReplacementResult("acknowledged", attempt.content_operation_id, attempt.id)
                return await self._acknowledge(
                    admission, execution, attempt, observed.receipt, updates
                )
            if observed.status == "prepared" and pipeline is not None:
                return await self._run_dataset(admission, execution, attempt, header, pipeline, updates)
            if observed.status == "absent" or (
                observed.status == "admitted" and header.producer_kind == "replace_dataset"
            ):
                connection, item, _, choice, previous = await self._capture(
                    admission, execution, retained=retained
                )
                content = await self._download(admission, execution, connection, item, choice, files)
                if (
                    len(content) != attempt.size_bytes
                    or hashlib.sha256(content).hexdigest() != attempt.sha256
                ):
                    raise changed()
                if header.producer_kind == "replace_dataset":
                    plan = await self._retained_dataset_plan(
                        admission, execution, attempt, header, previous, choice, content, pipeline
                    )
                    return await self._run_dataset(
                        admission, execution, attempt, header, pipeline, updates, plan=plan, content=content
                    )
                replacement = SourceReplacementExecution(execution, attempt.id, attempt.content_operation_id)
                return await self._run_document(
                    admission, execution, replacement, attempt, header, previous, choice, content, updates
                )
            return SourceReplacementResult("unresolved", attempt.content_operation_id, attempt.id)
        connection, item, selected, choice, previous = await self._capture(admission, execution)
        pipeline = self.structured.get() if self.structured is not None else None
        if selected.mode == "dataset" and pipeline is None:
            raise ServiceUnavailableException(
                "Dataset replacement is unavailable", code="SOURCE_INTAKE_REQUIRED"
            )
        content = await self._download(admission, execution, connection, item, choice, files)
        plan = await self._dataset_plan(
            admission, execution, selected, choice, previous, content, pipeline
        ) if selected.mode == "dataset" else None
        replacement = await self._reserve_document(
            admission, execution, selected, choice, previous, content, updates, dataset=plan
        )
        retained = await self._locate(admission, execution)
        if retained is None or previous.acknowledgement_json is None:
            raise changed()
        attempt, header = retained
        if selected.mode == "dataset":
            return await self._run_dataset(
                admission, execution, attempt, header, pipeline, updates, plan=plan, content=content
            )
        return await self._run_document(
            admission, execution, replacement, attempt, header, previous, choice, content, updates
        )

    async def _run_document(
        self, admission, execution, replacement, attempt, header, previous, choice, content, updates
    ):
        old = previous.acknowledgement_json["native_receipt"]
        from flycanon.core.services.sources.lineage.dtos import SourcePublicationBinding

        await updates.knowledge.domains.replace_document(
            tenant_id=admission.tenant_id,
            workspace_id=old["native_workspace_id"],
            source_id=old["native_source_id"],
            filename=choice.filename,
            content=content,
            expected_sha256=old["sha256"],
            actor=admission.owner,
            catalog_workspace_id=admission.destination[0],
            logical_source_key=attempt.source_id,
            operation_id=replacement.content_operation_id,
            expected_source_version_id=old["source_version_id"],
            expected_extraction_id=old["extraction_id"],
            _publication_guard=lambda: self.publication(admission, replacement),
            _source_publication=SourcePublicationBinding(attempt.id, header.descriptor_sha256),
        )
        observed = await self._inspect_document(admission, attempt, header, updates)
        if observed.status != "committed" or observed.receipt is None:
            return SourceReplacementResult("unresolved", attempt.content_operation_id, attempt.id)
        return await self._acknowledge(admission, execution, attempt, observed.receipt, updates)
