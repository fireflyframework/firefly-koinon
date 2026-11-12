# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Short source-authorized queue units, separate from public history reads."""

import asyncio
import hashlib
import json
from contextlib import asynccontextmanager
from contextvars import ContextVar
from dataclasses import asdict, dataclass
from functools import wraps

from pydantic_core import to_jsonable_python
from pyfly.data.transaction import current_unit_of_work
from sqlalchemy import String, cast, func, select

from koinon.assistants.entities import (
    AgentConfiguration,
    ChatMessage,
    ChatRun,
    ChatThread,
    Provider,
    ToolResult,
)
from koinon.assistants.lifecycle import timestamp
from koinon.assistants.memory.entities import ChatMemoryManifest
from koinon.assistants.run_selection import confirm_selection, operation_for_run
from koinon.integrations.content_sources.errors import SourceError
from koinon.integrations.content_sources.lifecycle import _no_remote_unit
from koinon.integrations.content_sources.read_context import reader_source_scope, reader_source_snapshot
from koinon.security.authority import primary_authority


@dataclass
class _Admission:
    actor: str
    tenant: str
    run_id: str
    worker_id: str
    task: object
    unit: object
    assistants: object
    reader: object
    identity: tuple
    purpose: str
    write: bool
    capture: object
    capture_sha256: str | None
    memory_consumed: bool = False
    active: bool = True


_admission: ContextVar[_Admission | None] = ContextVar("assistant_queue_source_unit", default=None)


async def _local_without_reader(assistants, run_id):
    from koinon.integrations.content_sources.sync_entities import SourceImportedAsset

    async with primary_authority():
        imported = await assistants.runs._require_session().scalar(
            select(SourceImportedAsset.asset_id)
            .join(ChatRun, ChatRun.tenant_id == SourceImportedAsset.tenant_id)
            .where(ChatRun.id == run_id)
            .limit(1)
        )
    if imported is not None:
        raise SourceError("unavailable")


@asynccontextmanager
async def run_choices(assistants, run_id, worker_id):
    reader = assistants.source_reader.get() if assistants.source_reader is not None else None
    if reader is None:
        await _local_without_reader(assistants, run_id)
        yield
        return
    async with primary_authority(fresh=True):
        row = (await _identity(assistants, run_id, worker_id))[0]
    _, selection = await operation_for_run(reader, row.subject, row.tenant_id, row.reader_source_selection)
    with (
        reader_source_scope(row.subject, row.tenant_id, selection.connections),
        reader_source_snapshot(row.subject, row.tenant_id, selection.snapshot()),
    ):
        yield


def admitted_run(actor, tenant, identifiers):
    """A queue admission covers only its exact run, task, and live primary unit."""
    value = _admission.get()
    if value is None:
        return False
    if (
        not value.active
        or value.task is not asyncio.current_task()
        or value.unit is not current_unit_of_work("primary")
        or (actor, tenant, tuple(identifiers)) != (value.actor, value.tenant, (value.run_id,))
    ):
        raise SourceError("authority_changed")
    return True


async def consume_memory_admission(actor, tenant, identifiers, *, captures=(), reader=None):
    if not admitted_run(actor, tenant, identifiers):
        return False
    value = _admission.get()
    if value is None:
        raise SourceError("authority_changed")
    if (
        captures
        or reader is not value.reader
        or value.memory_consumed
        or value.purpose
        not in {
            "release_answer",
            "validate_answer_plan",
            "authority",
            "fact_pool",
            "capture_limits",
            "citations",
        }
    ):
        raise SourceError("authority_changed")
    if await _identity(value.assistants, value.run_id, value.worker_id) != value.identity:
        raise SourceError("authority_changed")
    value.memory_consumed = True
    return True


def nested_memory_checked(assistants, run_id, worker_id):
    value = _admission.get()
    if value is None:
        return False
    admitted_run(value.actor, value.tenant, (run_id,))
    if value.assistants is not assistants or value.worker_id != worker_id:
        raise SourceError("authority_changed")
    return value.memory_consumed and value.purpose in {"release_answer", "validate_answer_plan"}


def _capture_digest(capture):
    if capture is None:
        return None
    value = asdict(capture)
    value["sources"] = [item.model_dump(mode="json") for item in capture.sources]
    value["rlm_tools"] = (
        [item.model_dump(mode="json") for item in capture.rlm_tools]
        if capture.rlm_tools is not None
        else None
    )
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


async def _identity(assistants, run_id, worker_id):
    session = assistants.runs._require_session()
    row = (
        await session.execute(
            select(
                ChatRun.id,
                ChatRun.tenant_id,
                ChatRun.thread_id,
                ChatRun.scope,
                ChatRun.sequence,
                ChatRun.status,
                ChatRun.worker_id,
                ChatRun.lease_until,
                ChatRun.attempts,
                ChatRun.access_token_id,
                ChatRun.user_message_id,
                ChatRun.message_id,
                ChatThread.subject,
                ChatThread.revision,
                ChatRun.reader_source_selection,
                ChatRun.agent_id,
                ChatRun.agent_revision,
                ChatRun.provider_revision,
                AgentConfiguration.revision.label("current_agent_revision"),
                AgentConfiguration.enabled.label("agent_enabled"),
                AgentConfiguration.provider_id,
                Provider.revision.label("current_provider_revision"),
                Provider.enabled.label("provider_enabled"),
            )
            .join(ChatThread, ChatThread.id == ChatRun.thread_id)
            .join(AgentConfiguration, AgentConfiguration.id == ChatRun.agent_id)
            .join(Provider, Provider.id == AgentConfiguration.provider_id)
            .where(
                ChatRun.id == run_id,
                ChatThread.deleted_at.is_(None),
                AgentConfiguration.tenant_id == ChatRun.tenant_id,
                Provider.tenant_id == ChatRun.tenant_id,
            )
        )
    ).first()
    if (
        row is None
        or row.status != "running"
        or row.worker_id != worker_id
        or (row.lease_until is None or row.lease_until <= timestamp())
    ):
        from pyfly.kernel import ConflictException

        raise ConflictException("Worker no longer owns this answer", code="RUN_LEASE_LOST")
    if (
        not row.agent_enabled
        or not row.provider_enabled
        or row.current_agent_revision != row.agent_revision
        or row.current_provider_revision != row.provider_revision
    ):
        from pyfly.kernel import ConflictException

        raise ConflictException("Agent configuration changed", code="CONFIGURATION_CHANGED")

    def fingerprint(column):
        return func.sha256(func.convert_to(cast(column, String), "UTF8"))

    results = tuple(
        (
            await session.execute(
                select(ToolResult.id, fingerprint(ToolResult.payload))
                .where(ToolResult.run_id == run_id)
                .order_by(ToolResult.id)
                .limit(2001)
            )
        ).all()
    )
    memory = tuple(
        (
            await session.execute(
                select(ChatMemoryManifest.id, fingerprint(ChatMemoryManifest.manifest_json))
                .where(ChatMemoryManifest.run_id == run_id)
                .order_by(ChatMemoryManifest.id)
                .limit(101)
            )
        ).all()
    )
    messages = tuple(
        (
            await session.execute(
                select(
                    ChatMessage.id,
                    fingerprint(ChatMessage.text),
                    fingerprint(ChatMessage.artifacts),
                    fingerprint(ChatMessage.citations),
                    fingerprint(ChatMessage.answer_policy),
                    fingerprint(ChatMessage.presentation),
                )
                .where(ChatMessage.id.in_((row.user_message_id, row.message_id)))
                .order_by(ChatMessage.id)
            )
        ).all()
    )
    if len(results) > 2000 or len(memory) > 100:
        raise SourceError("size_exceeded")
    return row, results, memory, messages


async def _lock_run(assistants, row):
    session = assistants.runs._require_session()
    for entity, predicate in (
        (ChatThread, ChatThread.id == row.thread_id),
        (ChatRun, ChatRun.id == row.id),
        (ChatMessage, ChatMessage.id.in_((row.user_message_id, row.message_id))),
        (ToolResult, ToolResult.run_id == row.id),
    ):
        await session.execute(select(entity.id).where(predicate).order_by(entity.id).with_for_update())
    # Memory inserts acquire FK KEY SHARE on the locked run/generation parents.
    # Runtime roles have SELECT/INSERT only; row locking must not require UPDATE.


@asynccontextmanager
async def _proof_scope(assistants, row, enabled):
    if not enabled:
        yield
        return
    from koinon.answers.release_proofs import _publication_scope

    async with _publication_scope(assistants, row):
        yield


@asynccontextmanager
async def run_source_unit(
    assistants, run_id, worker_id, *, write=False, capture=None, purpose="read", publish_proof=False
):
    existing = _admission.get()
    if existing is not None:
        if (existing.run_id, existing.worker_id) != (run_id, worker_id):
            raise SourceError("authority_changed")
        admitted_run(existing.actor, existing.tenant, (run_id,))
        if (
            purpose != "fact_pool"
            or existing.purpose not in {"release_answer", "validate_answer_plan"}
            or capture is not None
            or write
            and not existing.write
        ):
            raise SourceError("authority_changed")
        yield
        return
    reader = assistants.source_reader.get() if assistants.source_reader is not None else None
    if reader is None:
        if not publish_proof:
            await _local_without_reader(assistants, run_id)
            yield
            return
        if not write or purpose != "release_answer":
            raise SourceError("authority_changed")
        _no_remote_unit()
        async with primary_authority(read_only=False):
            await _local_without_reader(assistants, run_id)
            identity = await _identity(assistants, run_id, worker_id)
            row = identity[0]
            await _lock_run(assistants, row)
            if await _identity(assistants, run_id, worker_id) != identity:
                raise SourceError("authority_changed")
            value = _Admission(
                row.subject,
                row.tenant_id,
                run_id,
                worker_id,
                asyncio.current_task(),
                current_unit_of_work("primary"),
                assistants,
                None,
                identity,
                purpose,
                write,
                capture,
                _capture_digest(capture),
            )
            token = _admission.set(value)
            try:
                async with _proof_scope(assistants, row, True):
                    yield
                if _capture_digest(capture) != value.capture_sha256:
                    raise SourceError("authority_changed")
            finally:
                value.active = False
                _admission.reset(token)
        return
    _no_remote_unit()
    capture_sha256 = _capture_digest(capture)
    async with primary_authority(fresh=True):
        identity = await _identity(assistants, run_id, worker_id)
    row = identity[0]
    operation, selection = await operation_for_run(
        reader, row.subject, row.tenant_id, row.reader_source_selection
    )
    operation = await reader.runs(row.subject, row.tenant_id, (run_id,), operation=operation)
    if row.scope.get("asset_ids"):
        operation = await reader.entries(
            row.subject, row.tenant_id, row.scope["asset_ids"], operation=operation
        )
    if capture is not None:
        operation = await reader.sources(row.subject, row.tenant_id, capture.sources, operation=operation)
    async with operation.local_fence() if write else operation.read_fence():
        if write:
            await _lock_run(assistants, row)
        await confirm_selection(reader, row.subject, row.tenant_id, selection, local=True)
        if await _identity(assistants, run_id, worker_id) != identity:
            raise SourceError("authority_changed")
        if _capture_digest(capture) != capture_sha256:
            raise SourceError("authority_changed")
        value = _Admission(
            row.subject,
            row.tenant_id,
            run_id,
            worker_id,
            asyncio.current_task(),
            current_unit_of_work("primary"),
            assistants,
            reader,
            identity,
            purpose,
            write,
            capture,
            capture_sha256,
        )
        token = _admission.set(value)
        try:
            with (
                reader_source_scope(row.subject, row.tenant_id, selection.connections),
                reader_source_snapshot(row.subject, row.tenant_id, selection.snapshot()),
            ):
                async with _proof_scope(assistants, row, publish_proof):
                    yield
            if _capture_digest(capture) != capture_sha256:
                raise SourceError("authority_changed")
            released_identity = await _identity(assistants, run_id, worker_id) if write else identity
        finally:
            value.active = False
            _admission.reset(token)
    await operation.release()
    await confirm_selection(reader, row.subject, row.tenant_id, selection)
    async with primary_authority(fresh=True):
        if await _identity(assistants, run_id, worker_id) != released_identity:
            raise SourceError("authority_changed")


def queue_source_unit(function):
    @wraps(function)
    async def wrapped(self, run_id, worker_id, *args, **kwargs):
        def input_digest():
            return hashlib.sha256(
                json.dumps(
                    to_jsonable_python((args, kwargs)),
                    sort_keys=True,
                    allow_nan=False,
                ).encode()
            ).hexdigest()

        prepared = input_digest()
        async with run_source_unit(
            self.assistants,
            run_id,
            worker_id,
            write=function.__name__ in {"evidence", "release_answer", "citations"},
            capture=kwargs.get("capture"),
            purpose=function.__name__,
            publish_proof=(function.__name__ == "release_answer" and self.proof_publisher() is not None),
        ):
            if input_digest() != prepared:
                raise SourceError("authority_changed")
            result = await function(self, run_id, worker_id, *args, **kwargs)
            if input_digest() != prepared:
                raise SourceError("authority_changed")
            return result

    return wrapped
