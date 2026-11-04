# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Compose document-generation evidence without retaining a corpus transaction."""

from contextlib import asynccontextmanager
from dataclasses import dataclass

from flycanon.models.repositories.readiness_generation_repository import (
    ReadinessGenerationChangedError,
    ReadinessGenerationRepository,
    ReadinessSnapshot,
)
from flycanon.models.repositories.source_repository import SourceRepository
from pyfly.container import service
from pyfly.data.transaction import current_unit_of_work
from pyfly.kernel import ConflictException

from koinon.knowledge.adapters import NativeDomains
from koinon.organization_knowledge.transitions.generations import ModeGenerationRepository


@dataclass(frozen=True)
class ModeReadinessSnapshot:
    primary: int
    canon: int

    def encode(self):
        return {"primary": self.primary, "canon": self.canon}

    @classmethod
    def decode(cls, value):
        if not isinstance(value, dict) or any(
            type(value.get(key)) is not int or value[key] < 0 for key in ("primary", "canon")
        ):
            raise ConflictException(
                "Document readiness has no verified generation", code="KNOWLEDGE_MODE_VERIFICATION_REQUIRED"
            )
        return cls(value["primary"], value["canon"])


@service(name="organization_knowledge.mode_readiness_fence")
class ModeReadinessFence:
    def __init__(self, primary: ModeGenerationRepository, domains: NativeDomains):
        self.primary, self.domains = primary, domains

    def native(self):
        return ReadinessGenerationRepository(self.domains._resolve(SourceRepository))

    async def snapshot(self, tenant_id):
        primary = await self.primary.current(tenant_id)
        native = await self.native().snapshot(tenant_id)
        return ModeReadinessSnapshot(primary, native.tenant_generation)

    async def changes(self, tenant_id, domain, *, after_generation, after_workspace_id=None):
        if domain not in {"primary", "canon"}:
            raise ValueError("Select a readiness journal")
        repository = self.primary if domain == "primary" else self.native()
        return await repository.changes(
            tenant_id, after_generation=after_generation, after_workspace_id=after_workspace_id, limit=1
        )

    @asynccontextmanager
    async def hold(self, tenant_id, expected: ModeReadinessSnapshot):
        unit = current_unit_of_work("primary")
        if unit is None or unit.completed or unit.read_only:
            raise RuntimeError("Readiness fencing requires the caller's primary write transaction")
        if not await self.primary.matches(tenant_id, expected.primary):
            raise ConflictException(
                "The Library changed after verification", code="KNOWLEDGE_MODE_GENERATION_CHANGED"
            )
        try:
            async with self.native().hold(tenant_id, ReadinessSnapshot(expected.canon)):
                yield
        except ReadinessGenerationChangedError as error:
            raise ConflictException(
                "Native documents changed after verification", code="KNOWLEDGE_MODE_GENERATION_CHANGED"
            ) from error
