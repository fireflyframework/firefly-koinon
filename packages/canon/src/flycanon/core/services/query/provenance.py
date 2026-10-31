# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Optional caller-owned pre-model document receipts; no standalone runtime policy."""

from asyncio import Task, current_task, get_running_loop, run_coroutine_threadsafe
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from functools import wraps
from threading import RLock, get_ident
from typing import Any

from pyfly.kernel import ServiceUnavailableException


@dataclass
class Observation:
    observer: Any
    tenant_id: str
    workspace_id: str
    actor: str
    task: Task[Any]
    active: bool = True
    threads: set = field(default_factory=set)
    lock: Any = field(default_factory=RLock)
    source_ids: set = field(default_factory=set)
    knowledge_ids: set[str] = field(default_factory=set)
    allowed_sources: frozenset[str] | None = None
    loop: Any = None
    authorized: bool = False


_current: ContextVar[Observation | None] = ContextVar("document_evidence", default=None)


@contextmanager
def observe(observer, *, tenant_id, workspace_id, actor, dataset_id="", source_ids=None):
    task = current_task()
    if task is None:
        raise ServiceUnavailableException("A request-owned task is required", code="EVIDENCE_UNAVAILABLE")
    scope = Observation(observer, tenant_id, str(workspace_id), actor, task)
    scope.loop = get_running_loop()
    scope.allowed_sources = frozenset(map(str, source_ids)) if source_ids is not None else None
    token = _current.set(scope)
    try:
        yield
    finally:
        scope.active = False
        _current.reset(token)


def current():
    scope = _current.get()
    if scope is not None:
        try:
            task = current_task()
        except RuntimeError:
            task = None
        if not scope.active or (task is not scope.task and get_ident() not in scope.threads):
            raise ServiceUnavailableException(
                "Native provenance scope has expired", code="EVIDENCE_UNAVAILABLE"
            )
    return scope


async def before_model(stage, prompt, hits, *, tenant_id, workspace_id):
    scope = current()
    if scope is None:
        from flycanon.core.agents.model_bindings import current_scope

        binding = current_scope()
        if binding is not None and binding.required:
            raise ServiceUnavailableException(
                "Native provenance observer is required", code="EVIDENCE_UNAVAILABLE"
            )
        return
    if (tenant_id, str(workspace_id)) != (scope.tenant_id, scope.workspace_id):
        raise ServiceUnavailableException("Native provenance scope mismatch", code="EVIDENCE_UNAVAILABLE")
    await scope.observer.authorize()
    scope.observer.document_model(stage, prompt, hits, scope)


def worker(operation):
    @wraps(operation)
    def leased(*args, **kwargs):
        scope = _current.get()
        if scope is None:
            return operation(*args, **kwargs)
        if not scope.active:
            raise ServiceUnavailableException(
                "Native provenance scope has expired", code="EVIDENCE_UNAVAILABLE"
            )
        with scope.lock:
            scope.threads.add(get_ident())
        try:
            return operation(*args, **kwargs)
        finally:
            with scope.lock:
                scope.threads.discard(get_ident())

    return leased


async def _authorize(scope):
    from flycanon.core.services.retrieval.curated_corpus import authorize_rlm

    await scope.observer.authorize()
    await authorize_rlm(scope)


async def authorize():
    scope = current()
    if scope is not None:
        await _authorize(scope)
        if current() is not scope:
            raise ServiceUnavailableException(
                "Native provenance scope has expired", code="EVIDENCE_UNAVAILABLE"
            )
        scope.authorized = True


def authority(scope):
    try:
        task = current_task()
    except RuntimeError:
        task = None
    if task is scope.task:
        if not scope.authorized:
            raise ServiceUnavailableException(
                "Current canonical provenance authority is required", code="EVIDENCE_UNAVAILABLE"
            )
        scope.authorized = False
    else:
        future = run_coroutine_threadsafe(_authorize(scope), scope.loop)
        try:
            future.result(timeout=10)
            current()
        except BaseException:
            future.cancel()
            raise


def read(source_id, pages):
    scope = current()
    if scope is not None:
        with scope.lock:
            authority(scope)
            scope.source_ids.add(str(source_id))
            scope.observer.document_sync("rlm.read", "\n".join(pages), (str(source_id),), scope)


def execution_read(meta, read):
    """Admit an exact recorded view before an execution helper releases its content."""
    scope = current()
    hook = getattr(scope.observer, "document_execution_read", None) if scope is not None else None
    if scope is None or not callable(hook):
        raise ServiceUnavailableException(
            "The exact document execution observer is required", code="EVIDENCE_UNAVAILABLE"
        )
    with scope.lock:
        hook(meta, read, scope)


def model(stage, content):
    scope = current()
    if scope is not None:
        with scope.lock:
            authority(scope)
            if not scope.source_ids and not scope.knowledge_ids:
                raise ServiceUnavailableException(
                    "Native document provenance is missing", code="EVIDENCE_UNAVAILABLE"
                )
            if scope.source_ids:
                scope.observer.document_sync(stage, content, tuple(sorted(scope.source_ids)), scope)
            if scope.knowledge_ids:
                hook = getattr(scope.observer, "knowledge_sync", None)
                if not callable(hook):
                    raise ServiceUnavailableException(
                        "Knowledge provenance observer is required", code="EVIDENCE_UNAVAILABLE"
                    )
                hook(stage, content, tuple(sorted(scope.knowledge_ids)), scope)


def tool(receipt):
    """Persist an actual provider action separately from document/model reads."""
    scope = current()
    if scope is not None:
        hook = getattr(scope.observer, "document_tool", None)
        if not callable(hook):
            raise ServiceUnavailableException(
                "Native tool provenance observer is required",
                code="EVIDENCE_UNAVAILABLE",
            )
        with scope.lock:
            authority(scope)
            hook(receipt, scope)


def before_tool():
    scope = current()
    if scope is not None:
        hook = getattr(scope.observer, "document_tool_start", None)
        if not callable(hook):
            raise ServiceUnavailableException(
                "Native tool admission observer is required",
                code="EVIDENCE_UNAVAILABLE",
            )
        with scope.lock:
            authority(scope)
            hook(scope)


async def corpus(docs):
    scope = current()
    if scope is None:
        from flycanon.core.agents.model_bindings import current_scope

        binding = current_scope()
        if binding is not None and binding.required:
            raise ServiceUnavailableException(
                "Native provenance observer is required", code="EVIDENCE_UNAVAILABLE"
            )
        return None
    from flycanon.core.services.query.rlm.context_index import metadata_index
    from flycanon.interfaces.dtos.knowledge_corpus import KnowledgeVersionMeta

    await authorize()
    try:
        entries = []
        for key in docs:
            source = docs.resolve(key)
            if type(source) is KnowledgeVersionMeta:
                hook = getattr(scope.observer, "knowledge_corpus_meta", None)
                if not callable(hook) or (source.tenant_id, source.workspace_id) != (
                    scope.tenant_id,
                    scope.workspace_id,
                ):
                    raise ServiceUnavailableException(
                        "Knowledge corpus provenance is required", code="EVIDENCE_UNAVAILABLE"
                    )
                hook(source, scope)
                scope.knowledge_ids.add(source.item_id)
                entries.append({"filing_id": key, "filename": None, "title": source.title})
                continue
            if (
                source is None
                or not source.source_id
                or (source.tenant_id, source.workspace_id) != (scope.tenant_id, scope.workspace_id)
                or scope.allowed_sources is not None
                and str(source.source_id) not in scope.allowed_sources
            ):
                raise ServiceUnavailableException(
                    "Native corpus provenance is missing", code="EVIDENCE_UNAVAILABLE"
                )
            scope.source_ids.add(str(source.source_id))
            scope.observer.document_origin(str(source.source_id), source.filename)
            entries.append({"filing_id": key, "filename": source.filename, "title": source.title})
        context = metadata_index(entries)
        if scope.source_ids:
            scope.observer.document_sync("rlm.corpus", context, tuple(sorted(scope.source_ids)), scope)
        if scope.knowledge_ids:
            hook = getattr(scope.observer, "knowledge_sync", None)
            if not callable(hook):
                raise ServiceUnavailableException(
                    "Knowledge corpus observer is required", code="EVIDENCE_UNAVAILABLE"
                )
            hook("rlm.corpus", context, tuple(sorted(scope.knowledge_ids)), scope)
        return context
    finally:
        scope.authorized = False


def knowledge_execution_read(meta, read):
    scope = current()
    hook = getattr(scope.observer, "knowledge_execution_read", None) if scope is not None else None
    if scope is None or not callable(hook):
        raise ServiceUnavailableException(
            "Knowledge execution observer is required", code="EVIDENCE_UNAVAILABLE"
        )
    with scope.lock:
        hook(meta, read, scope)


async def database(session, rows):
    scope = current()
    if scope is None:
        return
    from sqlalchemy import text

    engine = session.get_bind().dialect.name
    identity = (
        (
            await session.execute(
                text(
                    "SELECT current_database() AS database, current_catalog AS catalog, "
                    "current_schema() AS schema"
                )
            )
        )
        .mappings()
        .one()
        if engine == "postgresql"
        else {}
    )
    scope.observer.document_database(
        {
            "engine": engine,
            "database": identity.get("database"),
            "catalog": identity.get("catalog"),
            "schema": identity.get("schema"),
        },
        rows,
    )


async def bind_retrieval_parts(hits):
    scope = current()
    if scope is not None:
        hook = getattr(scope.observer, "document_retrieval_parts", None)
        if callable(hook):
            await scope.observer.authorize()
            bound: Any = hook(hits, scope)
            return await bound
    return hits


def hydrated(hits):
    scope = current()
    if scope is not None:
        scope.observer.document_read_hits(hits, scope)
