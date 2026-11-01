# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Own the bounded spool and fresh authorization cuts for a streamed original."""

import math
import re
import tempfile
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from flycanon.core.services.sources.lineage.dtos import OriginalFileReceipt
from pyfly.container import service
from pyfly.data.transaction import Isolation, Propagation, TransactionTemplate, current_unit_of_work
from pyfly.kernel import ConflictException, RateLimitException
from pyfly.resilience import Bulkhead
from pyfly.security.context import SecurityContext
from pyfly.security.context_holder import SecurityContextHolder

from koinon.catalog.errors import AccessDenied
from koinon.knowledge.document_history.ports import DocumentHistoryPort
from koinon.knowledge.service import KnowledgeFacade
from koinon.security.authority import PRIMARY_POLICY_UNIT
from koinon.storage.scratch import ScratchAdmission


@dataclass
class OriginalDownload:
    path: Path
    receipt: OriginalFileReceipt
    guard: Callable[[], Awaitable[None]]
    close: Callable[[], Awaitable[None]]


@service(name="knowledge.original_downloads")
class OriginalDownloads:
    def __init__(self, knowledge: KnowledgeFacade, history: DocumentHistoryPort, scratch: ScratchAdmission):
        self.knowledge, self.history = knowledge, history
        self.scratch = scratch
        self.slots = Bulkhead(max_concurrent=1)

    @staticmethod
    def _receipt(receipt):
        if (
            type(receipt.bytes) is not int
            or not 1 <= receipt.bytes <= 128 * 1024**2
            or re.fullmatch(r"[0-9a-f]{64}", receipt.sha256) is None
            or re.fullmatch(r"[0-9a-f]{64}", receipt.anchor) is None
            or (
                receipt.filename is not None
                and (not isinstance(receipt.filename, str) or len(receipt.filename) > 512)
            )
        ):
            raise ValueError("A bounded verified original file receipt is required")

    async def _scope(self, subject, tenant, document, context):
        if (
            not context.is_authenticated
            or f"{context.attributes.get('iss')}|{context.attributes.get('sub')}" != subject
        ):
            raise AccessDenied("Verified original read identity is unavailable", code="AUTH_REQUIRED")
        expires = context.attributes.get("exp")
        if expires is not None and (
            isinstance(expires, bool)
            or not isinstance(expires, int | float)
            or not math.isfinite(expires)
            or expires <= datetime.now(UTC).timestamp()
        ):
            raise AccessDenied("Original read credential expired", code="TOKEN_UNAVAILABLE")
        with SecurityContextHolder.using(context):
            async with TransactionTemplate(
                "primary",
                name=PRIMARY_POLICY_UNIT,
                propagation=Propagation.REQUIRES_NEW,
                isolation=Isolation.SERIALIZABLE,
                read_only=True,
                read_from_primary=True,
            ).transaction():
                chain, binding = await self.knowledge.authorize_document_read(subject, tenant, document)
                return (chain[1].id, binding.native_workspace_id, binding.native_id)

    async def open(self, subject, tenant, document, *, context: SecurityContext, source_version_id=None):
        if current_unit_of_work("primary") is not None:
            raise ConflictException(
                "Original download cannot retain an ambient policy snapshot",
                code="ORIGINAL_AMBIENT_TRANSACTION",
            )
        if self.slots.available_slots < 1:
            raise RateLimitException(
                "An original download is already in progress", code="ORIGINAL_DOWNLOAD_BUSY"
            )
        await self.slots.acquire()
        temporary = None
        closed = False
        scratch_reservation = None

        async def close():
            nonlocal closed
            if closed:
                return
            closed = True
            try:
                if temporary is not None:
                    temporary.cleanup()
            finally:
                if scratch_reservation is not None:
                    scratch_reservation.close()
                self.slots.release()

        try:
            before = await self._scope(subject, tenant, document, context)
            native = dict(actor=subject, tenant_id=tenant, workspace_id=before[1], source_id=before[2])
            with SecurityContextHolder.using(context):
                expected = await self.history.original_identity(source_version_id=source_version_id, **native)
            self._receipt(expected)
            scratch_reservation = self.scratch.reserve(2 * expected.bytes)
            temporary = tempfile.TemporaryDirectory(prefix="koinon-original-download-")
            path = Path(temporary.name) / "original"
            with SecurityContextHolder.using(context):
                receipt = await self.history.original_file(
                    path=path, max_bytes=128 * 1024**2, source_version_id=source_version_id, **native
                )
            self._receipt(receipt)
            if receipt != expected:
                raise AccessDenied(
                    "Original identity changed during preparation", code="DOCUMENT_SCOPE_MISMATCH"
                )
            if source_version_id is not None and receipt.version_id != source_version_id:
                raise AccessDenied(
                    "Original version differs from the requested identity", code="DOCUMENT_SCOPE_MISMATCH"
                )

            async def guard():
                with SecurityContextHolder.using(context):
                    observed = await self.history.original_identity(
                        source_version_id=source_version_id, **native
                    )
                if observed != receipt:
                    raise AccessDenied("Original identity changed", code="DOCUMENT_SCOPE_MISMATCH")
                current = await self._scope(subject, tenant, document, context)
                if current != before:
                    raise AccessDenied("Document binding changed", code="DOCUMENT_SCOPE_MISMATCH")

            await guard()
            return OriginalDownload(path, receipt, guard, close)
        except BaseException:
            await close()
            raise
