# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from koinon_storage.cloud import CloudStore, ObjectIntegrityError, ObjectTooLargeError
from pyfly.context.lifecycle import pre_destroy

from koinon.storage.ports import BlobIntegrityError, BlobTooLargeError
from koinon.storage.settings import AttachmentStorageProfile


class CloudBlobStore:
    def __init__(self, profile: AttachmentStorageProfile, *, client=None, owns_client=True):
        self.native = CloudStore(profile.cloud_profile(), client=client, owns_client=owns_client)

    async def put(self, key, data, content_type=None):
        try:
            await self.native.put(key, data, content_type)
        except ObjectTooLargeError:
            raise BlobTooLargeError("Private cloud blob exceeds its configured byte bound") from None

    async def create_file(self, key, path, content_type=None):
        return await self.native.create_file(key, path, content_type)

    async def capture_file(self, key, size, digest):
        return await self.native.capture_file(key, size, digest)

    async def download_file(self, reference, path, *, max_bytes):
        await self.native.download_file(reference, path, max_bytes=max_bytes)

    async def get_bounded(self, key, max_bytes):
        try:
            return await self.native.get_bounded(key, max_bytes)
        except ObjectTooLargeError:
            raise BlobTooLargeError("Private cloud blob exceeds its read bound") from None
        except ObjectIntegrityError:
            raise BlobIntegrityError("Private cloud blob integrity verification failed") from None

    async def delete(self, key):
        await self.native.delete(key)

    async def purge_staging(self, key):
        await self.native.purge_staging(key)

    @pre_destroy
    async def close(self) -> None:
        await self.native.close()
