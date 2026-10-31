# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0

import asyncio
from typing import Literal

from koinon_sdk import (
    AgentConfiguration,
    AgentInput,
    ApiError,
    CatalogEntry,
    IndexPlanInput,
    IndexPlanView,
    KnowledgeScope,
    KoinonClient,
    Membership,
    MemberUpdate,
    ModelProvider,
    OrganizationChatSettings,
    OrganizationChatSettingsInput,
    OrganizationKnowledgeSettings,
    OrganizationKnowledgeSettingsInput,
    OrganizationPerson,
    OrganizationPersonPatch,
    ProviderInput,
)
from support import connect, required


async def plan_embeddings(
    client: KoinonClient,
    tenant: str,
    workspace: str,
    provider_id: str,
    model_id: str,
) -> IndexPlanView:
    return await client.plan_knowledge_index(
        tenant,
        IndexPlanInput(
            workspace_id=workspace,
            domain="documents",
            provider_id=provider_id,
            model_id=model_id,
        ),
    )


async def clear_manager(
    client: KoinonClient,
    tenant: str,
    person_id: str,
) -> OrganizationPerson:
    current = await client.organization_person(tenant, person_id)
    return await client.update_organization_person(
        tenant,
        person_id,
        OrganizationPersonPatch(expected_revision=current.revision, manager_id=None),
    )


async def clear_default_agent(
    client: KoinonClient, tenant: str
) -> OrganizationChatSettings:
    current = await client.organization_chat_settings(tenant)
    return await client.update_organization_chat_settings(
        tenant,
        OrganizationChatSettingsInput(
            expected_revision=current.revision,
            default_agent_id=None,
        ),
    )


async def read_entry(client: KoinonClient, tenant: str, entry_id: str) -> CatalogEntry:
    try:
        return await client.get(tenant, entry_id)
    except ApiError as error:
        # Correlate with operators without logging bearer tokens or request bodies.
        print(error.status, error.code, error.transaction_id)
        raise


async def set_reviewed_document_mode(
    client: KoinonClient,
    tenant: str,
    reviewed: OrganizationKnowledgeSettings,
    mode: Literal["rag", "rlm"],
    person_confirmed: bool,
) -> OrganizationKnowledgeSettings:
    if not person_confirmed:
        raise ValueError("Review the selected mode and retained settings first")
    documents = reviewed.documents.model_copy(update={"answer_mode": mode})
    return await client.update_organization_knowledge_settings(
        tenant,
        OrganizationKnowledgeSettingsInput(
            expected_revision=reviewed.revision,
            documents=documents,
            structured=reviewed.structured,
        ),
    )


async def create_reviewed_agent(
    client: KoinonClient,
    tenant: str,
    provider_id: str,
    model_id: str,
    scope: KnowledgeScope,
    person_confirmed: bool,
) -> AgentConfiguration:
    if not person_confirmed:
        raise ValueError("Review the configured model, tools and scope first")
    return await client.create_agent(
        tenant,
        AgentInput(
            name="Knowledge reader",
            provider_id=provider_id,
            model_id=model_id,
            scope=scope,
            tools=["search_knowledge", "inspect_schema", "query_dataset"],
            enabled=True,
        ),
    )


async def update_reviewed_member(
    client: KoinonClient,
    tenant: str,
    member_id: str,
    change: MemberUpdate,
    person_confirmed: bool,
) -> Membership:
    if not person_confirmed:
        raise ValueError("Review the actual member and access change first")
    return await client.update_member(tenant, member_id, change)


async def create_reviewed_provider(
    client: KoinonClient,
    tenant: str,
    value: ProviderInput,
    person_confirmed: bool,
) -> ModelProvider:
    if not person_confirmed:
        raise ValueError("Review the supported provider configuration first")
    return await client.create_provider(tenant, value)


async def main() -> None:
    async with connect() as client:
        person = await client.organization_person_self(required("KOINON_TENANT_ID"))
        print(person.id, person.job_title, person.revision)


if __name__ == "__main__":
    asyncio.run(main())
