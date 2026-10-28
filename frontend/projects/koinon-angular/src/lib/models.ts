// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import type { ResourceKind } from '@fireflyframework/koinon-sdk';
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

export interface FolderPageState {ids:string[];page?:number;pages?:number;total?:number;}
