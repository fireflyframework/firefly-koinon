// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import type { CatalogEntry, CatalogBrowseOutput, Page, ResourceKind } from '@fireflyframework/koinon-sdk';
export type KoinonView =
  | 'catalog'
  | 'sources'
  | 'search'
  | 'queries'
  | 'jobs'
  | 'lineage'
  | 'members'
  | 'audit'
  | 'providers'
  | 'advanced';
export interface KoinonScope {
  tenantId: string;
  workspaceId?: string;
  projectId?: string;
  resourceId?: string;
}
export const KIND_LABELS: Record<ResourceKind, string> = {
  workspace: 'Workspace',
  project: 'Project',
  collection: 'Collection',
  corpus: 'Corpus',
  source: 'Source',
  document: 'Document',
  dataset: 'Dataset',
  chunk: 'Chunk',
  table: 'Table',
  index_version: 'Index version',
  query_session: 'Query session',
};
export const PARENT_KINDS: Record<ResourceKind, (ResourceKind | null)[]> = {
  workspace: [null],
  project: ['workspace'],
  collection: ['project'],
  corpus: ['project'],
  source: ['collection', 'corpus'],
  document: ['source'],
  dataset: ['source'],
  chunk: ['document'],
  table: ['dataset'],
  index_version: ['collection', 'corpus', 'source', 'dataset'],
  query_session: ['project'],
};
export const NAVIGATION: { id: KoinonView; label: string; icon: string; group: string }[] = [
  { id: 'catalog', label: 'Knowledge library', icon: 'grid', group: 'knowledge' },
  { id: 'sources', label: 'Sources', icon: 'upload', group: 'knowledge' },
  { id: 'search', label: 'Search & answers', icon: 'search', group: 'knowledge' },
  { id: 'queries', label: 'Explore datasets', icon: 'table', group: 'knowledge' },
  { id: 'jobs', label: 'Activity', icon: 'jobs', group: 'operations' },
  { id: 'lineage', label: 'Lineage', icon: 'lineage', group: 'operations' },
  { id: 'members', label: 'Members', icon: 'users', group: 'administration' },
  { id: 'audit', label: 'Audit trail', icon: 'shield', group: 'administration' },
  { id: 'providers', label: 'Providers', icon: 'settings', group: 'administration' },
  { id: 'advanced', label: 'Structured tools', icon: 'code', group: 'administration' },
];

export interface FolderPageState {ids:string[];page?:number;pages?:number;total?:number;next_cursor?:string|null;}

/** Adapt authorized browse results without inventing totals or numbered pages. */
export function catalogBrowsePage(result: CatalogBrowseOutput): Page<CatalogEntry> {
  return {
    items: result.items.map(entry => {
      if (!Object.hasOwn(KIND_LABELS, entry.kind)) throw Error('The catalog returned an unsupported resource kind.');
      return {
        ...entry, kind: entry.kind as ResourceKind, description: entry.description ?? '',
        metadata: entry.metadata ?? {}, parent_id: entry.parent_id ?? null,
        workspace_id: entry.workspace_id ?? null, project_id: entry.project_id ?? null,
        created_by: entry.created_by ?? undefined, updated_by: entry.updated_by ?? undefined,
        updated_at: entry.updated_at ?? undefined,
      };
    }),
    actors: Object.fromEntries(Object.entries(result.actors ?? {}).map(([id, actor]) => [id, {...actor, avatar_data_url: actor.avatar_data_url ?? null, avatar_version: actor.avatar_version ?? null}])),
    summaries: Object.fromEntries(result.items.flatMap(({id}) => {
      const summary = result.summaries?.[id];
      if (!summary) return [];
      return [[id, {
        child_count: summary.child_count ?? null,
        document_count: summary.document_count ?? null,
        dataset_count: summary.dataset_count ?? null,
        table_count: summary.table_count ?? null,
        row_count: summary.row_count ?? null,
        column_count: summary.column_count ?? null,
        page_count: summary.page_count ?? null,
        size_bytes: summary.size_bytes ?? null,
        format: summary.format ?? null,
        language: summary.language ?? null,
        tags: summary.tags ?? [],
      }]];
    })),
    next_cursor: result.next_cursor ?? null,
  };
}
