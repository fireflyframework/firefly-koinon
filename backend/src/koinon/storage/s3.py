# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import base64
import hashlib
import threading
from typing import Any

from koinon_storage.client_lifecycle import ClientLifecycle
from pyfly.context.lifecycle import pre_destroy

from koinon.storage.ports import BlobTooLargeError, validate_key
from koinon.storage.settings import AttachmentStorageProfile


class S3BlobStore:
    """Private bounded objects in an existing bucket; never provisions buckets or public URLs."""

    def __init__(self, settings: AttachmentStorageProfile, *, client: Any = None, owns_client: bool = True):
        settings.__post_init__()
        self.settings = settings
        self._client = client
        self._owns_client = owns_client if client is not None else True
        self._lifecycle = ClientLifecycle()
        self._client_lock = threading.Lock()

    def _sdk(self):
        with self._client_lock:
            if self._client is None:
                try:
                    import boto3
                    from botocore.config import Config
                except ImportError:
                    raise OSError("Private S3 storage requires the boto3 storage dependency") from None
                self._client = boto3.client(
                    "s3",
                    endpoint_url=self.settings.s3_endpoint_url or None,
                    region_name=self.settings.s3_region or None,
                    config=Config(
                        connect_timeout=self.settings.request_timeout_seconds,
                        read_timeout=self.settings.request_timeout_seconds,
                        retries={"total_max_attempts": 2, "mode": "standard"},
                    ),
                )
            return self._client

    def _key(self, key: str):
        key = validate_key(key)
        prefix = self.settings.s3_prefix.rstrip("/")
        return prefix + "/" + key if prefix else key

    async def _run(self, function):
        with self._lifecycle.operation():
            try:
                return await self._lifecycle.run(function)
            except (BlobTooLargeError, FileNotFoundError):
                raise
            except Exception as error:
                response = getattr(error, "response", {})
                code = response.get("Error", {}).get("Code") if isinstance(response, dict) else None
                if code in {"404", "NoSuchKey", "NotFound"}:
                    raise FileNotFoundError("Registered private blob is unavailable") from error
                raise OSError("Private object storage request failed") from error

    async def put(self, key: str, data: bytes, content_type: str | None = None) -> None:
        full = self._key(key)
        if not isinstance(data, bytes) or not 0 < len(data) <= self.settings.max_object_bytes:
            raise BlobTooLargeError("Private blob exceeds its configured byte bound")
        digest = hashlib.sha256(data)
        arguments = {
            "Bucket": self.settings.s3_bucket,
            "Key": full,
            "Body": data,
            "ContentType": content_type or "application/octet-stream",
            "Metadata": {"sha256": digest.hexdigest(), "bytes": str(len(data))},
            "ChecksumSHA256": base64.b64encode(digest.digest()).decode(),
            "ServerSideEncryption": "AES256",
        }
        if self.settings.s3_kms_key_id:
            arguments.update(ServerSideEncryption="aws:kms", SSEKMSKeyId=self.settings.s3_kms_key_id)
        await self._run(lambda: self._sdk().put_object(**arguments))

    async def get_bounded(self, key: str, max_bytes: int) -> bytes:
        full = self._key(key)
        if type(max_bytes) is not int or not 0 <= max_bytes <= self.settings.max_object_bytes:
            raise ValueError("Private read requires a configured byte bound")

        def read():
            response = self._sdk().get_object(
                Bucket=self.settings.s3_bucket,
                Key=full,
                Range=f"bytes=0-{max_bytes}",
            )
            stream = response["Body"]
            try:
                if response.get("ContentLength", 0) > max_bytes:
                    raise BlobTooLargeError("Private blob exceeds its read bound")
                content = stream.read(max_bytes + 1)
                if len(content) > max_bytes:
                    raise BlobTooLargeError("Private blob exceeds its read bound")
                return content
            finally:
                stream.close()

        return await self._run(read)

    async def delete(self, key: str) -> None:
        full = self._key(key)
        await self._run(lambda: self._sdk().delete_object(Bucket=self.settings.s3_bucket, Key=full))

    async def purge_staging(self, key: str) -> None:
        with self._lifecycle.operation():
            validate_key(key)

    @pre_destroy
    async def close(self) -> None:
        def release():
            if self._owns_client and self._client is not None:
                self._client.close()

        await self._lifecycle.close(release)
