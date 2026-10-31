// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { connect, required, isMain } from "./support.mjs";
import type {
  ChatThread,
  ExportReview,
  ShareReview,
} from "@fireflyframework/koinon-sdk";
import {
  KoinonClient,
  type KnowledgeScope,
  type StreamEvent,
  type ChatEventData,
} from "@fireflyframework/koinon-sdk";
export async function createConversation(
  client: KoinonClient,
  tenant: string,
  scope: KnowledgeScope,
) {
  return client.chat.create(tenant, { title: "Knowledge question", scope });
}

export async function startQuestion(
  client: KoinonClient,
  tenant: string,
  threadId: string,
  scope: KnowledgeScope,
  question: string,
  stableRequestId: string,
) {
  const settings = await client.organizationChat.get(tenant, {
    ...(scope.workspace_id ? { workspace_id: scope.workspace_id } : {}),
    ...(scope.project_id ? { project_id: scope.project_id } : {}),
  });
  if (!settings.can_run || !settings.default_agent_id) {
    throw new Error("An operator must configure the organization's chat agent");
  }
  return client.chat.submit(tenant, threadId, {
    agent_id: settings.default_agent_id,
    message: question,
    scope,
    client_request_id: stableRequestId,
    attachment_ids: [],
  });
}

export async function consumeRun(
  client: KoinonClient,
  tenant: string,
  runId: string,
  checkpoint: (event: StreamEvent<ChatEventData>, text: string) => Promise<void>,
  signal?: AbortSignal,
  lastProcessedId?: string,
  initialText = "",
): Promise<{ lastProcessedId: string; terminal: string; text: string }> {
  let text = initialText;
  for await (const event of client.chat.events(tenant, runId, {
    signal,
    ...(lastProcessedId !== undefined ? { lastEventId: lastProcessedId } : {}),
  })) {
    if (event.type === "message_reset") {
      text = "";
    } else if (event.type === "message_delta") {
      text += event.data.text ?? "";
    }
    await checkpoint(event, text);
    lastProcessedId = event.id;
    if (["completed", "failed", "cancelled"].includes(event.type)) {
      return { lastProcessedId, terminal: event.type, text };
    }
  }
  throw new Error("Stream ended without a terminal event; reconcile the saved run");
}

export async function moveReviewedThread(
  client: KoinonClient,
  tenant: string,
  reviewed: ChatThread,
  folderId: string | null,
  personConfirmed: boolean,
) {
  if (!personConfirmed) throw new Error("Review the selected folder and thread");
  return client.chat.update(tenant, reviewed.id, {
    expected_revision: reviewed.revision,
    folder_id: folderId,
  });
}

export async function reviewConversationExport(
  client: KoinonClient,
  tenant: string,
  threadId: string,
  messageIds: string[],
) {
  return client.exports.review(tenant, {
    kind: "conversation",
    format: "markdown",
    thread_id: threadId,
    message_ids: messageIds,
    include_evidence: true,
  });
}

export async function createReviewedExport(
  client: KoinonClient,
  tenant: string,
  reviewed: ExportReview,
  personConfirmed: boolean,
) {
  if (!personConfirmed) throw new Error("Display the exact review and ask first");
  return client.exports.create(tenant, {
    review_id: reviewed.id,
    expected_revision: reviewed.revision,
  });
}

export async function createReviewedShare(
  client: KoinonClient,
  tenant: string,
  reviewed: ShareReview,
  personConfirmed: boolean,
) {
  if (!personConfirmed) throw new Error("Review recipients and selected messages");
  return client.shares.create(tenant, {
    review_id: reviewed.id,
    expected_revision: reviewed.revision,
    ...(reviewed.recipient_policy !== undefined
      ? { recipient_policy: reviewed.recipient_policy }
      : {}),
    expires_in_hours: 24,
  });
}

async function main(): Promise<void> {
  const threads = await connect().chat.threads(required("KOINON_TENANT_ID"), {
    query: { page: 1, page_size: 25 },
  });
  for (const thread of threads.items)
    console.log(thread.id, thread.title, thread.revision);
}

if (isMain(import.meta.url)) await main();
