# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import asyncio
import os
import tempfile
from contextlib import suppress
from pathlib import Path

from koinon.storage.ports import BlobTooLargeError, validate_key


class LocalBlobStore:
    def __init__(self, root: str):
        self.root = Path(root).expanduser()
        self.validate_root()
        self.root = self.root.resolve()

    def validate_root(self):
        root = self.root
        if root.is_symlink():
            raise OSError("Private storage must use a real directory")
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if not root.is_dir() or root.stat().st_mode & 0o077:
            raise OSError("Private storage root requires owner-only 0700 permissions")
        if not os.access(root, os.R_OK | os.W_OK | os.X_OK):
            raise OSError("Private storage requires owner read, write and traversal")

    def _path(self, key: str):
        self.validate_root()
        path = (self.root / validate_key(key)).resolve()
        if self.root not in path.parents:
            raise ValueError("Registered blob key escapes its private root")
        return path

    async def put(self, key: str, data: bytes, content_type: str | None = None) -> None:
        path = self._path(key)
        await asyncio.to_thread(self._write, path, data)

    async def put_immutable(self, key: str, data: bytes, content_type: str | None = None) -> None:
        await asyncio.to_thread(self._write, self._path(key), data, replace=False)

    def _write(self, path: Path, data: bytes, *, replace: bool = True):
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".staging-", delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            if replace:
                os.replace(temporary, path)
            else:
                with suppress(FileExistsError):
                    os.link(temporary, path)
            directory = path.parent
            while True:
                descriptor = os.open(directory, os.O_RDONLY)
                try:
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
                if directory == self.root:
                    break
                directory = directory.parent
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    async def get_bounded(self, key: str, max_bytes: int) -> bytes:
        if type(max_bytes) is not int or max_bytes < 0:
            raise ValueError("A nonnegative integer read bound is required")
        path = self._path(key)

        def read():
            with path.open("rb") as stream:
                content = stream.read(max_bytes + 1)
            if len(content) > max_bytes:
                raise BlobTooLargeError("Private blob exceeds its read bound")
            return content

        return await asyncio.to_thread(read)

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(self._path(key).unlink, missing_ok=True)

    async def purge_staging(self, key: str) -> None:
        directory = self._path(key).parent
        for index, path in enumerate(directory.glob(".staging-*")):
            if index >= 64:
                raise OSError("Registered staging cleanup requires another bounded attempt")
            if path.is_file() and not path.is_symlink():
                await asyncio.to_thread(path.unlink, missing_ok=True)
