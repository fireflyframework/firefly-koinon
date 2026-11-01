# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Development-only immutable file transport using the same pinned reference contract."""

from hashlib import sha256
from pathlib import Path

from koinon_storage.cloud import ObjectIntegrityError
from koinon_storage.files import FILE_CHUNK_BYTES, StoredObjectReference, VerifiedSink, source_file


def local_identity(root):
    return sha256(("localfs:" + str(Path(root).resolve())).encode()).hexdigest()


def version(path):
    value = path.stat()
    return f"{value.st_dev}:{value.st_ino}:{value.st_size}:{value.st_mtime_ns}"


def create_file(root, target, key, source, maximum):
    with source_file(source, maximum) as (stream, size, digest):
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            with target.open("xb") as sink:
                while data := stream.read(FILE_CHUNK_BYTES):
                    sink.write(data)
                sink.flush()
                import os

                os.fsync(sink.fileno())
        except FileExistsError:
            pass
        reference = StoredObjectReference(
            key, size, digest, local_identity(root), "local_inode", version(target)
        )
        with source_file(target, maximum) as (_, actual_size, actual_hash):
            if (actual_size, actual_hash) != (size, digest):
                raise ObjectIntegrityError("Original key already contains different bytes")
        return reference


def download_file(root, source, reference, target, maximum):
    if (
        reference.store_identity != local_identity(root)
        or reference.version_kind != "local_inode"
        or reference.version != version(source)
        or reference.size_bytes > maximum
    ):
        raise ObjectIntegrityError("Original file route, version or byte bound changed")
    target = Path(target)
    created = False
    try:
        with source_file(source, maximum) as (stream, _, _), target.open("xb") as destination:
            created = True
            sink = VerifiedSink(destination, reference)
            while data := stream.read(FILE_CHUNK_BYTES):
                sink.write(data)
            sink.finish()
        if reference.version != version(source):
            raise ObjectIntegrityError("Original file changed during transfer")
    except BaseException:
        if created:
            target.unlink(missing_ok=True)
        raise


def capture_file(root, path, key, size, digest, maximum):
    with source_file(path, maximum) as (_, actual_size, actual_digest):
        if (actual_size, actual_digest) != (size, digest):
            raise ObjectIntegrityError("Original differs from its admitted receipt")
        return StoredObjectReference(key, size, digest, local_identity(root), "local_inode", version(path))
