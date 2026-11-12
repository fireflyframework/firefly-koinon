# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Short, identity-pinned history reads under the requesting reader's authority."""

import asyncio
import base64
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime
from functools import wraps
from inspect import signature
from typing import TYPE_CHECKING

from pyfly.data.transaction import Propagation, current_unit_of_work, transactional
from sqlalchemy import String, and_, cast, func, literal, or_, select, true

from koinon.assistants.entities import ChatEvent, ChatMessage, ChatRun, ChatThread, ToolResult
from koinon.catalog.errors import AccessDenied
from koinon.integrations.content_sources.errors import SourceError
from koinon.integrations.content_sources.read_service import SourceReadOperation
from koinon.security.authority import primary_authority

if TYPE_CHECKING:
    from koinon.assistants.service import AssistantService


def unavailable():
    return AccessDenied("Conversation changed or is unavailable; reload it", code="CONVERSATION_READ_CHANGED")


@dataclass
class HistoryCapture:
    actor: str
    owner: str
    tenant: str
    thread_id: str
    identity: tuple
    operation: SourceReadOperation | None
    task: object = field(default_factory=asyncio.current_task)
    active: bool = True
    hydration_unit: object | None = None
    selection: dict = field(default_factory=dict)
    assistants: "AssistantService | None" = None

    @property
    def run_ids(self):
        return tuple(row[0] for row in self.identity[1])

    def assert_current(self):
        if not self.active or asyncio.current_task() is not self.task:
            raise unavailable()


_capture: ContextVar[HistoryCapture | None] = ContextVar("assistant_history_capture", default=None)


async def identities(session, owner, tenant, thread_id, selection=None):
    """Database-side hashes compare protected values without returning their bodies."""
    selection = selection or {}
    postgres = session.bind.dialect.name == "postgresql"

    def fingerprint(column):
        return func.sha256(func.convert_to(cast(column, String), "UTF8")) if postgres else literal(None)

    thread = (
        await session.execute(
            select(ChatThread.id, ChatThread.revision, ChatThread.scope, fingerprint(ChatThread.title)).where(
                ChatThread.id == thread_id,
                ChatThread.subject == owner,
                ChatThread.tenant_id == tenant,
                ChatThread.deleted_at.is_(None),
            )
        )
    ).first()
    if thread is None:
        raise unavailable()
    run_filter = [ChatRun.thread_id == thread_id, ChatRun.tenant_id == tenant]
    if "run_ids" in selection:
        run_filter.append(ChatRun.id.in_(selection["run_ids"]))
    elif "message_ids" in selection:
        run_filter.append(
            or_(
                ChatRun.message_id.in_(selection["message_ids"]),
                ChatRun.user_message_id.in_(selection["message_ids"]),
            )
        )
    runs = tuple(
        (
            await session.execute(
                select(
                    ChatRun.id,
                    ChatRun.sequence,
                    ChatRun.status,
                    ChatRun.access_token_id,
                    ChatRun.scope,
                    ChatRun.message_id,
                    ChatRun.user_message_id,
                    ChatRun.created_at,
                    fingerprint(ChatRun.reader_source_selection),
                )
                .where(*run_filter)
                .order_by(ChatRun.id)
                .limit(201)
            )
        ).all()
    )
    if len(runs) > 200:
        raise SourceError("size_exceeded")
    run_ids = tuple(row[0] for row in runs)
    message_ids = set(selection.get("message_ids", ()))
    message_ids.update(
        identifier
        for row in runs
        for identifier in ((row[6],) if selection.get("user_prompt_only") else (row[5], row[6]))
    )
    messages = tuple(
        (
            await session.execute(
                select(
                    ChatMessage.id,
                    ChatMessage.role,
                    ChatMessage.status,
                    fingerprint(ChatMessage.text),
                    fingerprint(ChatMessage.artifacts),
                    fingerprint(ChatMessage.answer_policy),
                    fingerprint(ChatMessage.citations),
                    fingerprint(ChatMessage.presentation),
                    ChatMessage.created_at,
                )
                .where(ChatMessage.thread_id == thread_id, ChatMessage.id.in_(message_ids))
                .order_by(ChatMessage.id)
                .limit(401)
            )
        ).all()
    )
    if not run_ids:
        return tuple(thread), runs, messages, (), ()
    if selection.get("user_prompt_only"):
        return tuple(thread), runs, messages, (), ()
    results = tuple(
        (
            await session.execute(
                select(
                    ToolResult.id,
                    ToolResult.run_id,
                    ToolResult.kind,
                    fingerprint(ToolResult.payload),
                    ToolResult.created_at,
                )
                .where(ToolResult.run_id.in_(run_ids))
                .order_by(ToolResult.id)
                .limit(2001)
            )
        ).all()
    )
    events = tuple(
        (
            await session.execute(
                select(ChatEvent.id, ChatEvent.run_id, ChatEvent.sequence, fingerprint(ChatEvent.data))
                .where(ChatEvent.run_id.in_(run_ids))
                .order_by(ChatEvent.id)
                .limit(10001)
            )
        ).all()
    )
    if len(messages) > 400 or len(results) > 2000 or len(events) > 10000:
        raise SourceError("size_exceeded")
    return tuple(thread), runs, messages, results, events


async def compare(capture, session):
    capture.assert_current()
    if (
        await identities(session, capture.owner, capture.tenant, capture.thread_id, capture.selection)
        != capture.identity
    ):
        raise unavailable()


def protected_hydration(function):
    """Storage-only outside a read; fixed admission is enforced by consumption entrypoints."""

    @wraps(function)
    async def wrapped(repository, *args, **kwargs):
        capture = _capture.get()
        if capture is None:
            async with primary_authority():
                return await function(repository, *args, **kwargs)
        capture.assert_current()
        arguments = signature(function).bind(repository, *args, **kwargs).arguments
        arguments = {**arguments, **arguments.get("filters", {})}
        allowed = {
            ChatThread: {capture.thread_id},
            ChatRun: set(capture.run_ids),
            ChatMessage: {row[0] for row in capture.identity[2]},
            ToolResult: {row[0] for row in capture.identity[3]},
            ChatEvent: {row[0] for row in capture.identity[4]},
        }
        for key, values in (
            ("thread_id", {capture.thread_id}),
            ("run_id", set(capture.run_ids)),
            ("id", allowed.get(repository._entity_type, set())),
        ):
            if key in arguments and arguments[key] not in values:
                raise unavailable()
        if "run_ids" in arguments and not set(arguments["run_ids"]).issubset(capture.run_ids):
            raise unavailable()
        if "message_ids" in arguments and not set(arguments["message_ids"]).issubset(allowed[ChatMessage]):
            raise unavailable()
        if function.__name__ == "find_all" and not {"id", "thread_id", "run_id"} & arguments.keys():
            raise unavailable()
        existing_unit = current_unit_of_work("primary")
        if capture.hydration_unit is not None:
            if existing_unit is not capture.hydration_unit:
                raise unavailable()
            return await function(repository, *args, **kwargs)
        if existing_unit is not None and not existing_unit.completed:
            raise unavailable()
        operation = capture.operation
        if operation is not None:
            await operation.release()
        fence = operation.read_fence() if operation is not None else primary_authority()
        async with fence:
            capture.hydration_unit = current_unit_of_work("primary")
            try:
                await compare(capture, repository._require_session())
                result = await function(repository, *args, **kwargs)
                await compare(capture, repository._require_session())
                return result
            finally:
                capture.hydration_unit = None

    # Declare the boundary so the native repository does not open an automatic unit
    # before source authorization. SUPPORTS itself opens no connection.
    return transactional(propagation=Propagation.SUPPORTS, read_only=True)(wrapped)


@asynccontextmanager
async def history_read(
    assistants,
    actor,
    tenant,
    *,
    thread_id=None,
    run_id=None,
    owner=None,
    local_only=False,
    operation=None,
    selection=None,
) -> AsyncIterator[HistoryCapture]:
    owner = owner or actor
    current = _capture.get()
    if current is not None:
        current.assert_current()
        if (current.actor, current.owner, current.tenant) != (actor, owner, tenant):
            raise unavailable()
        if thread_id is not None and current.thread_id != thread_id:
            raise unavailable()
        if run_id is not None and run_id not in current.run_ids:
            raise unavailable()
        yield current
        return
    async with primary_authority(fresh=True):
        session = assistants.threads._require_session()
        if run_id is not None:
            thread_id = await session.scalar(
                select(ChatRun.thread_id).where(ChatRun.id == run_id, ChatRun.tenant_id == tenant)
            )
        if run_id is not None:
            selection = {"run_ids": (run_id,)}
        if not isinstance(thread_id, str):
            raise unavailable()
        identity = await identities(session, owner, tenant, thread_id, selection)
    reader = assistants.source_reader.get() if assistants.source_reader is not None else None
    run_ids = tuple(row[0] for row in identity[1])
    if reader is None and run_ids and not (selection or {}).get("user_prompt_only"):
        from koinon.assistants.history.classification import local_conversation
        from koinon.integrations.content_sources.sync_entities import SourceImportedAsset

        async with primary_authority(fresh=True):
            session = assistants.threads._require_session()
            imported = await session.scalar(
                select(SourceImportedAsset.asset_id).where(SourceImportedAsset.tenant_id == tenant).limit(1)
            )
            if imported is not None and not await session.scalar(
                select(local_conversation(tenant, session))
                .select_from(ChatThread)
                .where(ChatThread.id == thread_id)
            ):
                raise SourceError("unavailable")
    if reader is not None and not (selection or {}).get("user_prompt_only"):
        if local_only:
            operation = await reader.begin(actor, tenant, [])
        for start in range(0, len(run_ids), 100):
            operation = await reader.runs(
                actor, tenant, run_ids[start : start + 100], operation=operation, owner=owner
            )
    capture = HistoryCapture(
        actor, owner, tenant, thread_id, identity, operation, selection=selection or {}, assistants=assistants
    )
    async with primary_authority(fresh=True):
        await compare(capture, assistants.threads._require_session())
    token = _capture.set(capture)
    try:
        yield capture
        if operation is not None:
            await operation.release()
        async with primary_authority(fresh=True):
            await compare(capture, assistants.threads._require_session())
    finally:
        capture.active = False
        _capture.reset(token)


def source_history(*, by="thread", transfer=False):
    def decorate(function):
        @wraps(function)
        async def wrapped(self, subject, tenant_id, identifier, *args, **kwargs):
            assistants = getattr(self, "assistants", self)
            reader = kwargs.get("reader_subject") if transfer else None
            selection = None
            if by == "thread":
                selection = await select_history(assistants, identifier, function.__name__, args, kwargs)
            async with history_read(
                assistants,
                reader or subject,
                tenant_id,
                owner=subject,
                selection=selection,
                **{f"{by}_id": identifier},
            ):
                return await function(self, subject, tenant_id, identifier, *args, **kwargs)

        # Public history reads suspend an ambient replica or write transaction before
        # candidate admission; every subsequent hydration owns a primary read unit.
        return transactional(propagation=Propagation.NOT_SUPPORTED, read_only=True, read_from_primary=True)(
            wrapped
        )

    return decorate


async def release_history():
    """Recheck authority immediately before sending captured excerpts to a model."""
    capture = _capture.get()
    if capture is None:
        raise unavailable()
    capture.assert_current()
    if capture.operation is not None:
        await capture.operation.release()
    if capture.assistants is None:
        raise unavailable()
    async with primary_authority(fresh=True):
        await compare(capture, capture.assistants.threads._require_session())


@asynccontextmanager
async def _title_model_boundary():
    """Keep a title's public read grant in its owning task while the model runs."""
    capture = _capture.get()
    if capture is None:
        raise unavailable()
    capture.assert_current()
    if capture.selection.get("user_prompt_only") is not True:
        raise unavailable()
    if capture.hydration_unit is not None or any(
        unit is not None and not unit.completed
        for unit in (current_unit_of_work(name) for name in ("primary", "canon", "structured"))
    ):
        raise unavailable()
    await release_history()
    token = _capture.set(None)
    try:
        yield
    finally:
        _capture.reset(token)
    await release_history()


def current_history_reader(owner):
    capture = _capture.get()
    if capture is None:
        return owner
    capture.assert_current()
    return capture.actor


async def select_history(assistants, thread_id, method, args, kwargs):
    """Choose bounded identities, never bodies, for the requested history operation."""
    from pyfly.kernel import InvalidRequestException

    if method in {"snapshot", "authorize_output"}:
        ids = tuple(args[0] if args else kwargs.get("message_ids", ()))
        if not 1 <= len(ids) <= 200 or len(set(ids)) != len(ids):
            raise InvalidRequestException("Choose distinct conversation messages", code="INVALID_SELECTION")
        return {"message_ids": ids}
    async with primary_authority(fresh=True):
        session = assistants.threads._require_session()
        if method == "propose":
            ids = tuple(
                await session.scalars(
                    select(ChatRun.id)
                    .where(ChatRun.thread_id == thread_id, ChatRun.status.in_(("completed", "running")))
                    .order_by(ChatRun.created_at.desc(), ChatRun.id.desc())
                    .limit(2)
                )
            )
            return {"run_ids": ids, "user_prompt_only": True}
        if method == "message_page":
            limit = kwargs.get("limit", 50)
            if type(limit) is not int or not 1 <= limit <= 100:
                raise InvalidRequestException("Choose a message limit from 1 to 100", code="INVALID_PAGE")
            statement = select(ChatMessage.id).where(ChatMessage.thread_id == thread_id)
            before = kwargs.get("before")
            if before:
                try:
                    if len(before) > 512:
                        raise ValueError()
                    stamp, identifier = json.loads(
                        base64.urlsafe_b64decode(before + "=" * (-len(before) % 4))
                    )
                    moment = datetime.fromisoformat(stamp)
                    if moment.tzinfo is None or not isinstance(identifier, str):
                        raise ValueError()
                except (ValueError, TypeError, KeyError) as error:
                    raise InvalidRequestException("Invalid message cursor", code="INVALID_CURSOR") from error
                statement = statement.where(
                    or_(
                        ChatMessage.created_at < moment,
                        and_(ChatMessage.created_at == moment, ChatMessage.id < identifier),
                    )
                )
            ids = tuple(
                await session.scalars(
                    statement.order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc()).limit(limit + 1)
                )
            )
            return {"message_ids": ids}
        # Metadata alone carries no implicit grant to any run or message body.
        return {"run_ids": ()}


def captured_ids(entity):
    capture = _capture.get()
    if capture is None:
        return None
    capture.assert_current()
    index = {ChatRun: 1, ChatMessage: 2, ToolResult: 3, ChatEvent: 4}[entity]
    return tuple(row[0] for row in capture.identity[index])


def captured_predicate(entity):
    identifiers = captured_ids(entity)
    return true() if identifiers is None else entity.id.in_(identifiers)


def has_history_capture():
    capture = _capture.get()
    if capture is None:
        return False
    capture.assert_current()
    return True
