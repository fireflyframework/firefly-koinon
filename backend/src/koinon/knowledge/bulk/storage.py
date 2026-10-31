# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Private immutable staging bytes; publication authority lives in primary SQL."""

import asyncio
import hashlib
import hmac
import json
from collections.abc import Awaitable, Callable
from contextlib import suppress
from dataclasses import asdict, dataclass, field
from pathlib import Path

from pyfly.container import component
from pyfly.context.lifecycle import pre_destroy
from pyfly.kernel import ConflictException, RateLimitException, ServiceUnavailableException

from koinon.knowledge.bulk.settings import BulkSettings
from koinon.storage.cloud import CloudBlobStore
from koinon.storage.local import LocalBlobStore
from koinon.storage.ports import BlobStore, admit
from koinon.storage.settings import AttachmentStorageProfile


@dataclass
class LocalWriterPermit:
    release: Callable[[], None] = field(repr=False)
    closed: bool = False

    def close(self) -> None:
        if not self.closed:
            self.closed = True
            self.release()


class _CreateOnlyLocal(LocalBlobStore):
    async def put(self, key: str, data: bytes, content_type: str | None = None) -> None:
        await self.put_immutable(key, data, content_type)


@component(name="knowledge.bulk.storage")
class BulkStorage:
    def __init__(self, settings: BulkSettings):
        self.settings = settings
        self._store: BlobStore | None = None
        self._identity: str | None = None
        self._active = 0
        self._writers = 0
        self._closing = False
        self._idle = asyncio.Event()
        self._idle.set()

    def configured(self) -> BlobStore:
        self.settings.validate()
        values = self.settings
        profile = AttachmentStorageProfile(
            backend=values.storage_backend,
            root=values.storage_root,
            azure_account_url=values.azure_account_url,
            azure_container=values.azure_container,
            azure_prefix=values.azure_prefix,
            gcs_bucket=values.gcs_bucket,
            gcs_project=values.gcs_project,
            gcs_prefix=values.gcs_prefix,
            gcs_endpoint_url=values.gcs_endpoint_url,
            request_timeout_seconds=values.storage_request_timeout_seconds,
            max_object_bytes=values.max_file_bytes,
        )
        if profile.backend == "local":
            path = Path(profile.root or "")
            if (
                not profile.root
                or not path.is_absolute()
                or path != path.resolve()
                or not path.is_dir()
                or path.is_symlink()
                or path.stat().st_mode & 0o077
            ):
                raise ServiceUnavailableException(
                    "Configure existing private durable staging storage", code="BULK_STORAGE_REQUIRED"
                )
        identity_values = asdict(profile)
        identity_values.pop("request_timeout_seconds")
        identity_values.pop("max_object_bytes")
        identity = hashlib.sha256(
            json.dumps(identity_values, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        if self._identity is not None and identity != self._identity:
            raise ConflictException("Bulk storage profile changed", code="BULK_STORAGE_CHANGED")
        if self._store is None:
            self._store = (
                _CreateOnlyLocal(profile.root) if profile.backend == "local" else CloudBlobStore(profile)
            )
            self._identity = identity
        return self._store

    def identity(self) -> str:
        self.configured()
        assert self._identity is not None
        return self._identity

    def writer_permit(self) -> LocalWriterPermit:
        self.configured()
        if self._closing:
            raise ServiceUnavailableException("Bulk staging is draining", code="BULK_STORAGE_DRAINING")
        if self._writers >= self.settings.max_local_storage_operations:
            raise RateLimitException("Local staging writer capacity is full", code="BULK_STORAGE_IO_LIMIT")
        self._writers += 1

        def release() -> None:
            self._writers -= 1

        return LocalWriterPermit(release)

    async def _bounded[T](self, operation: Callable[[], Awaitable[T]]) -> T:
        if self._closing:
            raise ServiceUnavailableException("Bulk staging is draining", code="BULK_STORAGE_DRAINING")
        if self._active >= self.settings.max_local_storage_operations:
            raise RateLimitException("Local staging I/O capacity is full", code="BULK_STORAGE_IO_LIMIT")
        self._active += 1
        self._idle.clear()
        task = asyncio.ensure_future(operation())
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            while not task.done():
                try:
                    await asyncio.shield(task)
                except asyncio.CancelledError:
                    continue
                except Exception:
                    break
            with suppress(BaseException):
                task.result()
            raise
        finally:
            self._active -= 1
            if not self._active:
                self._idle.set()

    async def put(self, key: str, content: bytes, digest: str) -> None:
        store = self.configured()
        await self._bounded(
            lambda: admit(store, key, content, sha256=digest, max_bytes=self.settings.max_file_bytes)
        )

    async def read(self, key: str, size: int, digest: str, *, storage_identity: str | None = None) -> bytes:
        store = self.configured()
        if (storage_identity is not None and storage_identity != self.identity()) or (
            storage_identity is None and self.settings.storage_backend != "local"
        ):
            raise ConflictException("Retained staging profile differs", code="BULK_STORAGE_CHANGED")
        if type(size) is not int or not 1 <= size <= self.settings.max_file_bytes:
            raise ConflictException("Stored original exceeds its bound", code="BULK_ORIGINAL_INTEGRITY")
        content = await self._bounded(lambda: store.get_bounded(key, size))
        if len(content) != size or not hmac.compare_digest(hashlib.sha256(content).hexdigest(), digest):
            raise ConflictException(
                "Original failed its immutable byte receipt", code="BULK_ORIGINAL_INTEGRITY"
            )
        return content

    @pre_destroy
    async def close(self) -> None:
        self._closing = True
        await self._idle.wait()
        if isinstance(self._store, CloudBlobStore):
            await self._store.close()
