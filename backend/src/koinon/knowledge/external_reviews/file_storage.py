# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import hashlib

from pyfly.container import Provider, component
from pyfly.kernel import ServiceUnavailableException

from koinon.knowledge.attachments.storage import AttachmentStorage
from koinon.knowledge.external_reviews.entities import ExternalFileReviewRow
from koinon.storage.ports import BlobReceipt, BlobStore, admit


@component(name="knowledge.external_reviews.storage")
class ExternalReviewFileStorage:
    def __init__(self, attachments: Provider[AttachmentStorage | None]):
        self.attachments = attachments

    def configured(self) -> tuple[BlobStore, int]:
        storage = self.attachments.get()
        if storage is None:
            raise ServiceUnavailableException(
                "Configure private object storage", code="EXTERNAL_STORAGE_REQUIRED"
            )
        return storage.configured(), storage.profile.max_object_bytes

    @staticmethod
    def key(row: ExternalFileReviewRow, suffix: str) -> str:
        owner = hashlib.sha256(
            (row.tenant_id + "\0" + row.subject + "\0" + row.credential_id).encode()
        ).hexdigest()
        return f"{owner}/external-reviews/{row.id}/{suffix}"

    async def put(self, row: ExternalFileReviewRow, suffix: str, content: bytes, sha256: str) -> BlobReceipt:
        store, limit = self.configured()
        return await admit(store, self.key(row, suffix), content, sha256=sha256, max_bytes=limit)

    async def read(self, row: ExternalFileReviewRow, suffix: str, size: int, sha256: str) -> bytes:
        store, limit = self.configured()
        if not 0 < size <= limit:
            raise ValueError("File exceeds its configured storage bound")
        content = await store.get_bounded(self.key(row, suffix), size)
        if len(content) != size or hashlib.sha256(content).hexdigest() != sha256:
            raise ValueError("Staged file integrity verification failed")
        return content

    async def purge(self, row: ExternalFileReviewRow, suffix: str) -> None:
        store, _ = self.configured()
        key = self.key(row, suffix)
        await store.delete(key)
        await store.purge_staging(key)
