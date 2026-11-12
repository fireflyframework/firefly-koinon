# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Safe provider failures without remote URLs, bodies or credential material."""

from typing import Literal

ErrorCode = Literal[
    "invalid_response",
    "invalid_identity",
    "invalid_cursor",
    "access_denied",
    "authority_changed",
    "reconnect_required",
    "unavailable",
    "resync_required",
    "throttled",
    "transport_error",
    "timeout",
    "unsupported",
    "size_exceeded",
    "version_changed",
    "unsafe_url",
    "scope_mismatch",
]


class SourceError(Exception):
    def __init__(
        self,
        code: ErrorCode,
        *,
        retry_after: int | None = None,
        http_status: int | None = None,
        definitive_read_denial: bool = False,
    ) -> None:
        self.code = code
        self.retry_after = retry_after
        self.http_status = http_status
        # A masked target read is not proof of deletion or complete enumeration.
        self.definitive_read_denial = definitive_read_denial
        super().__init__(code)
