# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Download an exact remote original before privately authorized native intake."""

import asyncio
import hashlib
import hmac
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from pyfly.container import Provider, service
from pyfly.kernel import ConflictException, ServiceUnavailableException
from sqlalchemy import select

from koinon.integrations.content_sources.dtos import Account, SourceScope
from koinon.integrations.content_sources.import_entities import SourceImportAttempt
from koinon.integrations.content_sources.lifecycle import _no_remote_unit
from koinon.integrations.content_sources.mapping_dtos import MappingReviewInput
from koinon.integrations.content_sources.mapping_entities import SourceMapping, SourceObject
from koinon.integrations.content_sources.mapping_preview import available_extensions, import_choice
from koinon.integrations.content_sources.mapping_service import SourceMappings
from koinon.integrations.content_sources.reader_access import _OperationToken
from koinon.integrations.content_sources.settings import ContentSourceSettings
from koinon.integrations.content_sources.source_publication import SourcePublicationWriter, observed_item
from koinon.integrations.content_sources.sync_entities import (
    SourceMappingPolicy,
    SourceSyncObservation,
    SourceSyncRun,
    SourceSyncWork,
)
from koinon.integrations.content_sources.sync_runs import SourceRunLease
from koinon.knowledge.bulk.dtos import BulkAction, FileBatchCreate
from koinon.knowledge.bulk.ports import SourceIntakeAdmission
from koinon.knowledge.bulk.service import FileBatches
from koinon.security.authority import primary_authority


def changed():
    return ConflictException("Source original or intake identity changed", code="SOURCE_INTAKE_CHANGED")


class _FileSink:
    def __init__(self, stream, limit):
        self.stream, self.limit = stream, limit
        self.size, self.digest = 0, hashlib.sha256()

    async def write(self, chunk: bytes) -> None:
        if not isinstance(chunk, bytes) or self.size + len(chunk) > self.limit:
            raise changed()
        self.stream.write(chunk)
        self.size += len(chunk)
        self.digest.update(chunk)


@dataclass(frozen=True, slots=True)
class SourceFileJob:
    batch_id: str
    item_id: str
    job_id: str


@service(name="content_sources.files")
class SourceFiles:
    def __init__(
        self,
        writer: SourcePublicationWriter,
        mappings: SourceMappings,
        files: Provider[FileBatches | None] | None = None,
        settings: ContentSourceSettings | None = None,
    ):
        self.writer, self.mappings, self.files = writer, mappings, files
        self.settings = settings or ContentSourceSettings()

    async def _capture(self, admission, execution):
        if len(admission.items) != 1:
            raise changed()
        async with (
            self.writer.prepare(admission, execution=execution),
            primary_authority(read_only=False, fresh=True),
            self.writer.fence(admission),
        ):
            session = self.writer.intake._require_session()
            pin = admission.items[0]
            mapping = await session.get(SourceMapping, admission.mapping_id)
            run = await session.get(SourceSyncRun, admission.run_id)
            policy = await session.get(SourceMappingPolicy, run.policy_id)
            observation = await session.get(SourceSyncObservation, pin.observation_id)
            work = await session.get(SourceSyncWork, pin.work_id)
            origin = await session.get(SourceObject, pin.object_id)
            item = observed_item(observation.event_json)
            request = MappingReviewInput.model_validate(policy.policy_json["request"])
            choice = import_choice(item, request, available_extensions(request.mode))
            expected_scope = SourceScope(
                Account(mapping.provider, mapping.external_subject, mapping.external_tenant), mapping.drive_id
            )
            prior = await session.scalar(
                select(SourceImportAttempt.id)
                .where(
                    SourceImportAttempt.tenant_id == admission.tenant_id,
                    SourceImportAttempt.object_id == pin.object_id,
                )
                .limit(1)
            )
            if (
                item.kind != "file"
                or item.version is None
                or item.scope != expected_scope
                or item.item_id != origin.item_id
                or choice.reason is not None
                or work.status != "admitted"
                or work.attempt_id is not None
                or prior is not None
            ):
                raise changed()
            return mapping.connection_id, item, request, choice

    async def _item(self, files, admission, execution, batch_id):
        async with (
            self.writer.prepare(admission, execution=execution),
            primary_authority(read_only=False, fresh=True),
            self.writer.fence(admission),
        ):
            batch = await files._scope(
                admission.owner, admission.tenant_id, batch_id, write=True, _source_admission=admission
            )
            items = await files.records.all_items(batch_id)
            if len(items) != 1:
                raise changed()
            item = await files._item_for_write(
                admission.owner, admission.tenant_id, batch, items[0].id, _source_admission=admission
            )
            return item.id, batch.revision, item.job_id

    async def intake(self, admission: SourceIntakeAdmission, execution: SourceRunLease) -> SourceFileJob:
        _no_remote_unit()
        files = self.files.get() if self.files is not None else None
        if files is None:
            raise ServiceUnavailableException(
                "Source file intake is unavailable", code="SOURCE_INTAKE_REQUIRED"
            )
        connection, item, policy, choice = await self._capture(admission, execution)
        remaining = (execution.expires_at - datetime.now(UTC)).total_seconds() - 10
        if remaining <= 0:
            raise changed()
        timeout = min(self.settings.transport_options()["transfer_timeout"], remaining)
        grant = await self.mappings.connections.read_grant(
            admission.owner, admission.tenant_id, connection, item.scope.account
        )
        if grant.revision != admission.connection_revision:
            raise changed()
        limit = files.storage.effective_file_limit()
        with files.storage.scratch.reserve(limit), TemporaryDirectory(prefix="koinon-source-") as directory:
            path = Path(directory) / "original"
            with path.open("xb") as stream:
                sink = _FileSink(stream, limit)
                async with (
                    asyncio.timeout(timeout),
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
            request = FileBatchCreate.model_validate(
                {
                    "destination": dict(
                        zip(("workspace_id", "project_id", "parent_id"), admission.destination, strict=True)
                    ),
                    "items": [
                        {
                            "client_item_id": admission.items[0].work_id,
                            "filename": choice.filename,
                            "mode": policy.mode,
                            "size_bytes": sink.size,
                            "sha256": receipt.sha256,
                        }
                    ],
                }
            )
            private = dict(_source_admission=admission, _source_execution=execution)
            batch = await files.create(
                admission.owner,
                admission.tenant_id,
                request,
                "source:" + admission.items[0].work_id,
                **private,
            )
            item_id, _, _ = await self._item(files, admission, execution, batch.id)
            await files.stage(
                admission.owner,
                admission.tenant_id,
                batch.id,
                item_id,
                path,
                "source-original:" + admission.items[0].work_id,
                **private,
            )
        _, revision, _ = await self._item(files, admission, execution, batch.id)
        await files.submit(
            admission.owner,
            admission.tenant_id,
            batch.id,
            BulkAction(expected_revision=revision),
            "source-submit:" + admission.items[0].work_id,
            **private,
        )
        _, _, job_id = await self._item(files, admission, execution, batch.id)
        if job_id is None:
            raise changed()
        return SourceFileJob(batch.id, item_id, job_id)
