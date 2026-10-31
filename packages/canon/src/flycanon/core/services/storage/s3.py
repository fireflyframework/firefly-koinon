# Copyright 2024-2026 Firefly Software Foundation
# Modifications Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""S3 ObjectStore backend (prod). Requires ``uv sync --extra s3``.

boto3 is synchronous, so each call is offloaded onto a worker thread with
``asyncio.to_thread`` -- the same pattern the local backend uses -- to keep the
event loop free. AWS credentials are resolved by boto3 from the standard
environment (``AWS_ACCESS_KEY_ID`` / ``AWS_SECRET_ACCESS_KEY`` / profiles /
instance roles); only the bucket, key prefix and optional endpoint/region are
configured here.
"""

from __future__ import annotations

from functools import partial
from typing import Any

from koinon_storage.client_lifecycle import ClientLifecycle
from pyfly.context.lifecycle import pre_destroy

from flycanon.core.services.storage.object_store import ObjectStore, ObjectTooLargeError

# Guarded like the qdrant/chroma vector-store backends: importing this module
# without the ``s3`` extra installed must not crash; the factory raises a clear
# error only when an S3 store is actually requested.
try:
    import boto3
    from botocore.exceptions import ClientError

    _HAS_BOTO3 = True
except ImportError:  # pragma: no cover -- exercised via the s3 extra being absent
    boto3 = None  # type: ignore[assignment]
    ClientError = Exception  # type: ignore[assignment, misc]
    _HAS_BOTO3 = False


class S3ObjectStore(ObjectStore):
    """Bucket-relative ObjectStore backed by boto3.

    Keys are placed under ``prefix`` within ``bucket``. ``endpoint_url`` allows
    pointing at MinIO or other S3-compatible services; ``region`` is forwarded
    to the client when set.
    """

    def __init__(
        self,
        bucket: str,
        prefix: str = "",
        endpoint_url: str | None = None,
        region: str | None = None,
        *,
        client: Any = None,
        owns_client: bool = True,
    ) -> None:
        if client is None and not _HAS_BOTO3:
            raise RuntimeError("S3ObjectStore requires the 's3' extra; run: uv sync --extra s3")
        self._bucket = bucket
        self._prefix = prefix.strip("/")
        self._lifecycle = ClientLifecycle()
        self._owns_client = owns_client if client is not None else True
        if client is None:
            assert boto3 is not None
            client = boto3.client("s3", endpoint_url=endpoint_url, region_name=region)
        self._client = client

    def _full_key(self, key: str) -> str:
        if ".." in key.split("/") or key.startswith("/"):
            raise ValueError(f"illegal key {key!r}")
        if not self._prefix:
            return key
        return f"{self._prefix}/{key}"

    async def put(self, key: str, data: bytes, content_type: str | None = None) -> None:
        full = self._full_key(key)
        kwargs: dict[str, object] = {
            "Bucket": self._bucket,
            "Key": full,
            "Body": data,
        }
        if content_type is not None:
            kwargs["ContentType"] = content_type
        await self._lifecycle.run(lambda: self._client.put_object(**kwargs))

    async def get(self, key: str) -> bytes:
        return await self._lifecycle.run(lambda: self.get_sync(key))

    async def get_bounded(self, key: str, max_bytes: int) -> bytes:
        if max_bytes < 0:
            raise ValueError("The byte limit cannot be negative")
        full = self._full_key(key)

        def read():
            try:
                response = self._client.get_object(Bucket=self._bucket, Key=full)
            except ClientError as error:
                if _is_not_found(error):
                    raise FileNotFoundError(key) from error
                raise
            stream = response["Body"]
            try:
                content = stream.read(max_bytes + 1)
                if len(content) > max_bytes:
                    raise ObjectTooLargeError("Original exceeds the configured byte limit")
                return content
            finally:
                stream.close()

        return await self._lifecycle.run(read)

    def get_sync(self, key: str) -> bytes:
        with self._lifecycle.operation():
            full = self._full_key(key)
            try:
                response = self._client.get_object(Bucket=self._bucket, Key=full)
            except ClientError as error:
                if _is_not_found(error):
                    raise FileNotFoundError(key) from error
                raise
            stream = response["Body"]
            try:
                return stream.read()
            finally:
                stream.close()

    async def delete(self, key: str) -> None:
        full = self._full_key(key)
        await self._lifecycle.run(partial(self._client.delete_object, Bucket=self._bucket, Key=full))

    async def exists(self, key: str) -> bool:
        full = self._full_key(key)
        try:
            await self._lifecycle.run(partial(self._client.head_object, Bucket=self._bucket, Key=full))
        except ClientError as exc:
            if _is_not_found(exc):
                return False
            raise
        return True

    @pre_destroy
    async def close(self) -> None:
        def release():
            if self._owns_client:
                self._client.close()

        await self._lifecycle.close(release)


def _is_not_found(exc: Exception) -> bool:
    """Whether a boto3 ClientError represents a missing key / 404."""
    error = getattr(exc, "response", {}).get("Error", {})
    return error.get("Code") in ("404", "NoSuchKey", "NotFound")
