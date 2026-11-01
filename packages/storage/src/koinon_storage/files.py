# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Pinned object versions and file-based transfers without whole-object memory copies."""

import hmac
import importlib
import json
import os
import re
import stat
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path

from koinon_storage.cloud import ObjectCollisionError, ObjectIntegrityError, ObjectTooLargeError, validate_key

FILE_CHUNK_BYTES = 65536
MAX_LIBRARY_FILE_BYTES = 128 * 1024**2
MAX_OBJECT_BYTES = 256 * 1024**2


@dataclass(frozen=True, slots=True)
class StoredObjectReference:
    key: str
    size_bytes: int
    sha256: str
    store_identity: str
    version_kind: str
    version: str
    schema_version: int = 1

    def __post_init__(self):
        validate_key(self.key)
        if (
            type(self.schema_version) is not int
            or self.schema_version != 1
            or type(self.size_bytes) is not int
            or not 1 <= self.size_bytes <= MAX_OBJECT_BYTES
        ):
            raise ValueError("Unsupported bounded object reference")
        if any(
            not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None
            for value in (self.sha256, self.store_identity)
        ):
            raise ValueError("Object references require SHA256 data and route identities")
        if (
            self.version_kind not in {"azure_etag", "gcs_generation", "s3_version", "local_inode"}
            or not isinstance(self.version, str)
            or not 1 <= len(self.version) <= 2048
            or any(ord(char) < 32 or ord(char) == 127 for char in self.version)
        ):
            raise ValueError("Object references require an exact provider version")

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, value):
        if not isinstance(value, dict) or set(value) != {
            "schema_version",
            "key",
            "size_bytes",
            "sha256",
            "store_identity",
            "version_kind",
            "version",
        }:
            raise ValueError("Use the complete versioned object reference")
        return cls(**value)


def route_identity(profile):
    fields = (
        ("backend", "azure_account_url", "azure_container", "azure_prefix")
        if profile.backend == "azure"
        else ("backend", "gcs_bucket", "gcs_project", "gcs_prefix", "gcs_endpoint_url")
    )
    return sha256(
        json.dumps(
            {name: getattr(profile, name) for name in fields}, sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()


@contextmanager
def source_file(path, maximum):
    path = Path(path)
    if path.is_symlink():
        raise ValueError("A regular owned input file is required")
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
    with os.fdopen(descriptor, "rb") as source:
        before = os.fstat(source.fileno())
        if not stat.S_ISREG(before.st_mode) or not 1 <= before.st_size <= maximum:
            raise ObjectTooLargeError("Input file exceeds its configured byte bound")
        digest = sha256()
        count = 0
        while chunk := source.read(FILE_CHUNK_BYTES):
            count += len(chunk)
            if count > maximum:
                raise ObjectTooLargeError("Input file exceeds its configured byte bound")
            digest.update(chunk)
        after = os.fstat(source.fileno())

        def identity(value):
            return (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns)

        if count != before.st_size or identity(before) != identity(after):
            raise ObjectIntegrityError("Input file changed during verification")
        source.seek(0)
        yield source, count, digest.hexdigest()
        if identity(before) != identity(os.fstat(source.fileno())):
            raise ObjectIntegrityError("Input file changed during transport")


class VerifiedSink:
    def __init__(self, stream, reference):
        self.stream, self.reference = stream, reference
        self.count, self.digest = 0, sha256()

    def write(self, data):
        if self.count + len(data) > self.reference.size_bytes:
            raise ObjectIntegrityError("Object exceeds its registered byte receipt")
        result = self.stream.write(data)
        if result != len(data):
            raise ObjectIntegrityError("Scratch write did not persist its complete chunk")
        self.count += result
        self.digest.update(data)
        return result

    def tell(self):
        return self.count

    def seek(self, position, whence=0):
        if whence != 0 or position != self.count:
            raise ObjectIntegrityError("Object transfer attempted an out-of-order write")
        return self.count

    def finish(self):
        if self.count != self.reference.size_bytes or not hmac.compare_digest(
            self.digest.hexdigest(), self.reference.sha256
        ):
            raise ObjectIntegrityError("Object differs from its registered byte receipt")
        self.stream.flush()
        os.fsync(self.stream.fileno())


def _properties(store, reference):
    blob = store._object(store._full_key(reference.key))
    if store.profile.backend == "azure":
        props = blob.get_blob_properties(**store._options())
        size, version = props.size, str(props.etag)
    else:
        blob.reload(**store._options())
        size, version = blob.size, str(blob.generation)
    if size != reference.size_bytes or version != reference.version:
        raise ObjectIntegrityError("Stored object version or size changed")
    return blob


def _download(store, reference, path):
    blob = _properties(store, reference)
    path = Path(path)
    created = False
    try:
        with path.open("xb") as target:
            created = True
            sink = VerifiedSink(target, reference)
            if store.profile.backend == "azure":
                conditions = importlib.import_module("azure.core").MatchConditions
                chunks = blob.download_blob(
                    offset=0,
                    length=reference.size_bytes + 1,
                    etag=reference.version,
                    match_condition=conditions.IfNotModified,
                    max_concurrency=1,
                    **store._options(),
                ).chunks()
                for chunk in chunks:
                    sink.write(chunk)
            else:
                blob.chunk_size = 4 * 1024 * 1024
                blob.download_to_file(
                    sink,
                    start=0,
                    end=reference.size_bytes - 1,
                    if_generation_match=int(reference.version),
                    checksum="auto",
                    **store._options(),
                )
            sink.finish()
    except BaseException:
        if created:
            path.unlink(missing_ok=True)
        raise


def _reference(store, key, size, digest):
    blob = store._object(store._full_key(key))
    if store.profile.backend == "azure":
        props = blob.get_blob_properties(**store._options())
        actual, version = props.size, str(props.etag)
        kind = "azure_etag"
    else:
        blob.reload(**store._options())
        actual, version = blob.size, str(blob.generation)
        kind = "gcs_generation"
    if actual != size:
        raise ObjectCollisionError("Stored object size differs from the admitted original")
    return StoredObjectReference(key, size, digest, route_identity(store.profile), kind, version)


async def create_file(store, key, path, content_type=None):
    full = store._full_key(key)

    def create():
        with source_file(path, store.profile.max_object_bytes) as (source, size, digest):
            blob = store._object(full)
            metadata = {"sha256": digest, "bytes": str(size)}
            try:
                if store.profile.backend == "azure":
                    settings = importlib.import_module("azure.storage.blob").ContentSettings(
                        content_type=content_type or "application/octet-stream"
                    )
                    options = {"encryption_scope": store.encryption_scope} if store.encryption_scope else {}
                    blob.upload_blob(
                        source,
                        length=size,
                        overwrite=False,
                        metadata=metadata,
                        content_settings=settings,
                        max_concurrency=1,
                        **store._options(),
                        **options,
                    )
                else:
                    blob.chunk_size = 4 * 1024 * 1024
                    blob.metadata = metadata
                    blob.upload_from_file(
                        source,
                        size=size,
                        rewind=False,
                        content_type=content_type or "application/octet-stream",
                        if_generation_match=0,
                        checksum="auto",
                        **store._options(),
                    )
            except Exception as error:
                if store._status(error) not in {409, 412}:
                    raise
            reference = _reference(store, key, size, digest)
            # Verification is streamed to owned scratch, never a second whole object in memory.
            import tempfile

            with tempfile.TemporaryDirectory(prefix="koinon-verify-") as directory:
                _download(store, reference, Path(directory) / "verified")
            return reference

    return await store._run(create)


async def download_file(store, reference, path, max_bytes):
    reference = StoredObjectReference.from_dict(reference.to_dict())
    if reference.store_identity != route_identity(store.profile):
        raise ObjectIntegrityError("Object reference belongs to another storage route")
    expected = "azure_etag" if store.profile.backend == "azure" else "gcs_generation"
    if (
        reference.version_kind != expected
        or type(max_bytes) is not int
        or not reference.size_bytes <= max_bytes <= store.profile.max_object_bytes
    ):
        raise ObjectIntegrityError("Object reference exceeds its configured route or byte bound")
    await store._run(lambda: _download(store, reference, path))


async def capture_file(store, key, size, digest):
    if type(size) is not int or not 1 <= size <= store.profile.max_object_bytes:
        raise ObjectTooLargeError("Original exceeds its configured byte bound")

    def capture():
        import tempfile

        reference = _reference(store, key, size, digest)
        with tempfile.TemporaryDirectory(prefix="koinon-verify-") as directory:
            _download(store, reference, Path(directory) / "original")
        return reference

    return await store._run(capture)
