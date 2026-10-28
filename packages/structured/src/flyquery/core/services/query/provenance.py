# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Optional caller-owned receipts around actual native reads and executions."""

from asyncio import CancelledError, current_task
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from functools import wraps
from typing import Any

from pyfly.kernel import ServiceUnavailableException


@dataclass
class Observation:
    observer: Any
    tenant_id: str
    workspace_id: str
    dataset_id: str
    actor: str
    task: object
    resolved: dict = field(default_factory=dict)
    resolved_rows: dict = field(default_factory=dict)
    active: bool = True


_current: ContextVar[Observation | None] = ContextVar("structured_evidence", default=None)
_attempt: ContextVar[int | None] = ContextVar("structured_sql_attempt", default=None)


@contextmanager
def observe(observer, *, tenant_id, workspace_id, dataset_id, actor):
    scope = Observation(observer, tenant_id, str(workspace_id), str(dataset_id), actor, current_task())
    token = _current.set(scope)
    try:
        yield
    finally:
        scope.active = False
        _current.reset(token)


def current():
    scope = _current.get()
    if scope is not None:
        if not scope.active or scope.task is not current_task():
            raise ServiceUnavailableException(
                "Native provenance scope has expired", code="EVIDENCE_UNAVAILABLE"
            )
        scope.observer.scope(scope.tenant_id, scope.workspace_id, scope.actor)
    return scope


async def before_model(stage, prompt, bundle, *, tenant_id, workspace_id, dataset_id, execution=None):
    scope = current()
    if scope is None:
        from flyquery.core.agents.model_bindings import current_scope

        bindings = current_scope()
        if bindings is not None and bindings.required:
            raise ServiceUnavailableException(
                "Native provenance observer is required", code="EVIDENCE_UNAVAILABLE"
            )
    if scope is not None:
        if (tenant_id, str(workspace_id), str(dataset_id)) != (
            scope.tenant_id,
            scope.workspace_id,
            scope.dataset_id,
        ):
            raise ServiceUnavailableException("Native provenance scope mismatch", code="EVIDENCE_UNAVAILABLE")
        if execution is not None:
            scope.observer.structured_result(execution, scope)
        await scope.observer.structured_model(stage, prompt, bundle, scope)


def resolved(dataset_id, rows):
    scope = current()
    if scope is not None:
        if str(dataset_id) != scope.dataset_id:
            raise ServiceUnavailableException(
                "Native provenance dataset mismatch", code="EVIDENCE_UNAVAILABLE"
            )
        scope.resolved = {row["name"]: str(row.get("snapshot_id") or "") for row in rows}
        scope.resolved_rows = {row["name"]: dict(row) for row in rows}
        scope.observer.structured_resolved(rows, scope)
        if _attempt.get() is not None:
            scope.observer.sql_pins(_attempt.get(), scope.resolved)


def candidate(operation):
    @wraps(operation)
    async def tracked(self, sql, *args, **kwargs):
        stage = kwargs.pop("_evidence_stage", "candidate")
        scope = current()
        if scope is None:
            return await operation(self, sql, *args, **kwargs)
        identifier = scope.observer.sql_begin(stage, sql)
        scope.observer.sql_dataset(identifier, scope.dataset_id)
        token = _attempt.set(identifier)
        try:
            result = await operation(self, sql, *args, **kwargs)
            ast = result.get("ast")
            scope.observer.sql_candidate(identifier, result["status"], getattr(ast, "classification", None))
            return result
        except BaseException as error:
            scope.observer.sql_failed(identifier, isinstance(error, CancelledError))
            raise
        finally:
            _attempt.reset(token)

    return tracked


def execution(operation):
    @wraps(operation)
    async def tracked(self, sql, attached_tables, *args, **kwargs):
        scope = current()
        if scope is None:
            return await operation(self, sql, attached_tables, *args, **kwargs)
        identifier = _attempt.get()
        if identifier is None:
            identifier = scope.observer.sql_begin("lookup", sql)
        from flyquery.core.services.execution.ast_classifier import AstClassifier

        classification = AstClassifier().classify(sql)
        names = [name for name in classification.table_refs if name in attached_tables]
        scope.observer.sql_pins(identifier, {name: scope.resolved.get(name, "") for name in names})
        scope.observer.sql_tables(identifier, [scope.resolved_rows[name] for name in names])
        scope.observer.sql_dataset(identifier, scope.dataset_id)
        scope.observer.sql_classified(identifier, classification.classification)
        token = _attempt.set(identifier)
        try:
            result = await operation(self, sql, attached_tables, *args, **kwargs)
            scope.observer.sql_executed(identifier, result)
            return result
        except BaseException as error:
            scope.observer.sql_failed(identifier, isinstance(error, CancelledError))
            raise
        finally:
            _attempt.reset(token)

    return tracked


def direct(operation):
    @wraps(operation)
    async def tracked(self, request, body, *args, **kwargs):
        scope = current()
        if scope is None:
            return await operation(self, request, body, *args, **kwargs)
        identifier = scope.observer.sql_begin("direct", body.sql)
        scope.observer.sql_dataset(identifier, scope.dataset_id)
        token = _attempt.set(identifier)
        try:
            result = await operation(self, request, body, *args, **kwargs)
            status = "scope" if result.execution_status == "REJECTED_BY_FIREWALL" else "error"
            scope.observer.sql_candidate(identifier, status, result.ast_classification)
            return result
        except BaseException as error:
            scope.observer.sql_failed(identifier, isinstance(error, CancelledError))
            raise
        finally:
            _attempt.reset(token)

    return tracked


def request_context(request):
    scope = current()
    if scope is None:
        return None
    from flyquery.web.conventions.context import current_tenant_context

    context = current_tenant_context()
    if (
        context is None
        or getattr(request.state, "legacy_tenant_context", None) is not context
        or (context.tenant_id, str(context.workspace_id), context.actor)
        != (scope.tenant_id, scope.workspace_id, scope.actor)
    ):
        raise ServiceUnavailableException(
            "Native internal authority is unavailable", code="EVIDENCE_UNAVAILABLE"
        )
    return context


def engine(context, *, executed):
    scope = current()
    if scope is not None and _attempt.get() is not None:
        scope.observer.sql_engine(_attempt.get(), context or {}, executed=executed)
