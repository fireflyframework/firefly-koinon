# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Trusted attestations of the original persisted answer verifier.

The private capability is scoped to the source-authorized queue transaction.
Database publisher credentials are a separate, mandatory trust boundary.
"""

import asyncio
from contextlib import asynccontextmanager
from contextvars import ContextVar
from dataclasses import dataclass

from pydantic_core import to_jsonable_python
from pyfly.data.transaction import current_unit_of_work
from pyfly.kernel import ConflictException
from sqlalchemy import func, select, text
from sqlalchemy.orm import load_only

from koinon.answers.contexts import active_result_rows, current_release_context
from koinon.answers.receipts import AnswerRelease, digest, verified_release
from koinon.answers.release_proof_repository import AnswerReleaseProofRepository
from koinon.assistants.entities import ChatEvent, ChatMessage, ChatRun, ToolResult
from koinon.assistants.lifecycle import identifier


class PublicationRejected(ConflictException):
    def __init__(self):
        super().__init__("Answer publication could not be verified", code="ANSWER_PROOF_REJECTED")


class InvalidRetainedRelease(PublicationRejected):
    """The original persisted verifier rejects this exact retained release."""


class ProjectionUnavailable(PublicationRejected):
    """Integrity could not be classified within the bounded projection contract."""


@dataclass(eq=False)
class _Publication:
    task: object
    unit: object
    assistants: object
    run_id: str
    worker_id: str
    release_id: str
    identity: tuple
    generation: tuple | None
    reset: int | None
    active: bool = True
    used: bool = False


_publication: ContextVar[_Publication | None] = ContextVar("answer_release_publication", default=None)


def _require_publication(candidate, release_id):
    unit = current_unit_of_work("primary")
    if (
        not isinstance(candidate, _Publication)
        or candidate is not _publication.get()
        or not candidate.active
        or candidate.used
        or candidate.task is not asyncio.current_task()
        or candidate.unit is not unit
        or unit is None
        or unit.completed
        or unit.read_only
        or candidate.release_id != release_id
    ):
        raise PublicationRejected()
    return candidate


def current_publication():
    value = _publication.get()
    return _require_publication(value, value.release_id if value is not None else None)


def _run_binding(row):
    # Event append changes sequence inside publication; every authority identity stays fixed.
    return tuple(
        (key, digest(to_jsonable_python(value))) for key, value in row._mapping.items() if key != "sequence"
    )


async def _selector(session, run_id):
    reset = await session.scalar(
        select(func.max(ChatEvent.sequence)).where(
            ChatEvent.run_id == run_id, ChatEvent.type == "message_reset"
        )
    )
    generations = (
        await session.execute(
            select(
                ToolResult.id,
                ToolResult.payload["generation"]["start_sequence"].as_integer().label("start_sequence"),
                ToolResult.created_at,
            )
            .where(ToolResult.run_id == run_id, ToolResult.kind == "generation")
            .limit(2001)
        )
    ).all()
    if len(generations) > 2000:
        raise PublicationRejected()
    eligible = [row for row in generations if reset is None or row.start_sequence >= reset]
    current = max(eligible, key=lambda row: (row.start_sequence, row.created_at)) if eligible else None
    return ((current.id, current.start_sequence, current.created_at) if current else None), reset


@asynccontextmanager
async def _publication_scope(assistants, row):
    from koinon.assistants.run_sources import _admission, admitted_run

    admission = _admission.get()
    if (
        admission is None
        or admission.purpose != "release_answer"
        or not admission.write
        or admission.assistants is not assistants
        or _publication.get() is not None
        or not admitted_run(row.subject, row.tenant_id, (row.id,))
    ):
        raise PublicationRejected()
    generation, reset = await _selector(assistants.runs._require_session(), row.id)
    value = _Publication(
        asyncio.current_task(),
        current_unit_of_work("primary"),
        assistants,
        row.id,
        row.worker_id,
        identifier(),
        _run_binding(row),
        generation,
        reset,
    )
    token = _publication.set(value)
    try:
        _require_publication(value, value.release_id)
        yield value
    finally:
        value.active = False
        _publication.reset(token)


async def verify_persisted_release(session, capture, *, release_id=None):
    """Run the original Python verifier over bounded, authoritative persisted values."""
    release_id = capture.header.release_result_id if capture is not None else release_id
    identity = (
        await session.execute(
            text(
                "SELECT u.id AS run_id,u.tenant_id,u.thread_id,u.message_id,u.user_message_id,"
                "octet_length(u.reader_source_selection::text) AS selection_bytes "
                "FROM public.koinon_chat_tool_results r JOIN public.koinon_chat_runs u ON u.id=r.run_id "
                "JOIN public.koinon_chat_threads t ON t.id=u.thread_id AND t.tenant_id=u.tenant_id "
                "WHERE r.id=:release AND r.kind='answer_release'"
            ),
            {"release": release_id},
        )
    ).first()
    if identity is None:
        raise InvalidRetainedRelease()
    for entity, maximum in ((ToolResult, 2000), (ChatEvent, 10000)):
        count = await session.scalar(
            select(func.count()).select_from(
                select(entity.id).where(entity.run_id == identity.run_id).limit(maximum + 1).subquery()
            )
        )
        if count > maximum:
            raise ProjectionUnavailable()
    size = await session.scalar(
        text(
            "SELECT coalesce((SELECT sum(octet_length(payload::text)) "
            "FROM public.koinon_chat_tool_results WHERE run_id=:run),0)+"
            "coalesce(octet_length(m.text),0)+coalesce(octet_length(m.citations::text),0)+"
            "coalesce(octet_length(m.artifacts::text),0)+coalesce(octet_length(m.answer_policy::text),0) "
            "FROM public.koinon_chat_messages m WHERE m.id=:message"
        ),
        {"run": identity.run_id, "message": identity.message_id},
    )
    if size is None:
        raise InvalidRetainedRelease()
    if size > 16777216 or (identity.selection_bytes or 0) > 131072:
        raise ProjectionUnavailable()
    from koinon.assistants.run_selection import stored_selection
    from koinon.integrations.content_sources.errors import SourceError

    selection = await session.scalar(
        select(ChatRun.reader_source_selection).where(ChatRun.id == identity.run_id)
    )
    try:
        stored_selection(selection)
    except SourceError:
        raise ProjectionUnavailable() from None
    message = await session.scalar(
        select(ChatMessage)
        .where(ChatMessage.id == identity.message_id)
        .options(
            load_only(
                ChatMessage.id,
                ChatMessage.thread_id,
                ChatMessage.role,
                ChatMessage.text,
                ChatMessage.citations,
                ChatMessage.artifacts,
                ChatMessage.answer_policy,
                raiseload=True,
            )
        )
        .execution_options(populate_existing=True)
    )
    rows = list(
        (
            await session.scalars(
                select(ToolResult)
                .where(ToolResult.run_id == identity.run_id)
                .order_by(ToolResult.id)
                .limit(2001)
                .execution_options(populate_existing=True)
            )
        ).all()
    )
    if (
        message is None
        or len(rows) > 2000
        or message.thread_id != identity.thread_id
        or message.role != "assistant"
    ):
        raise InvalidRetainedRelease()
    reset = await session.scalar(
        select(func.max(ChatEvent.sequence)).where(
            ChatEvent.run_id == identity.run_id, ChatEvent.type == "message_reset"
        )
    )
    try:
        active = active_result_rows(rows, reset=reset, run_id=identity.run_id, artifacts=message.artifacts)
        target = next((row for row in active if row.id == release_id and row.kind == "answer_release"), None)
        if target is None or not current_release_context(target.payload, reset or 0):
            raise InvalidRetainedRelease()
        receipt = verified_release(message, active)
        expected = AnswerRelease.model_validate(target.payload.get("release"))
        if (
            receipt is None
            or receipt != expected
            or receipt.tenant_id != identity.tenant_id
            or receipt.run_id != identity.run_id
            or receipt.message_id != identity.message_id
        ):
            raise InvalidRetainedRelease()
    except (ValueError, TypeError, KeyError, AttributeError):
        raise InvalidRetainedRelease() from None
    if (
        sum(
            row.kind == "answer_release" and row.payload.get("release") == target.payload.get("release")
            for row in active
        )
        != 1
    ):
        raise ProjectionUnavailable()
    if capture is not None:
        header = capture.header
        if (
            receipt.generation_id != header.generation_id
            or (reset or 0) != header.reset_sequence
            or digest(receipt.model_dump(mode="json")) != header.canonical_seal_sha256
            or (
                identity.run_id,
                identity.tenant_id,
                identity.thread_id,
                identity.message_id,
                identity.user_message_id,
            )
            != (header.run_id, header.tenant_id, header.thread_id, header.message_id, header.user_message_id)
        ):
            raise ProjectionUnavailable()
    return receipt


class AnswerReleaseProofPublisher:
    def __init__(self, repository: AnswerReleaseProofRepository):
        self.repository = repository

    async def publish_verified_release(self, admission, release_id):
        value = _require_publication(admission, release_id)
        value.used = True
        from koinon.assistants.run_sources import _identity

        session = self.repository._require_session()
        if session is not value.assistants.runs._require_session():
            raise PublicationRejected()
        await session.flush()
        row = (await _identity(value.assistants, value.run_id, value.worker_id))[0]
        if _run_binding(row) != value.identity:
            raise PublicationRejected()
        generation, reset = await _selector(session, value.run_id)
        if (generation, reset) != (value.generation, value.reset):
            raise PublicationRejected()
        capture = await self.repository.capture(release_id)
        if capture is None:
            raise PublicationRejected()
        await verify_persisted_release(session, capture)
        return await self.repository.publish(capture, worker_id=value.worker_id, attempt=row.attempts)
