// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { connect, required, isMain } from "./support.mjs";
import type { DocumentVersion, DocumentChunks } from "@fireflyframework/koinon-sdk";
import {
  KoinonClient,
  type UploadResponse,
  type DocumentPartContent,
  type KnowledgeIntent,
} from "@fireflyframework/koinon-sdk";
export async function ingestDocument(
  client: KoinonClient,
  tenant: string,
  workspace: string,
  file: File,
): Promise<UploadResponse> {
  if (file.size === 0 || file.size > 32 * 1024 * 1024) {
    throw new Error("Choose a nonempty file up to 32 MiB");
  }
  const project = await client.catalog.create(tenant, {
    kind: "project",
    name: "Operations",
    parent_id: workspace,
  });
  const collection = await client.catalog.create(tenant, {
    kind: "collection",
    name: "Policies",
    parent_id: project.id,
  });
  await client.catalog.update(tenant, collection.id, { name: "Approved policies" });
  return client.sources.uploadFile(tenant, {
    file,
    filename: file.name,
    workspace_id: workspace,
    project_id: project.id,
    parent_id: collection.id,
    mode: "document",
  });
}

export async function retrieve(
  client: KoinonClient,
  tenant: string,
  workspace: string,
  datasetId: string,
  sql: string,
  signal?: AbortSignal,
) {
  const hits = await client.search(
    tenant,
    { question: "Retention policy", workspace_id: workspace, limit: 10, answer: false },
    { signal },
  );
  const query = await client.query(tenant, { dataset_id: datasetId, sql }, { signal });
  return { hits, query };
}

export async function firstRecordedChunk(
  client: KoinonClient,
  tenant: string,
  documentId: string,
): Promise<DocumentPartContent | undefined> {
  const versions = await client.documents.versions(tenant, documentId, {
    page: 1,
    page_size: 25,
  });
  const version = versions.items[0];
  if (!version) return;
  const extractions = await client.documents.extractions(
    tenant,
    documentId,
    version.source_version_id,
    { page: 1, page_size: 25 },
  );
  const extraction = extractions.items[0];
  if (!extraction) return;
  const parts = await client.documents.parts(
    tenant,
    documentId,
    version.source_version_id,
    extraction.extraction_id,
    { kind: "chunk", page: 1, page_size: 25 },
  );
  const part = parts.items[0];
  if (!part) return;
  return client.documents.part(
    tenant,
    documentId,
    version.source_version_id,
    extraction.extraction_id,
    part.source_part_id,
  );
}

export async function previewDraft(
  client: KoinonClient,
  tenant: string,
  destinationId: string,
  title: string,
  userBody: string,
) {
  return client.knowledgeIntents.preview(tenant, {
    action: "create_draft",
    destination_id: destinationId,
    content: { title, body: userBody },
    origin: { kind: "user_statement" },
  });
}

export async function confirmReviewedIntent(
  client: KoinonClient,
  tenant: string,
  reviewed: KnowledgeIntent,
  userConfirmed: boolean,
  stableKey: string,
) {
  if (!userConfirmed || reviewed.status !== "preview") {
    throw new Error("Review the current intent and confirm it explicitly");
  }
  return client.knowledgeIntents.confirm(
    tenant,
    reviewed.id,
    {
      confirm: true,
      expected_revision: reviewed.revision,
      authorization_digest: reviewed.authorization_digest,
    },
    stableKey,
  );
}

export async function appendReviewedFile(
  client: KoinonClient,
  tenant: string,
  datasetId: string,
  file: File,
  stableKey: string,
  personConfirmed: boolean,
) {
  if (!personConfirmed || file.size === 0 || file.size > 32 * 1024 * 1024) {
    throw new Error("Review the dataset and a nonempty file up to 32 MiB");
  }
  return client.dataset.appendFile(tenant, datasetId, file, stableKey, {
    filename: file.name,
  });
}

export async function replaceReviewedDocument(
  client: KoinonClient,
  tenant: string,
  documentId: string,
  original: DocumentVersion,
  head: DocumentChunks,
  file: File,
  personConfirmed: boolean,
) {
  if (
    !personConfirmed ||
    !head.extraction_id ||
    original.source_version_id !== head.source_version_id
  ) {
    throw new Error("Review the matching original and extraction head");
  }
  if (!file.size || file.size > 32 * 1024 * 1024) {
    throw new Error("Choose replacement bytes up to 32 MiB");
  }
  return client.documents.replace(tenant, documentId, file, {
    filename: file.name,
    expected_sha256: original.sha256,
    expected_source_version_id: original.source_version_id,
    expected_extraction_id: head.extraction_id,
    acknowledge_chunk_invalidation: true,
  });
}

export async function ingestDataset(
  client: KoinonClient,
  tenant: string,
  workspace: string,
  projectId: string,
  collectionId: string,
  file: File,
): Promise<UploadResponse> {
  if (!file.size || file.size > 32 * 1024 * 1024) {
    throw new Error("Choose a nonempty file up to 32 MiB");
  }
  return client.sources.uploadFile(tenant, {
    file,
    filename: file.name,
    workspace_id: workspace,
    project_id: projectId,
    parent_id: collectionId,
    mode: "dataset",
  });
}

async function main(): Promise<void> {
  const versions = await connect().documents.versions(
    required("KOINON_TENANT_ID"),
    required("KOINON_DOCUMENT_ID"),
    { page: 1, page_size: 25 },
  );
  for (const version of versions.items) {
    console.log(version.source_version_id, version.sha256);
  }
}

if (isMain(import.meta.url)) await main();
