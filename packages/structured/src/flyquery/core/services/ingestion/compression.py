# Copyright 2024-2026 Firefly Software Foundation
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

"""Transparent decompression for upload-time format chain."""

from __future__ import annotations

import asyncio
import bz2
import gzip
import os
import tempfile
import threading
import zipfile
from pathlib import Path

from flyquery.core.services.ingestion.resources import bounded_copy, copy_file, current_scope

MAX_DECOMPRESSED_BYTES = 5 * 1024 * 1024 * 1024  # 5 GB safety cap


async def decompress_to_temp(source_path: str, compression: str) -> str:
    """Decompress *source_path* into a temp file and return the temp path.

    The caller is responsible for deleting the returned temp file when done.
    """
    ownership = threading.Lock()
    abandoned = False
    output: str | None = None

    def populate():
        nonlocal output
        path = _sync(source_path, compression)
        # Runner shutdown can cancel the executor Task while this thread still runs.
        with ownership:
            if abandoned:
                Path(path).unlink(missing_ok=True)
            else:
                output = path
        return path

    worker = asyncio.create_task(asyncio.to_thread(populate))
    try:
        result = await asyncio.shield(worker)
    except asyncio.CancelledError as cancelled:
        with ownership:
            abandoned = True
            if output is not None:
                Path(output).unlink(missing_ok=True)
                output = None
        while not worker.done():
            try:
                await asyncio.shield(worker)
            except asyncio.CancelledError:
                continue
            except Exception as cleanup_failure:
                raise cancelled from cleanup_failure
        try:
            worker.result()
        except asyncio.CancelledError:
            raise cancelled from None
        except Exception as cleanup_failure:
            raise cancelled from cleanup_failure
        raise
    with ownership:
        output = None
    return result


def _sync(source_path: str, compression: str) -> str:
    p = Path(source_path)
    # Determine the inner extension (strip the compression suffix).
    if compression == "gz" or compression == "bz2":
        inner_ext = p.stem.rsplit(".", 1)[-1] if "." in p.stem else ".bin"
        if not inner_ext.startswith("."):
            inner_ext = f".{inner_ext}"
    elif compression == "zip":
        inner_ext = ".bin"
    elif compression == "none":
        inner_ext = p.suffix or ".bin"
    else:
        raise ValueError(f"unknown compression {compression!r}")

    # We only need the path, then we hand it to ``gzip.open`` / ``bz2.open`` /
    # ``zipfile`` to populate. ``mkstemp`` gives us that without the open file
    # handle that SIM115 would otherwise rightly complain about.
    scratch_root = current_scope().policy.scratch_root
    if scratch_root is None:
        fd, out_path = tempfile.mkstemp(suffix=inner_ext)
    else:
        fd, out_path = tempfile.mkstemp(suffix=inner_ext, dir=scratch_root)
    try:
        os.close(fd)
        if compression == "gz":
            with gzip.open(source_path, "rb") as src, open(out_path, "wb") as dst:
                _bounded_copy(
                    src, dst, min(MAX_DECOMPRESSED_BYTES, current_scope().policy.decompressed_max_bytes)
                )
        elif compression == "bz2":
            with bz2.open(source_path, "rb") as src, open(out_path, "wb") as dst:
                _bounded_copy(
                    src, dst, min(MAX_DECOMPRESSED_BYTES, current_scope().policy.decompressed_max_bytes)
                )
        elif compression == "zip":
            with zipfile.ZipFile(source_path, "r") as zf:
                files = [n for n in zf.namelist() if not n.endswith("/")]
                if len(files) != 1:
                    raise ValueError(f"zip must contain exactly one file; got multiple files: {files}")
                with zf.open(files[0]) as src, open(out_path, "wb") as dst:
                    _bounded_copy(
                        src, dst, min(MAX_DECOMPRESSED_BYTES, current_scope().policy.decompressed_max_bytes)
                    )
        elif compression == "none":
            copy_file(source_path, out_path)
    except BaseException:
        Path(out_path).unlink(missing_ok=True)
        raise

    return out_path


def _bounded_copy(src, dst, cap: int) -> None:
    bounded_copy(src, dst, cap)
