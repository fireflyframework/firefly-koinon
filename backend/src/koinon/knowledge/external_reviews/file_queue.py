# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Transfer an explicitly approved original into the existing fenced bulk worker."""

import hashlib
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from pyfly.container import Provider, component
from pyfly.data.relational.sqlalchemy import transactional
from pyfly.kernel import ConflictException, ServiceUnavailableException

from koinon.knowledge.bulk.dtos import BulkAction, BulkDestination, FileBatchCreate, FileManifestItem
from koinon.knowledge.bulk.service import FileBatches
from koinon.knowledge.external_reviews.file_dtos import ExternalFileReviewInput

if TYPE_CHECKING:
    from koinon.knowledge.external_reviews.file_service import ExternalFileReviews


@component(name="knowledge.external_reviews.file_queue")
class ExternalFileQueue:
    def __init__(self, files: Provider[FileBatches | None]):
        self.files = files

    def capacity(self) -> int:
        files = self.files.get()
        if files is None:
            return 0
        files.settings.validate()
        try:
            files.storage.configured()
        except ServiceUnavailableException:
            return 0
        return files.settings.max_file_bytes

    @transactional
    async def link(self, reviews: "ExternalFileReviews", subject, tenant, identifier, batch_id, source):
        row = await reviews.load(subject, tenant, identifier, lock=True)
        if row.bulk_batch_id is not None and row.bulk_batch_id != batch_id:
            raise ConflictException(
                "This approval already owns another batch", code="EXTERNAL_INTAKE_MISMATCH"
            )
        await reviews.source(subject, tenant, identifier, source)
        row.bulk_batch_id = batch_id
        await reviews.rows.save(row)

    async def enqueue(
        self, reviews: "ExternalFileReviews", subject: str, tenant: str, identifier: str
    ) -> None:
        files = self.files.get()
        if files is None:
            raise ServiceUnavailableException(
                "Configure queued file ingestion", code="EXTERNAL_INTAKE_UNAVAILABLE"
            )
        row = await reviews.load(subject, tenant, identifier)
        destination = await reviews.authorize(subject, tenant, row)
        request = ExternalFileReviewInput.model_validate(row.request_json)
        if row.status != "ingesting" or not row.confirmation_key or not row.blob_reference_json:
            raise ConflictException("Approve a sealed original first", code="EXTERNAL_REVIEW_CHANGED")
        operation = hashlib.sha256((row.id + "\0" + row.confirmation_key).encode()).hexdigest()
        batch = await files.create(
            subject,
            tenant,
            FileBatchCreate(
                destination=BulkDestination(
                    workspace_id=destination.workspace_id,
                    project_id=destination.project_id,
                    parent_id=destination.id,
                ),
                items=[
                    FileManifestItem(
                        client_item_id=row.id,
                        filename=request.filename,
                        mode=request.mode,
                        size_bytes=request.size_bytes,
                        sha256=request.sha256,
                    )
                ],
            ),
            "external-review:" + operation,
        )
        items = (await files.items(subject, tenant, batch.id, page_size=1)).items
        if len(items) != 1 or items[0].client_item_id != row.id or items[0].status != "awaiting_upload":
            raise ConflictException("Inspect the retained intake batch", code="EXTERNAL_INTAKE_MISMATCH")
        item = items[0]
        source = await reviews.authority.catalog.get(subject, tenant, item.source_id)
        await self.link(reviews, subject, tenant, identifier, batch.id, source)
        # The review and the batch can use different containers; verify and copy, never retarget a reference.
        async with reviews.storage.spool(request.size_bytes):
            with tempfile.TemporaryDirectory(prefix="koinon-approved-original-") as directory:
                path = Path(directory) / "original"
                await reviews.storage.download(row, path, request.size_bytes, request.sha256)
                ticket = await files.reserve_stream(
                    subject, tenant, batch.id, item.id, "external-file:" + operation
                )
                await files.finish_stream(
                    subject, tenant, batch.id, item.id, ticket, path, request.size_bytes, request.sha256
                )
        current = await files.get(subject, tenant, batch.id)
        await files.submit(
            subject,
            tenant,
            batch.id,
            BulkAction(expected_revision=current.revision),
            "external-submit:" + operation,
        )
