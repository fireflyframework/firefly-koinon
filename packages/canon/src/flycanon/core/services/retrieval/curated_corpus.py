# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Optional request-owned native version corpus; standalone behavior is unchanged."""

from asyncio import current_task
from collections.abc import Awaitable, Callable
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import TYPE_CHECKING

from pyfly.kernel import ServiceUnavailableException

if TYPE_CHECKING:
    from flycanon.core.services.retrieval.retrieval_service import Hit


@dataclass
class CorpusLease:
    tenant_id: str
    workspace_id: str
    retrieve: Callable[..., Awaitable[list["Hit"]]]
    task: object
    documents: bool = True
    active: bool = True


_current: ContextVar[CorpusLease | None] = ContextVar("curated_version_corpus", default=None)


@contextmanager
def bind(*, tenant_id, workspace_id, retrieve, documents=True):
    lease = CorpusLease(tenant_id, workspace_id, retrieve, current_task(), documents)
    token = _current.set(lease)
    try:
        yield
    finally:
        lease.active = False
        _current.reset(token)


async def search(*, tenant_id, workspace_id, query, limit):
    lease = _current.get()
    if lease is None:
        return []
    if (
        not lease.active
        or current_task() is not lease.task
        or (tenant_id, workspace_id) != (lease.tenant_id, lease.workspace_id)
    ):
        raise ServiceUnavailableException(
            "Curated corpus admission expired", code="KNOWLEDGE_CORPUS_SCOPE_EXPIRED"
        )
    return await lease.retrieve(query=query, limit=limit)


def documents_enabled(*, tenant_id, workspace_id):
    lease = _current.get()
    if lease is None:
        return True
    if (
        not lease.active
        or current_task() is not lease.task
        or (tenant_id, workspace_id) != (lease.tenant_id, lease.workspace_id)
    ):
        raise ServiceUnavailableException(
            "Curated corpus admission expired", code="KNOWLEDGE_CORPUS_SCOPE_EXPIRED"
        )
    return lease.documents
