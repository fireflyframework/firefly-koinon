# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Caller-transaction structural proof operations; no authorization is inferred."""

import json

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from koinon.integrations.content_sources.structure_publication_dtos import (
    ResolvedSourcePublication,
    StructurePublicationIdentity,
    StructureWrite,
    encode_structure_writes,
)


class SourceStructurePublications:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def resolve(
        self, tenant: str, mapping: str, object_id: str, revision: str
    ) -> ResolvedSourcePublication | None:
        value = await self.session.scalar(
            text("SELECT public.koinon_resolve_source_publication(:tenant,:mapping,:object,:revision)"),
            {"tenant": tenant, "mapping": mapping, "object": object_id, "revision": revision},
        )
        if value is None:
            return None
        for field in ("native_receipt", "effective_vector", "original_members"):
            value[field + "_json"] = json.dumps(value.pop(field), separators=(",", ":"), sort_keys=True)
        return ResolvedSourcePublication(**value)

    async def begin(
        self,
        *,
        run_id: str,
        work_id: str,
        observation_id: str,
        worker_id: str,
        job_attempt: int,
        operations: tuple[StructureWrite, ...],
    ) -> StructurePublicationIdentity:
        value = await self.session.scalar(
            text(
                "SELECT public.koinon_begin_source_structure("
                ":run,:work,:observation,:worker,:attempt,CAST(:operations AS json))"
            ),
            {
                "run": run_id,
                "work": work_id,
                "observation": observation_id,
                "worker": worker_id,
                "attempt": job_attempt,
                "operations": encode_structure_writes(operations),
            },
        )
        return StructurePublicationIdentity(**value)

    async def finalize(self, proof_id: str) -> StructurePublicationIdentity:
        value = await self.session.scalar(
            text("SELECT public.koinon_finalize_source_structure(:proof)"), {"proof": proof_id}
        )
        return StructurePublicationIdentity(**value)

    async def completed(
        self, *, tenant: str, work_id: str, observation_id: str
    ) -> StructurePublicationIdentity | None:
        value = await self.session.scalar(
            text("SELECT public.koinon_completed_source_structure(:tenant,:work,:observation)"),
            {"tenant": tenant, "work": work_id, "observation": observation_id},
        )
        return StructurePublicationIdentity(**value) if value else None
