# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Release only a verified owned spool, with current authority at every response cut."""

import asyncio
import hmac
import os
import re
import stat
from hashlib import sha256
from urllib.parse import quote

from starlette.responses import StreamingResponse


class OriginalFileResponse(StreamingResponse):
    def __init__(self, download):
        self.download = download
        self.deadline_seconds = 120
        receipt = download.receipt
        if (
            type(receipt.bytes) is not int
            or not 1 <= receipt.bytes <= 128 * 1024**2
            or re.fullmatch(r"[0-9a-f]{64}", receipt.sha256) is None
        ):
            raise ValueError("A bounded verified original receipt is required")
        super().__init__(
            (),
            media_type="application/octet-stream",
            headers={
                "Content-Length": str(receipt.bytes),
                "Content-Disposition": "attachment; filename*=UTF-8''"
                + quote(receipt.filename or "document", safe=""),
                "X-Content-Type-Options": "nosniff",
                "Cache-Control": "private, no-store",
                "ETag": '"' + receipt.sha256 + '"',
            },
        )

    async def stream_response(self, send):
        await self.download.guard()
        descriptor = os.open(
            self.download.path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
        )
        with os.fdopen(descriptor, "rb") as source:
            observed = os.fstat(source.fileno())
            if not stat.S_ISREG(observed.st_mode) or observed.st_size != self.download.receipt.bytes:
                raise ValueError("Original scratch differs from its verified receipt")
            await send(
                {"type": "http.response.start", "status": self.status_code, "headers": self.raw_headers}
            )
            digest = sha256()
            size = 0
            while chunk := source.read(65536):
                size += len(chunk)
                digest.update(chunk)
                if size > self.download.receipt.bytes:
                    raise ValueError("Original scratch exceeded its receipt")
                await self.download.guard()
                await send({"type": "http.response.body", "body": chunk, "more_body": True})
            if size != self.download.receipt.bytes or not hmac.compare_digest(
                digest.hexdigest(), self.download.receipt.sha256
            ):
                raise ValueError("Original scratch failed its final integrity cut")
        await self.download.guard()
        await send({"type": "http.response.body", "body": b"", "more_body": False})

    async def __call__(self, scope, receive, send):
        try:
            async with asyncio.timeout(self.deadline_seconds):
                await super().__call__(scope, receive, send)
        finally:
            await self.download.close()


async def original_file_response(download):
    try:
        return OriginalFileResponse(download)
    except BaseException:
        await download.close()
        raise
