// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import type {
  ContextResponse,
  FileBatchItemView,
  FileBatchView,
} from '@fireflyframework/koinon-sdk';
export type RetainedUploadOperation =
  | 'submit'
  | 'cancel'
  | 'recover_original'
  | 'reconcile'
  | 'retry_processing'
  | 'finalize_publication'
  | 'acknowledge_commit';
export interface RetainedUploadScope {
  owner: object | null;
  subject: string;
  tenantId: string;
  clientRevision: number;
  accessRevision?: number;
  transport: object | null;
  allowed: boolean;
}
export interface RetainedUploadRequest {
  subject: string;
  tenantId: string;
  batchId: string;
  itemId: string | null;
  operation: RetainedUploadOperation;
  expectedRevision: number;
  key: string;
}
export function sameRetainedUploadScope(a: RetainedUploadScope, b: RetainedUploadScope) {
  return (
    a.owner === b.owner &&
    a.subject === b.subject &&
    a.tenantId === b.tenantId &&
    a.clientRevision === b.clientRevision &&
    a.accessRevision === b.accessRevision &&
    a.transport === b.transport &&
    a.allowed === b.allowed
  );
}
export function retainedUploadAccess(
  context: ContextResponse | null,
  tenantId: string,
  workspaceId?: string,
  now = Date.now(),
) {
  const grants =
    context?.memberships.filter(
      (m) =>
        m.subject === context.subject &&
        m.tenant_id === tenantId &&
        m.active &&
        (!workspaceId || m.workspace_id === null || m.workspace_id === workspaceId) &&
        (m.expires_at == null || Date.parse(m.expires_at) > now),
    ) ?? [];
  const permissions = new Set([
    ...(context?.tenants.find((t) => t.id === tenantId)?.permissions ?? []),
    ...(workspaceId
      ? (context?.workspace_permissions?.[workspaceId] ?? [])
      : grants.flatMap((m) =>
          m.workspace_id ? (context?.workspace_permissions?.[m.workspace_id] ?? []) : [],
        )),
  ]);
  const read = !!context?.subject && grants.length > 0 && permissions.has('catalog:read');
  return {
    read,
    write:
      read &&
      grants.some((m) => ['editor', 'operator', 'admin'].includes(m.role)) &&
      permissions.has('catalog:write') &&
      permissions.has('ingest:write'),
  };
}
export function retainedUploadActions(
  batch: FileBatchView,
  items: FileBatchItemView[],
  itemId?: string,
  now = Date.now(),
): RetainedUploadOperation[] {
  if (
    batch.status === 'expired' ||
    (batch.status === 'staging' && Date.parse(batch.expires_at) <= now)
  )
    return [];
  if (itemId) {
    const item = items.find((row) => row.id === itemId);
    if (!item) return [];
    if (
      !batch.cancellation_requested &&
      batch.status === 'staging' &&
      item.status === 'awaiting_upload'
    )
      return ['recover_original'];
    if (['failed', 'reconciling'].includes(item.status) && item.job_id) return ['reconcile'];
    return [];
  }
  const actions: RetainedUploadOperation[] = [];
  if (
    batch.status === 'staging' &&
    !batch.cancellation_requested &&
    items.length === batch.total_items &&
    items.length > 0 &&
    items.every((i) => i.status === 'staged')
  )
    actions.push('submit');
  if (
    !batch.cancellation_requested &&
    ['staging', 'queued', 'running', 'reconciling'].includes(batch.status)
  )
    actions.push('cancel');
  return actions;
}
