# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from koinon_storage.cloud import CloudProfile, CloudStore
from koinon_storage.cloud import ObjectTooLargeError as CloudTooLargeError
from pyfly.context.lifecycle import pre_destroy

from flycanon.core.services.storage.object_store import ObjectStore, ObjectTooLargeError


class CloudObjectStore(ObjectStore):
    def __init__(self, profile: CloudProfile, *, client=None, owns_client=True):
        self.native = CloudStore(profile, client=client, owns_client=owns_client)

    async def put(self, key, data, content_type=None):
        await self.native.put(key, data, content_type)

    async def create_file(self, key, path, content_type=None):
        return await self.native.create_file(key, path, content_type)

    async def download_file(self, reference, path, *, max_bytes):
        await self.native.download_file(reference, path, max_bytes=max_bytes)

    async def get(self, key):
        return await self.get_bounded(key, self.native.profile.max_object_bytes)

    async def get_bounded(self, key, max_bytes):
        try:
            return await self.native.get_bounded(key, max_bytes)
        except CloudTooLargeError:
            raise ObjectTooLargeError("Original exceeds the configured byte limit") from None

    def get_sync(self, key):
        try:
            return self.native.get_sync(key)
        except CloudTooLargeError:
            raise ObjectTooLargeError("Original exceeds the configured byte limit") from None

    async def delete(self, key):
        await self.native.delete(key)

    async def exists(self, key):
        return await self.native.exists(key)

    @pre_destroy
    async def close(self) -> None:
        await self.native.close()
