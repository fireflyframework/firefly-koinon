# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Offer configured tools compatible with current authorized source selections."""

from typing import cast

from pyfly.container import service

from koinon.assistants.scope import KnowledgeScopePolicy
from koinon.assistants.tool_activity import ToolName
from koinon.assistants.tool_offering_dtos import ToolOffering
from koinon.assistants.tool_offering_mappers import selected_source
from koinon.catalog.entities import CatalogEntry
from koinon.catalog.errors import AccessDenied
from koinon.catalog.service import CatalogService

PERMISSIONS = {
    "search_knowledge": "knowledge:search",
    "inspect_schema": "catalog:read",
    "query_dataset": "query:execute",
    "propose_catalog_update": "catalog:write",
}
KINDS = {
    "search_knowledge": {"document", "knowledge_item"},
    "inspect_schema": {"dataset"},
    "query_dataset": {"dataset"},
    "propose_catalog_update": {"document", "dataset"},
}


@service(name="assistants.tool-availability")
class AssistantToolAvailability:
    def __init__(self, catalog: CatalogService, scope_policy: KnowledgeScopePolicy):
        self.catalog, self.scope_policy = catalog, scope_policy

    async def action_allowed(
        self,
        subject: str,
        tenant_id: str,
        tool: str,
        workspace_id: str | None,
        entry: CatalogEntry | None = None,
    ) -> bool:
        try:
            await self.catalog.authorize(subject, tenant_id, PERMISSIONS[tool], workspace_id)
            if tool == "propose_catalog_update" and entry is not None and self.catalog.restriction:
                await self.catalog.restriction.resource(subject, entry, write=True)
        except AccessDenied:
            return False
        return True

    async def resolve(self, subject: str, tenant_id: str, scope: dict, enabled: list[str]) -> ToolOffering:
        scope = await self.scope_policy.validate_scope(subject, tenant_id, scope)
        explicit = "asset_ids" in scope
        # A denied selected source is an error. Only optional action denial removes a tool.
        entries = [await self.catalog.get(subject, tenant_id, key) for key in scope.get("asset_ids", [])]
        offered: list[ToolName] = []
        for tool in dict.fromkeys(enabled):
            if tool not in PERMISSIONS:
                continue
            relevant = [entry for entry in entries if entry.kind in KINDS[tool]]
            if explicit and not relevant:
                continue
            if explicit:
                allowed = True
                for entry in relevant:
                    if not await self.action_allowed(subject, tenant_id, tool, entry.workspace_id, entry):
                        allowed = False
                        break
            else:
                allowed = await self.action_allowed(subject, tenant_id, tool, scope.get("workspace_id"))
            if allowed:
                offered.append(cast(ToolName, tool))
        # Re-read all selections after optional permission awaits before mapping any labels.
        entries = [await self.catalog.get(subject, tenant_id, entry.id) for entry in entries]
        return ToolOffering(
            selection="explicit_selection" if explicit else "broader_scope",
            sources=tuple(selected_source(entry) for entry in entries),
            tools=tuple(offered),
        )
