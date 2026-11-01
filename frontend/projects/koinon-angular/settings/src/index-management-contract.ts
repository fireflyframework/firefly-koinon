// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import type {
  ContextResponse,
  IndexActivateInput,
  IndexCreateInput,
  IndexRevisionInput,
  KnowledgeConnection,
  KnowledgeIndexView,
} from '@fireflyframework/koinon-sdk';
export type IndexDomain = 'documents' | 'structured';
export type IndexActionName = 'activate' | 'cancel' | 'resume' | 'finish' | 'restore_previous';
export interface IndexManagementScope {
  owner: object | null;
  subject: string;
  tenantId: string;
  workspaceId: string;
  domain: IndexDomain;
  clientRevision: number;
  read: boolean;
  manage: boolean;
}
export type IndexWrite =
  | { operation: 'create'; input: IndexCreateInput; targetId: null; key: string }
  | { operation: 'resume'; input: IndexRevisionInput; targetId: string; key: string }
  | { operation: 'activate'; input: IndexActivateInput; targetId: string; key: null }
  | { operation: 'cancel'; input: IndexRevisionInput; targetId: string; key: null };
export interface SavedIndexWrite {
  subject: string;
  tenantId: string;
  workspaceId: string;
  domain: IndexDomain;
  createdAt: number;
  write: IndexWrite;
}
export function sameIndexScope(a: IndexManagementScope, b: IndexManagementScope) {
  return (
    a.owner === b.owner &&
    a.subject === b.subject &&
    a.tenantId === b.tenantId &&
    a.workspaceId === b.workspaceId &&
    a.domain === b.domain &&
    a.clientRevision === b.clientRevision &&
    a.read === b.read &&
    a.manage === b.manage
  );
}
export function indexPermissions(
  context: ContextResponse | null,
  tenantId: string,
  workspaceId: string,
  now = Date.now(),
) {
  const workspace = context?.workspaces.find(
    (row) =>
      row.id === workspaceId &&
      row.tenant_id === tenantId &&
      row.kind === 'workspace' &&
      row.status !== 'archived',
  );
  const grants =
    context?.memberships.filter(
      (row) =>
        row.subject === context.subject &&
        row.tenant_id === tenantId &&
        row.active &&
        (row.workspace_id === null || row.workspace_id === workspaceId) &&
        (row.expires_at == null || Date.parse(row.expires_at) > now),
    ) ?? [];
  const permissions = new Set([
    ...(context?.tenants.find((row) => row.id === tenantId)?.permissions ?? []),
    ...(context?.workspace_permissions?.[workspaceId] ?? []),
  ]);
  const read =
    !!context?.subject && !!workspace && grants.length > 0 && permissions.has('catalog:read');
  return {
    read,
    manage:
      read &&
      grants.some((row) => row.role === 'admin' || row.role === 'operator') &&
      permissions.has('indexes:manage') &&
      permissions.has('providers:write'),
  };
}
export function embeddingAssignment(
  workspace: KnowledgeConnection[],
  organization: KnowledgeConnection[],
  domain: IndexDomain,
  workspaceId: string,
) {
  const role = domain + '.embedding',
    selected = workspace.filter(
      (row) => row.domain === domain && row.role === role && row.workspace_id === workspaceId,
    ),
    inherited = organization.filter(
      (row) => row.domain === domain && row.role === role && row.workspace_id == null,
    );
  if (selected.length > 1 || (!selected.length && inherited.length > 1))
    throw new Error('Ambiguous embedding assignment');
  return selected[0] ?? inherited[0] ?? null;
}
export function availableIndexActions(row: KnowledgeIndexView): IndexActionName[] {
  if (row.active || row.status === 'active') return [];
  if (row.status === 'activating')
    return row.recovery_required ? ['finish', 'restore_previous'] : [];
  if (['queued', 'building', 'awaiting_index'].includes(row.status)) return ['cancel'];
  const actions: IndexActionName[] = [];
  if (
    ['ready', 'retired'].includes(row.status) &&
    row.indexed &&
    row.chunk_count === row.vector_count
  )
    actions.push('activate');
  if (['failed', 'cancelled', 'ready', 'retired'].includes(row.status)) actions.push('resume');
  return actions;
}
