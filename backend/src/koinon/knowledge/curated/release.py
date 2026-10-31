# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Detect authority changes across awaited policy checks without duplicating those policies."""

from pyfly.container import service
from pyfly.security.context_holder import SecurityContextHolder

from koinon.catalog.errors import AccessDenied
from koinon.catalog.service import CatalogService
from koinon.knowledge.curated.release_dtos import CuratedReleaseStamp
from koinon.knowledge.curated.release_repository import CuratedReleaseRepository


@service(name="knowledge.curated.release_fence")
class CuratedReleaseFence:
    def __init__(self, catalog: CatalogService, repository: CuratedReleaseRepository):
        self.catalog, self.repository = catalog, repository

    async def observe(self, subject: str, tenant_id: str, item_ids: tuple[str, ...]) -> CuratedReleaseStamp:
        context = SecurityContextHolder.get_context()
        token_id = context.attributes.get("koinon_token_id") if context else None
        return await self.repository.observe(
            subject, tenant_id, item_ids, self.catalog.effective_membership_rows(), token_id
        )

    async def require_unchanged(
        self, subject: str, tenant_id: str, item_ids: tuple[str, ...], admitted: CuratedReleaseStamp
    ) -> None:
        # This final statement is the primary authorization cut; native versions remain immutable pins.
        current = await self.observe(subject, tenant_id, item_ids)
        if current != admitted:
            raise AccessDenied(
                "Knowledge authority changed during this read; retry in the current scope",
                code="KNOWLEDGE_AUTHORITY_CHANGED",
            )
