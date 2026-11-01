# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Borrowed private file evidence; callers retain native model and context-budget ownership."""

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import datetime

from koinon.knowledge.attachments.dtos import AttachmentHistorySummary


@dataclass(frozen=True, slots=True)
class AttachmentRef:
    id: str
    tenant_id: str
    thread_id: str
    subject: str
    sha256: str
    revision: int
    filename: str
    media_type: str
    kind: str
    size_bytes: int
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class AttachmentBudget:
    """The executor's native remaining-context check receives the exact proposed text."""

    fits_text: Callable[[str], Awaitable[bool]]
    allowed_media_types: frozenset[str] = frozenset()
    max_text_chars: int = 24000
    max_binary_bytes: int = 16 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class PrivateTextUnit:
    id: str
    text: str
    sha256: str
    page: int | None = None


@dataclass(frozen=True, slots=True)
class AttachmentContent:
    ref: AttachmentRef
    text: str | None = None
    data: bytes | None = None
    media_type: str | None = None
    complete: bool = False
    chunk_ids: tuple[str, ...] = ()
    total_chunks: int = 0
    warnings: tuple[str, ...] = ()
    text_units: tuple[PrivateTextUnit, ...] = ()


class ChatAttachmentAccess(ABC):
    @abstractmethod
    async def validate_selection(
        self, subject: str, tenant_id: str, thread_id: str, ids: Sequence[str]
    ) -> tuple[AttachmentRef, ...]:
        """Validate the complete ordered selection before reading bytes or opening model clients."""
        ...

    @abstractmethod
    async def content_for_model(
        self,
        subject: str,
        tenant_id: str,
        thread_id: str,
        refs: tuple[AttachmentRef, ...],
        *,
        question: str,
        budget: AttachmentBudget,
    ) -> tuple[AttachmentContent, ...]:
        """Return verified private data under both hard bounds and the caller's native context budget."""
        ...

    @abstractmethod
    async def authorize_evidence(
        self, subject: str, tenant_id: str, thread_id: str, refs: tuple[AttachmentRef, ...]
    ) -> None:
        """Revalidate current ownership, scope, expiry and immutable digests for replay/history/results."""
        ...

    @abstractmethod
    async def pin_selection(
        self,
        subject: str,
        tenant_id: str,
        thread_id: str,
        refs: tuple[AttachmentRef, ...],
        *,
        run_id: str,
        message_id: str,
    ) -> None:
        """Persist server-created ordered refs atomically with a caller's native run/message transaction."""
        ...

    @abstractmethod
    async def for_run(
        self, subject: str, tenant_id: str, thread_id: str, run_id: str
    ) -> tuple[AttachmentRef, ...]:
        """Load ordered immutable run refs and repeat current authorization."""
        ...

    @abstractmethod
    async def summaries_for_message(
        self, subject: str, tenant_id: str, thread_id: str, message_id: str
    ) -> tuple[AttachmentHistorySummary, ...]:
        """Return owner-only history metadata, including expired/removed badges, without reading bytes."""
        ...
