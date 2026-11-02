# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Fresh authorized product configuration; distinct from organizational knowledge evidence."""

from pyfly.container import service

from koinon.answers.help_dtos import ProductHelpContext
from koinon.assistants.connections import provider_state
from koinon.assistants.tool_offering import AssistantToolAvailability
from koinon.assistants.tool_offering_mappers import private_offering
from koinon.organization_branding.service import OrganizationBrandingService


@service(name="assistants.product-context")
class AssistantProductContext:
    def __init__(self, branding: OrganizationBrandingService, tools: AssistantToolAvailability):
        self.branding, self.tools = branding, tools

    async def resolve(self, subject, tenant_id, scope, agent, provider, refs):
        identity = await self.branding.get(subject, tenant_id)
        capability = next(
            (c for c in provider_state(provider)["model_capabilities"] if c["model_id"] == agent.model_id),
            None,
        )
        offering = (
            private_offering(
                refs, search_enabled=not capability or capability["tools"]["supported"] is not False
            )
            if refs
            else await self.tools.resolve(subject, tenant_id, scope, agent.tools)
        )
        return ProductHelpContext(
            product_name=identity.branding.product_name,
            assistant_name=identity.branding.assistant_name,
            branding_revision=identity.revision,
            branding_origin=identity.origin,
            selection=offering.selection,
            tools=offering.tools,
        )
