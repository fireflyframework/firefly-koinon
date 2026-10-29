# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Private durable bytes with opaque registered keys and bounded verified reads."""

import hashlib
from pathlib import Path
from uuid import UUID

from pyfly.container import component
from pyfly.kernel import ConflictException, ServiceUnavailableException

from koinon.knowledge.attachments.settings import AttachmentSettings
from koinon.storage.cloud import CloudBlobStore
from koinon.storage.local import LocalBlobStore
from koinon.storage.ports import BlobIntegrityError, BlobStore, BlobTooLargeError, admit
from koinon.storage.s3 import S3BlobStore
from koinon.storage.settings import AttachmentStorageProfile


@component(name="knowledge.attachments.storage")
class AttachmentStorage:
    def __init__(self, settings: AttachmentSettings, profile: AttachmentStorageProfile | None = None):
        self.settings = settings
        self.profile = profile or AttachmentStorageProfile()
        self.store: BlobStore | None = None
        self._binding: tuple | None = None

    def configured(self):
        profile = self.profile
        profile.__post_init__()
        root = profile.root or self.settings.storage_root
        if (
            profile.backend == "local"
            and profile.root
            and self.settings.storage_root
            and (
                Path(profile.root).expanduser().absolute()
                != Path(self.settings.storage_root).expanduser().absolute()
            )
        ):
            raise ValueError("Private storage root conflicts with the retained attachment root")
        binding = (
            profile.backend,
            root,
            profile.s3_bucket,
            profile.s3_prefix,
            profile.s3_endpoint_url,
            profile.s3_region,
            profile.s3_kms_key_id,
            profile.azure_account_url,
            profile.azure_container,
            profile.azure_prefix,
            profile.gcs_bucket,
            profile.gcs_project,
            profile.gcs_prefix,
            profile.gcs_endpoint_url,
            profile.request_timeout_seconds,
            profile.max_object_bytes,
        )
        if self._binding is not None and self._binding != binding:
            raise ValueError("Private storage profile cannot change in a running instance")
        if self.store is None:
            if profile.backend == "s3":
                self.store = S3BlobStore(profile)
            elif profile.backend in {"azure", "gcs"}:
                self.store = CloudBlobStore(profile)
            else:
                if not root:
                    raise ServiceUnavailableException(
                        "Configure a dedicated private attachment storage directory",
                        code="ATTACHMENT_STORAGE_REQUIRED",
                    )
                try:
                    self.store = LocalBlobStore(root)
                except OSError as error:
                    raise ServiceUnavailableException(
                        "Configure a private real directory with owner read, write and traversal",
                        code="ATTACHMENT_STORAGE_REQUIRED",
                    ) from error
            self._binding = binding
        if isinstance(self.store, LocalBlobStore):
            try:
                self.store.validate_root()
            except OSError as error:
                raise ServiceUnavailableException(
                    "The private storage directory is unavailable or its permissions changed",
                    code="ATTACHMENT_STORAGE_REQUIRED",
                ) from error
        return self.store

    @staticmethod
    def key(row, normalized=False):
        namespace = hashlib.sha256(
            (row.tenant_id + "\0" + row.subject + "\0" + row.thread_id).encode()
        ).hexdigest()
        return namespace + "/" + str(UUID(row.id)) + ("/normalized" if normalized else "/original")

    async def put(self, row, content: bytes, *, normalized=False):
        if not content or len(content) > self.profile.max_object_bytes:
            raise ValueError("Private blob exceeds a supported byte bound")
        expected = hashlib.sha256(content).hexdigest() if normalized else row.sha256
        if not normalized and len(content) != row.size_bytes:
            raise ValueError("Private original differs from its admitted size")
        await admit(
            self.configured(),
            self.key(row, normalized),
            content,
            sha256=expected,
            max_bytes=self.profile.max_object_bytes,
        )

    async def read(self, row, *, normalized=False):
        expected_size = row.normalized_size_bytes if normalized else row.size_bytes
        expected_hash = row.normalized_sha256 if normalized else row.sha256
        if (
            expected_size is None
            or not 0 < expected_size <= self.profile.max_object_bytes
            or not expected_hash
        ):
            raise ConflictException("Private original is unavailable", code="ATTACHMENT_ORIGINAL_UNAVAILABLE")
        try:
            content = await self.configured().get_bounded(self.key(row, normalized), expected_size)
        except (BlobTooLargeError, BlobIntegrityError) as error:
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
        store = self.configured()
        for normalized in (False, True):
            await store.delete(self.key(row, normalized))
        await store.purge_staging(self.key(row))
