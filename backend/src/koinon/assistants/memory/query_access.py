# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Native stored queries retain the exact server generation that supplied their context."""

from contextvars import ContextVar

from flyquery.core.services.query.consumer_context import ConsumerQueryAccess
from flyquery.web.conventions.context import current_tenant_context
from pyfly.container import service

from koinon.assistants.memory.egress import MemoryEgress
from koinon.assistants.memory.egress_dtos import MemoryEgressBinding, MemoryEgressPin
from koinon.assistants.memory.mappers import digest
from koinon.assistants.memory.service import unavailable

_checking: ContextVar[bool] = ContextVar("koinon_query_context_authorization", default=False)


@service(name="assistants.memory_query_access")
class MemoryQueryAccess(ConsumerQueryAccess):
    def __init__(self, egress: MemoryEgress):
        self.egress = egress

    async def authorize(self, contexts, tenant_id, workspace_id):
        # Source resolution reads native query metadata during this same flattened
        # authorization. Its output remains inside the enclosing release boundary.
        if _checking.get():
            return
        context = current_tenant_context()
        if context is None or context.tenant_id != tenant_id or str(context.workspace_id) != workspace_id:
            raise unavailable()
        bindings = []
        for value in contexts:
            if (value.get("kind"), value.get("subject"), value.get("tenant_id")) != (
                "koinon_generation",
                context.actor,
                tenant_id,
            ):
                raise unavailable()
            binding = MemoryEgressBinding.model_validate(value["binding"])
            if not binding.generation_id:
                raise unavailable()
            generation = (
                await self.egress.memory.get().assistants.get().results.find_by_id(binding.generation_id)
            )
            if generation is None or generation.run_id != binding.run_id or generation.kind != "generation":
                raise unavailable()
            bindings.append(
                binding.model_copy(
                    update={
                        "results": (
                            MemoryEgressPin(
                                id=generation.id,
                                sha256=digest({"kind": generation.kind, "payload": generation.payload}),
                            ),
                        )
                    }
                )
            )
        token = _checking.set(True)
        try:
            await self.egress.authorize(context.actor, tenant_id, tuple(bindings))
        finally:
            _checking.reset(token)
