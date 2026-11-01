# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import hashlib
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

from koinon_storage.files import StoredObjectReference
from pyfly.container import Provider, component
from pyfly.kernel import RateLimitException, ServiceUnavailableException

from koinon.knowledge.attachments.storage import AttachmentStorage
from koinon.knowledge.external_reviews.entities import ExternalFileReviewRow
from koinon.storage.ports import BlobReceipt, BlobStore, FileBlobStore, admit
from koinon.storage.scratch import ScratchAdmission


@component(name="knowledge.external_reviews.storage")
class ExternalReviewFileStorage:
    def __init__(self, attachments: Provider[AttachmentStorage | None], scratch: ScratchAdmission):
        self.attachments = attachments
        self.scratch = scratch
        self._spooling = False

    @asynccontextmanager
    async def spool(self, size_bytes: int):
        if self._spooling:
            raise RateLimitException("File preparation is busy; try again", code="EXTERNAL_FILE_IO_LIMIT")
        with self.scratch.reserve(2 * size_bytes):
            self._spooling = True
            try:
                yield
            finally:
                self._spooling = False

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
        if isinstance(store, FileBlobStore):
            if not 0 < len(content) <= limit or hashlib.sha256(content).hexdigest() != sha256:
                raise ValueError("Staged file differs from its admitted bytes")
            with self.scratch.reserve(2 * len(content)), tempfile.TemporaryDirectory(
                prefix="koinon-review-chunk-"
            ) as directory:
                path = Path(directory) / "chunk"
                with path.open("xb") as target:
                    target.write(content)
                reference = await store.create_file(self.key(row, suffix), path)
                return BlobReceipt(reference.key, reference.size_bytes, reference.sha256)
        return await admit(store, self.key(row, suffix), content, sha256=sha256, max_bytes=limit)

    def file_transport(self) -> bool:
        store, _ = self.configured()
        return isinstance(store, FileBlobStore)

    async def seal_file(
        self, row: ExternalFileReviewRow, size: int, sha256: str
    ) -> StoredObjectReference | None:
        store, limit = self.configured()
        if not 0 < size <= limit:
            raise ValueError("File exceeds its configured storage bound")
        with tempfile.TemporaryDirectory(prefix="koinon-review-seal-") as directory:
            path = Path(directory) / "original"
            digest, count = hashlib.sha256(), 0
            with path.open("xb") as target:
                for index in range(len(row.chunks_json)):
                    chunk = row.chunks_json[str(index)]
                    content = await self.read(row, f"chunks/{index}", chunk["size"], chunk["sha256"])
                    count += len(content)
                    if count > size:
                        raise ValueError("Staged file exceeds its admitted size")
                    digest.update(content)
                    target.write(content)
            if count != size or digest.hexdigest() != sha256:
                raise ValueError("Staged file differs from its admitted digest")
            if isinstance(store, FileBlobStore):
                return await store.create_file(self.key(row, "original"), path)
            # Legacy byte-only stores keep their existing synchronous admission ceiling.
            if size > 32 * 1024**2:
                raise ValueError("Large file ingestion requires a file-based object store")
            await self.put(row, "original", path.read_bytes(), sha256)
            return None

    async def download(self, row: ExternalFileReviewRow, path: Path, size: int, sha256: str) -> None:
        store, limit = self.configured()
        if not 0 < size <= limit:
            raise ValueError("File exceeds its configured storage bound")
        recorded = row.blob_reference_json
        if recorded is not None:
            reference = StoredObjectReference.from_dict(recorded)
            if (reference.key, reference.size_bytes, reference.sha256) != (
                self.key(row, "original"),
                size,
                sha256,
            ):
                raise ValueError("Stored file reference differs from the approved manifest")
            if not isinstance(store, FileBlobStore):
                raise ValueError("The sealed object's storage transport is unavailable")
            await store.download_file(reference, path, max_bytes=size)
        elif isinstance(store, FileBlobStore):
            reference = await store.capture_file(self.key(row, "original"), size, sha256)
            await store.download_file(reference, path, max_bytes=size)
        else:
            if size > 32 * 1024**2:
                raise ValueError("Large file ingestion requires a file-based object store")
            content = await self.read(row, "original", size, sha256)
            with path.open("xb") as target:
                target.write(content)

    async def read(self, row: ExternalFileReviewRow, suffix: str, size: int, sha256: str) -> bytes:
        store, limit = self.configured()
        if not 0 < size <= limit:
            raise ValueError("File exceeds its configured storage bound")
        if suffix == "original" and row.blob_reference_json is not None:
            if size > 32 * 1024**2:
                raise ValueError("Use the queued file transport for large originals")
            async with self.spool(size):
                with tempfile.TemporaryDirectory(prefix="koinon-reviewed-read-") as directory:
                    path = Path(directory) / "original"
                    await self.download(row, path, size, sha256)
                    return path.read_bytes()
        content = await store.get_bounded(self.key(row, suffix), size)
        if len(content) != size or hashlib.sha256(content).hexdigest() != sha256:
            raise ValueError("Staged file integrity verification failed")
        return content

    async def purge(self, row: ExternalFileReviewRow, suffix: str) -> None:
        store, _ = self.configured()
        key = self.key(row, suffix)
        await store.delete(key)
        await store.purge_staging(key)
