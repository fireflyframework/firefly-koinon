# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import hashlib
import hmac
from dataclasses import dataclass
from typing import Protocol


class BlobTooLargeError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class BlobReceipt:
    key: str
    size_bytes: int
    sha256: str


class BlobStore(Protocol):
    async def put(self, key: str, data: bytes, content_type: str | None = None) -> None: ...
    async def get_bounded(self, key: str, max_bytes: int) -> bytes: ...
    async def delete(self, key: str) -> None: ...
    async def purge_staging(self, key: str) -> None: ...


def validate_key(key: str) -> str:
    if (
        not isinstance(key, str)
        or not key
        or len(key) > 1024
        or key.startswith("/")
        or any(part in {"", ".", ".."} for part in key.split("/"))
        or any(char in key for char in ("\\", "\0", "\r", "\n"))
    ):
        raise ValueError("A registered relative blob key is required")
    return key


async def admit(store: BlobStore, key: str, content: bytes, *, sha256: str, max_bytes: int) -> BlobReceipt:
    validate_key(key)
    if not isinstance(content, bytes) or not content or len(content) > max_bytes:
        raise BlobTooLargeError("Private blob exceeds its admitted byte bound")
    digest = hashlib.sha256(content).hexdigest()
    if not isinstance(sha256, str) or not hmac.compare_digest(digest, sha256):
        raise ValueError("Private blob does not match its admitted digest")
    await store.put(key, content)
    verified = await store.get_bounded(key, len(content))
    if len(verified) != len(content) or not hmac.compare_digest(hashlib.sha256(verified).hexdigest(), digest):
        raise OSError("Private blob admission could not verify persisted bytes")
    return BlobReceipt(key, len(content), digest)
