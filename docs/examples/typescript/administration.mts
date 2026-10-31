// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { connect, required, isMain } from "./support.mjs";
import type {
  OrganizationKnowledgeSettings,
  KnowledgeScope,
  MemberUpdate,
  ProviderInput,
} from "@fireflyframework/koinon-sdk";
import { KoinonClient, offsetPages, KoinonError } from "@fireflyframework/koinon-sdk";
export async function planEmbeddings(
  client: KoinonClient,
  tenant: string,
  workspace: string,
  providerId: string,
  modelId: string,
) {
  return client.knowledgeIndexes.plan(tenant, {
    workspace_id: workspace,
    domain: "documents",
    provider_id: providerId,
    model_id: modelId,
  });
}

export async function clearManager(
  client: KoinonClient,
  tenant: string,
  personId: string,
) {
  const current = await client.organizationPeople.get(tenant, personId);
  if (current.revision === undefined) throw new Error("Current revision is required");
  return client.organizationPeople.update(tenant, personId, {
    expected_revision: current.revision,
    manager_id: null,
  });
}

export async function clearDefaultAgent(client: KoinonClient, tenant: string) {
  const current = await client.organizationChat.get(tenant);
  return client.organizationChat.update(tenant, {
    expected_revision: current.revision,
    default_agent_id: null,
  });
}

export async function browseDocuments(
  client: KoinonClient,
  tenant: string,
  workspace: string,
  signal: AbortSignal,
) {
  for await (const page of offsetPages(
    (number, currentSignal) =>
      client.catalog.list(
        tenant,
        { workspace_id: workspace, kind: "document", page: number, page_size: 25 },
        { signal: currentSignal },
      ),
    1,
    signal,
  )) {
    for (const document of page.items) console.log(document.id, document.name);
  }
}

export async function readEntry(client: KoinonClient, tenant: string, entryId: string) {
  try {
    return await client.catalog.get(tenant, entryId);
  } catch (error) {
    if (error instanceof KoinonError) {
      console.error(error.status, error.code, error.requestId);
    }
    throw error;
  }
}

export async function setReviewedDocumentMode(
  client: KoinonClient,
  tenant: string,
  reviewed: OrganizationKnowledgeSettings,
  mode: "rag" | "rlm",
  personConfirmed: boolean,
) {
  if (!personConfirmed) throw new Error("Review the mode and retained settings");
  return client.organizationKnowledge.update(tenant, {
    expected_revision: reviewed.revision,
    documents: { ...reviewed.documents, answer_mode: mode },
    structured: reviewed.structured,
  });
}

export async function createReviewedAgent(
  client: KoinonClient,
  tenant: string,
  providerId: string,
  modelId: string,
  scope: KnowledgeScope,
  personConfirmed: boolean,
) {
  if (!personConfirmed) throw new Error("Review the model, tools and scope");
  return client.agents.create(tenant, {
    name: "Knowledge reader",
    provider_id: providerId,
    model_id: modelId,
    scope,
    tools: ["search_knowledge", "inspect_schema", "query_dataset"],
    enabled: true,
  });
}

export async function updateReviewedMember(
  client: KoinonClient,
  tenant: string,
  memberId: string,
  change: MemberUpdate,
  personConfirmed: boolean,
) {
  if (!personConfirmed) throw new Error("Review the member and access change");
  return client.members.update(tenant, memberId, change);
}

export async function createReviewedProvider(
  client: KoinonClient,
  tenant: string,
  input: ProviderInput,
  personConfirmed: boolean,
) {
  if (!personConfirmed) throw new Error("Review the supported provider configuration");
  return client.providers.create(tenant, input);
}

async function main(): Promise<void> {
  const person = await connect().organizationPeople.me(required("KOINON_TENANT_ID"));
  console.log(person.id, person.job_title, person.revision);
}

if (isMain(import.meta.url)) await main();
