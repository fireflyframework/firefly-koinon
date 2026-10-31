# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Lazy authorization port prevents recursive service construction or memory DAG traversal."""

from abc import ABC, abstractmethod

from koinon.assistants.memory.dtos import MemoryReceipt
from koinon.assistants.memory.projections import MemoryOutputCapture


class ChatMemoryAccess(ABC):
    async def query_context(self, subject: str, tenant_id: str, run_id: str) -> dict:
        raise NotImplementedError("Stored query generation binding is unavailable")

    @abstractmethod
    async def authorize(
        self, subject: str, tenant_id: str, run_id: str, *, captures: tuple[MemoryOutputCapture, ...] = ()
    ) -> MemoryReceipt | None: ...

    @abstractmethod
    async def authorize_many(
        self,
        subject: str,
        tenant_id: str,
        run_ids: tuple[str, ...],
        *,
        captures: tuple[MemoryOutputCapture, ...] = (),
    ) -> dict[str, MemoryReceipt | None]: ...

    @abstractmethod
    async def authorize_result(
        self, subject: str, tenant_id: str, run_id: str, result_id: str, expected_sha256: str
    ) -> None: ...
