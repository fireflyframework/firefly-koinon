// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { retainedUploadActions, retainedUploadAccess } from './library-retained-uploads-contract';
import type {
  ContextResponse,
  FileBatchView,
  FileBatchItemView,
} from '@fireflyframework/koinon-sdk';
const batch = {
  status: 'staging',
  cancellation_requested: false,
  total_items: 1,
  expires_at: '2099-01-01T00:00:00Z',
} as FileBatchView;
it('offers explicit submit only after every current original is staged', () => {
  const item = { id: 'item', status: 'awaiting_upload', job_id: null } as FileBatchItemView;
  expect(retainedUploadActions(batch, [item], item.id)).toContain('recover_original');
  expect(retainedUploadActions(batch, [item])).not.toContain('submit');
  expect(retainedUploadActions(batch, [{ ...item, status: 'staged' }])).toContain('submit');
  expect(
    retainedUploadActions({ ...batch, status: 'expired' }, [{ ...item, status: 'staged' }]),
  ).not.toContain('submit');
});
it('requires a current grant and matching workspace permissions for mutations', () => {
  const context = {
    subject: 'alex',
    tenants: [{ id: 'north', permissions: [] }],
    memberships: [
      {
        id: 'grant',
        tenant_id: 'north',
        subject: 'alex',
        workspace_id: 'one',
        role: 'editor',
        active: true,
      },
    ],
    workspace_permissions: { one: ['catalog:read', 'catalog:write', 'ingest:write'] },
    workspaces: [],
  } as unknown as ContextResponse;
  expect(retainedUploadAccess(context, 'north', 'one')).toEqual({ read: true, write: true });
  expect(retainedUploadAccess(context, 'north', 'two')).toEqual({ read: false, write: false });
  expect(retainedUploadAccess({ ...context, memberships: [] }, 'north', 'one')).toEqual({
    read: false,
    write: false,
  });
});
it('keeps native outcome inspection available after staging expiry or cancellation', () => {
  const expired = { ...batch, status: 'running' as const, expires_at: '2000-01-01T00:00:00Z' };
  expect(retainedUploadActions(expired, [])).toContain('cancel');
  const item = { id: 'item', status: 'reconciling', job_id: 'job' } as FileBatchItemView;
  expect(
    retainedUploadActions(
      { ...expired, status: 'reconciling', cancellation_requested: true },
      [item],
      'item',
    ),
  ).toContain('reconcile');
});
