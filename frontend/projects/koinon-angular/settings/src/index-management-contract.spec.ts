// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import type {
  ContextResponse,
  KnowledgeConnection,
  KnowledgeIndexView,
} from '@fireflyframework/koinon-sdk';
import {
  indexPermissions,
  embeddingAssignment,
  availableIndexActions,
} from './index-management-contract';

const context: ContextResponse = {
  subject: 'issuer|alex',
  tenants: [
    {
      id: 'north',
      name: 'North',
      roles: ['admin'],
      permissions: ['catalog:read', 'indexes:manage', 'providers:write'],
    },
  ],
  memberships: [
    {
      id: 'grant',
      subject: 'issuer|alex',
      tenant_id: 'north',
      workspace_id: null,
      role: 'admin',
      active: true,
    },
  ],
  workspaces: [
    {
      id: 'space',
      tenant_id: 'north',
      kind: 'workspace',
      name: 'Space',
      status: 'active',
      parent_id: null,
      workspace_id: 'space',
      project_id: null,
      description: '',
      metadata: {},
      created_at: '2026-11-01T00:00:00Z',
    },
  ],
};
it('requires current membership, workspace and both management permissions', () => {
  expect(indexPermissions(context, 'north', 'space')).toEqual({ read: true, manage: true });
  expect(indexPermissions({ ...context, memberships: [] }, 'north', 'space')).toEqual({
    read: false,
    manage: false,
  });
  expect(indexPermissions(context, 'north', 'other')).toEqual({ read: false, manage: false });
  expect(
    indexPermissions(
      {
        ...context,
        memberships: context.memberships.map((row) => ({
          ...row,
          expires_at: '2020-01-01T00:00:00Z',
        })),
      },
      'north',
      'space',
    ).manage,
  ).toBe(false);
  expect(
    indexPermissions(
      {
        ...context,
        tenants: context.tenants.map((row) => ({
          ...row,
          permissions: ['catalog:read', 'indexes:manage'],
        })),
      },
      'north',
      'space',
    ),
  ).toEqual({ read: true, manage: false });
});
it('accepts workspace authority without borrowing a different workspace grant', () => {
  const scoped = {
    ...context,
    tenants: context.tenants.map((row) => ({ ...row, permissions: [] })),
    memberships: context.memberships.map((row) => ({
      ...row,
      workspace_id: 'space',
      role: 'operator' as const,
    })),
    workspace_permissions: { space: ['catalog:read', 'indexes:manage', 'providers:write'] },
  };
  expect(indexPermissions(scoped, 'north', 'space').manage).toBe(true);
  expect(
    indexPermissions(
      {
        ...scoped,
        memberships: scoped.memberships.map((row) => ({ ...row, workspace_id: 'different' })),
      },
      'north',
      'space',
    ).manage,
  ).toBe(false);
});
it('selects a disabled workspace override without falling back to the organization', () => {
  const inherited = {
    id: 'default',
    workspace_id: null,
    domain: 'documents',
    role: 'documents.embedding',
    revision: 2,
    enabled: true,
  } as KnowledgeConnection;
  const override = {
    ...inherited,
    id: 'override',
    workspace_id: 'space',
    revision: 5,
    enabled: false,
  };
  expect(embeddingAssignment([override], [inherited], 'documents', 'space')).toBe(override);
  expect(embeddingAssignment([], [inherited], 'documents', 'space')).toBe(inherited);
  expect(() =>
    embeddingAssignment(
      [override, { ...override, id: 'duplicate' }],
      [inherited],
      'documents',
      'space',
    ),
  ).toThrow();
});
it('offers only native lifecycle actions for the current observed state', () => {
  const row = {
    status: 'queued',
    active: false,
    recovery_required: false,
    indexed: false,
    chunk_count: 2,
    vector_count: 0,
  } as KnowledgeIndexView;
  expect(availableIndexActions(row)).toEqual(['cancel']);
  expect(
    availableIndexActions({ ...row, status: 'ready', indexed: true, vector_count: 2 }),
  ).toEqual(['activate', 'resume']);
  expect(availableIndexActions({ ...row, status: 'active', active: true })).toEqual([]);
  expect(availableIndexActions({ ...row, status: 'activating', recovery_required: true })).toEqual([
    'finish',
    'restore_previous',
  ]);
  expect(availableIndexActions({ ...row, status: 'ready', indexed: false })).toEqual(['resume']);
});
