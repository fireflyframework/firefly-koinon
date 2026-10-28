# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Private durable bytes with opaque registered keys and bounded verified reads."""

import hashlib
import os
import tempfile
from pathlib import Path
from uuid import UUID

from flycanon.core.services.storage.local_fs import LocalFsObjectStore
from flycanon.core.services.storage.object_store import ObjectTooLargeError
from pyfly.container import component
from pyfly.kernel import ConflictException, ServiceUnavailableException

from koinon.knowledge.attachments.settings import AttachmentSettings


class AtomicPrivateStore(LocalFsObjectStore):
    @staticmethod
    def _write(path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".staging-", delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
            for directory in (path.parent, path.parent.parent, path.parent.parent.parent):
                descriptor = os.open(directory, os.O_RDONLY)
                try:
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)


@component(name="knowledge.attachments.storage")
class AttachmentStorage:
    def __init__(self, settings: AttachmentSettings):
        self.settings = settings
        self.store: AtomicPrivateStore | None = None

    def configured(self):
        if not self.settings.storage_root:
            raise ServiceUnavailableException(
                "Configure a dedicated private attachment storage directory",
                code="ATTACHMENT_STORAGE_REQUIRED",
            )
        root = Path(self.settings.storage_root).expanduser()
        if root.is_symlink():
            raise ServiceUnavailableException(
                "Use a private real directory", code="ATTACHMENT_STORAGE_REQUIRED"
            )
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if root.stat().st_mode & 0o077:
            raise ServiceUnavailableException(
                "The attachment storage directory must have private 0700 permissions",
                code="ATTACHMENT_STORAGE_REQUIRED",
            )
        if not os.access(root, os.R_OK | os.W_OK | os.X_OK):
            raise ServiceUnavailableException(
                "The private attachment directory must permit owner read, write and traversal",
                code="ATTACHMENT_STORAGE_REQUIRED",
            )
        if self.store is None:
            self.store = AtomicPrivateStore(str(root))
        return self.store

    @staticmethod
    def key(row, normalized=False):
        namespace = hashlib.sha256(
            (row.tenant_id + "\0" + row.subject + "\0" + row.thread_id).encode()
        ).hexdigest()
        return namespace + "/" + str(UUID(row.id)) + ("/normalized" if normalized else "/original")

    async def put(self, row, content: bytes, *, normalized=False):
        if not content or len(content) > 64 * 1024 * 1024:
            raise ValueError("Private blob exceeds a supported byte bound")
        await self.configured().put(self.key(row, normalized), content)

    async def read(self, row, *, normalized=False):
        expected_size = row.normalized_size_bytes if normalized else row.size_bytes
        expected_hash = row.normalized_sha256 if normalized else row.sha256
        if expected_size is None or not 0 < expected_size <= 64 * 1024 * 1024 or not expected_hash:
            raise ConflictException("Private original is unavailable", code="ATTACHMENT_ORIGINAL_UNAVAILABLE")
        try:
            content = await self.configured().get_bounded(self.key(row, normalized), expected_size)
        except ObjectTooLargeError as error:
            raise ConflictException(
                "Private file integrity verification failed", code="ATTACHMENT_DIGEST_MISMATCH"
            ) from error
        except (FileNotFoundError, OSError) as error:
            raise ServiceUnavailableException(
                "The private file is unavailable in its configured storage",
                code="ATTACHMENT_ORIGINAL_UNAVAILABLE",
            ) from error
        if len(content) != expected_size or hashlib.sha256(content).hexdigest() != expected_hash:
            raise ConflictException(
                "Private file integrity verification failed", code="ATTACHMENT_DIGEST_MISMATCH"
            )
        return content

    async def purge(self, row):
        for normalized in (False, True):
            await self.configured().delete(self.key(row, normalized))
        directory = Path(self.settings.storage_root) / self.key(row).rsplit("/", 1)[0]
        for index, path in enumerate(directory.glob(".staging-*")):
            if index >= 64:
                raise OSError("Registered private staging cleanup requires another bounded attempt")
            if path.is_file() and not path.is_symlink():
                path.unlink(missing_ok=True)
