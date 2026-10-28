// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import type { ChatFolder, ChatThread, KnowledgeScope, Page } from '@fireflyframework/koinon-sdk';
export interface ConversationPage<T> {
  items: readonly T[];
  page: number;
  pages: number | null;
  total: number | null;
  pending: boolean;
  error: string;
}
export interface ConversationBranch {
  folder: ChatFolder;
  expanded: boolean;
  children: ConversationPage<ChatFolder>;
  threads: ConversationPage<ChatThread>;
}
export function emptyConversationPage<T>(): ConversationPage<T> {
  return { items: [], page: 0, pages: null, total: null, pending: false, error: '' };
}
export function observedPage<T extends { id: string }>(
  previous: ConversationPage<T>,
  page: Page<T>,
  append: boolean,
): ConversationPage<T> {
  if (
    !Number.isInteger(page.page) ||
    !Number.isInteger(page.pages) ||
    !Number.isInteger(page.total) ||
    page.page! < 1 ||
    page.pages! < 0 ||
    page.total! < 0
  )
    throw Error('Conversation paging metadata is unavailable.');
  const items = append ? [...previous.items, ...page.items] : page.items;
  return {
    items: [...new Map(items.map((row) => [row.id, row])).values()],
    page: page.page!,
    pages: page.pages!,
    total: page.total!,
    pending: false,
    error: '',
  };
}
export function scopeWithin(scope: KnowledgeScope, limit: KnowledgeScope): boolean {
  for (const key of ['workspace_id', 'project_id', 'collection_id'] as const)
    if (limit[key] != null && scope[key] !== limit[key]) return false;
  return (
    limit.asset_ids == null ||
    (scope.asset_ids != null && scope.asset_ids.every((id) => limit.asset_ids!.includes(id)))
  );
}
