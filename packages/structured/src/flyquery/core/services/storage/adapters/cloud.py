# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Native structured port over bounded immutable cloud bytes."""

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime

from koinon_storage.cloud import CloudProfile, CloudStore, ObjectTooLargeError
from pyfly.context.lifecycle import pre_destroy

from flyquery.core.services.storage.object_store import ObjectMeta


class CloudObjectStore:
    def __init__(self, profile: CloudProfile, *, presign_ttl_s=86400, client=None, owns_client=True):
        self.native = CloudStore(profile, client=client, owns_client=owns_client)
        self._presign_ttl_s = presign_ttl_s

    async def put(self, key: str, body: bytes | AsyncIterator[bytes], content_type: str, kms_key_uri=None):
        limit = self.native.profile.max_object_bytes
        self.native._full_key(key)
        if isinstance(body, bytes):
            data = body
        else:
            data = bytearray()
            async with asyncio.timeout(self.native.profile.request_timeout_seconds):
                async for chunk in body:
                    if not isinstance(chunk, bytes):
                        raise ValueError("Cloud upload chunks must be bytes")
                    if len(data) + len(chunk) > limit:
                        raise ObjectTooLargeError("Cloud object exceeds its configured byte limit")
                    data.extend(chunk)
            data = bytes(data)
        if len(data) > limit:
            raise ObjectTooLargeError("Cloud object exceeds its configured byte limit")
        await self.native.put(key, data, content_type, kms_key_uri=kms_key_uri)
        return ObjectMeta(
            key=key,
            size_bytes=len(data),
            content_type=content_type,
            etag=None,
            last_modified=datetime.now(tz=UTC),
            kms_key_uri=kms_key_uri,
        )

    async def get(self, key):
        async def chunks():
            content = await self.native.get(key)
            for offset in range(0, len(content), 1024 * 1024):
                yield content[offset : offset + 1024 * 1024]

        return chunks()

    @staticmethod
    def _metadata(key, value, backend):
        if backend == "azure":
            content_type = getattr(value.content_settings, "content_type", None)
            modified = value.last_modified
        else:
            content_type, modified = value.content_type, value.updated
        return ObjectMeta(
            key=key,
            size_bytes=value.size,
            content_type=content_type or "application/octet-stream",
            etag=str(value.etag) if value.etag else None,
            last_modified=modified or datetime.now(tz=UTC),
        )

    async def head(self, key):
        value = await self.native.head(key)
        return self._metadata(key, value, self.native.profile.backend)

    async def delete(self, key):
        await self.native.delete(key)

    async def list(self, prefix):
        async def items():
            values = await self.native.list_metadata(prefix)
            profile = self.native.profile
            configured = profile.azure_prefix if profile.backend == "azure" else profile.gcs_prefix
            lead = configured.rstrip("/") + "/" if configured else ""
            for value in values:
                if not value.name.startswith(lead):
                    raise OSError("Cloud listing returned an object outside its configured prefix")
                key = value.name[len(lead) :]
                yield self._metadata(key, value, profile.backend)

        return items()

    async def presign_get(self, key, ttl_s):
        if not 0 < ttl_s <= self._presign_ttl_s:
            raise ValueError("Signed object URL exceeds its configured lifetime")
        return await self.native.presign_get(key, ttl_s)

    async def copy(self, src_key, dst_key):
        self.native._full_key(dst_key)
        source = await self.head(src_key)
        await self.native.put(dst_key, await self.native.get(src_key), source.content_type)

    @pre_destroy
    async def close(self) -> None:
        await self.native.close()
