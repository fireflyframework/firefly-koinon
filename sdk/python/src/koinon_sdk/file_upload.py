# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Bounded private snapshots used by the streamed bulk helper."""

import asyncio
import hashlib
import os
import re
import stat
import tempfile
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import BinaryIO

MAX_ORIGINAL_BYTES = 128 * 1024**2
BLOCK_BYTES = 65536


def _snapshot(path: Path, size: int, sha256: str) -> BinaryIO:
    if type(size) is not int or not 1 <= size <= MAX_ORIGINAL_BYTES:
        raise ValueError("Choose a nonempty original of at most 128 MiB")
    if re.fullmatch(r"[0-9a-f]{64}", sha256) is None:
        raise ValueError("Supply the original manifest's SHA-256")
    if path.is_symlink():
        raise ValueError("Choose a regular file, not a symbolic link")
    # Ownership passes to the async context manager only after verification succeeds.
    snapshot = tempfile.TemporaryFile(mode="w+b", prefix="koinon-original-")  # noqa: SIM115
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
        with os.fdopen(descriptor, "rb") as source:
            before = os.fstat(source.fileno())
            if not stat.S_ISREG(before.st_mode) or before.st_size != size:
                raise ValueError("Original size differs from its admitted manifest")
            digest, count = hashlib.sha256(), 0
            while part := source.read(BLOCK_BYTES):
                count += len(part)
                if count > size:
                    raise ValueError("Original grew during verification")
                digest.update(part)
                snapshot.write(part)
            after = os.fstat(source.fileno())
            if (
                count != size
                or digest.hexdigest() != sha256
                or (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
                != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
            ):
                raise ValueError("Original differs from its admitted manifest")
        snapshot.seek(0)
        return snapshot
    except BaseException:
        snapshot.close()
        raise


@asynccontextmanager
async def verified_original(path: Path, size: int, sha256: str) -> AsyncGenerator[BinaryIO, None]:
    task = asyncio.create_task(asyncio.to_thread(_snapshot, path, size, sha256))
    try:
        snapshot = await asyncio.shield(task)
    except asyncio.CancelledError:
        while not task.done():
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                continue
            except Exception:
                break
        with suppress(BaseException):
            task.result().close()
        raise
    try:
        yield snapshot
    finally:
        snapshot.close()
