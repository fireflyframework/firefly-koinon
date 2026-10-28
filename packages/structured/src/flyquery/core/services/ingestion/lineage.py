# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Optional borrowed product lineage observer; standalone ingestion remains independent."""

import json
from asyncio import CancelledError
from contextlib import asynccontextmanager, contextmanager
from contextvars import ContextVar
from dataclasses import asdict, dataclass
from hashlib import sha256
from typing import Any, Protocol

from pyfly.kernel import ConflictException, ForbiddenException, ServiceUnavailableException


class LineageError(ServiceUnavailableException):
    """A required durable product receipt failed; provider fallbacks must not absorb it."""

    def __init__(self, message="Durable file lineage is unavailable", **kwargs):
        super().__init__(message, code=kwargs.pop("code", "INGESTION_LINEAGE_UNAVAILABLE"), **kwargs)


class LineageDenied(ForbiddenException, LineageError):
    pass


class LineageConflict(ConflictException, LineageError):
    pass


class LineageSink(Protocol):
    async def emit(self, event: str, **values: Any) -> Any: ...


@dataclass
class _Lease:
    sink: LineageSink
    active: bool = True


_section: ContextVar[str | None] = ContextVar("structured_lineage_section", default=None)


@contextmanager
def section(run_id):
    token = _section.set(run_id)
    try:
        yield
    finally:
        _section.reset(token)


_current: ContextVar[_Lease | None] = ContextVar("structured_ingestion_lineage", default=None)


@contextmanager
def observe(sink: LineageSink):
    lease = _Lease(sink)
    token = _current.set(lease)
    try:
        yield
    finally:
        lease.active = False
        _current.reset(token)


async def emit(event: str, **values):
    lease = _current.get()
    if lease is None:
        return None
    if not lease.active:
        raise LineageError("The ingestion lineage scope expired")
    if _section.get() is not None:
        values.setdefault("run_id", _section.get())
    try:
        return await lease.sink.emit(event, **values)
    except LineageError:
        raise
    except ForbiddenException as error:
        raise LineageDenied(
            "Ingestion authority changed", code=getattr(error, "code", None) or "ACCESS_DENIED"
        ) from error
    except ConflictException as error:
        raise LineageConflict(
            "Ingestion version changed", code=getattr(error, "code", None) or "CONTENT_VERSION_CONFLICT"
        ) from error
    except Exception as error:
        raise LineageError(
            "Verify the structured lineage migration and scoped storage permissions, then retry ingestion"
        ) from error


@asynccontextmanager
async def stage(run_id, name, *, completion=True):
    if run_id is None:
        yield
        return
    await emit(
        "step",
        run_id=run_id,
        kind="stage_input",
        implementation="structured." + name,
        parameters={"stage": name},
    )
    try:
        with section(run_id):
            yield
    except BaseException as error:
        try:
            await emit(
                "step",
                run_id=run_id,
                kind="stage_failed",
                implementation="structured." + name,
                parameters={"stage": name},
            )
        except Exception:
            if isinstance(error, CancelledError):
                raise error from None
            raise
        raise
    else:
        if not completion:
            return
        await emit(
            "step",
            run_id=run_id,
            kind="stage_completed",
            implementation="structured." + name,
            parameters={"stage": name},
        )


async def model_input(prompt, *, role, implementation, implementation_sha256=None, agent=None):
    if _current.get() is None:
        return
    from flyquery.core.agents.model_bindings import agent_construction, binding_for
    from flyquery.core.agents.provenance import settings_digest

    binding = binding_for(role)
    construction = agent_construction(agent) if agent is not None else None
    if construction is not None and construction.role != role:
        raise LineageError("The model constructor does not match the recorded ingestion role")
    metadata = {}
    if construction is not None:
        metadata.update(
            model_class=construction.model_class,
            instructions_sha256=construction.instructions_sha256,
            applied_model_settings_sha256=construction.applied_model_settings_sha256,
            constructor_identity_complete=bool(
                construction.provenance
                and construction.provenance.complete
                and construction.applied_model_settings_sha256
            ),
        )
        if construction.provenance is not None:
            recorded = asdict(construction.provenance)
            metadata["binding_mode"] = recorded.pop("mode")
            metadata.update(recorded)
    else:
        metadata["constructor_identity_complete"] = False
    await emit(
        "model_input",
        input_sha256=sha256(prompt.encode()).hexdigest(),
        implementation=implementation,
        implementation_sha256=implementation_sha256,
        parameters={
            "role": role,
            "model_reference": f"{construction.provider}:{construction.model_name}" if construction else None,
            "api": construction.api if construction else None,
            "output_mode": construction.output_mode if construction else None,
            "binding_settings_sha256": settings_digest(binding.model_settings) if binding else None,
            "transformation_identity_complete": False,
            **metadata,
        },
    )


async def model_output(output, *, implementation, implementation_sha256=None):
    if _current.get() is None:
        return
    encode = getattr(output, "model_dump", None)
    body = (
        json.dumps(encode(mode="json"), sort_keys=True, ensure_ascii=False)
        if callable(encode)
        else str(output)
    )
    await emit(
        "model_output",
        output_sha256=sha256(body.encode()).hexdigest(),
        implementation=implementation,
        implementation_sha256=implementation_sha256,
        parameters={"output_encoding": "pydantic-json" if callable(encode) else "python-str"},
    )
