// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { availableTokenScopes, tokenDependencies, tokenScopeGroup } from './token-permissions';
const scopes = [
  { id: 'catalog:read', name: 'Browse', dependencies: [] },
  { id: 'catalog:write', name: 'Maintain', dependencies: ['catalog:read'] },
  { id: 'ingest:write', name: 'Import', dependencies: ['catalog:read', 'catalog:write'] },
  { id: 'members:write', name: 'People', dependencies: [] },
  { id: 'profile:write', name: 'Profile', dependencies: ['profile:read'] },
  { id: 'profile:read', name: 'Read profile', dependencies: [] },
];
it('offers organization management only from current organization permissions', () => {
  expect(availableTokenScopes(scopes, new Set()).map((s) => s.id)).not.toContain('members:write');
  expect(availableTokenScopes(scopes, new Set(['members:write'])).map((s) => s.id)).toContain(
    'members:write',
  );
  expect(availableTokenScopes(scopes, new Set()).map((s) => s.id)).toContain('ingest:write');
});
it('includes all advertised dependencies without inventing an unavailable permission', () => {
  expect(tokenDependencies(['ingest:write'], scopes)).toEqual([
    'catalog:read',
    'catalog:write',
    'ingest:write',
  ]);
  expect(tokenDependencies(['unknown'], scopes)).toEqual([]);
  expect(
    tokenDependencies(
      ['ingest:write'],
      scopes.filter((s) => s.id !== 'catalog:write'),
    ),
  ).toEqual([]);
});
it('separates resource maintenance from organization and personal permissions', () => {
  expect(tokenScopeGroup('ingest:write')).toBe('write');
  expect(tokenScopeGroup('catalog:read')).toBe('read');
  expect(tokenScopeGroup('jobs:manage')).toBe('organization');
  expect(tokenScopeGroup('profile:write')).toBe('profile');
});
it('rejects cyclic dependency graphs', () => {
  expect(
    tokenDependencies(
      ['a'],
      [
        { id: 'a', name: 'A', dependencies: ['b'] },
        { id: 'b', name: 'B', dependencies: ['a'] },
      ],
    ),
  ).toEqual([]);
});
it('removes knowledge writes after current workspace access changes while preserving personal scopes', () => {
  const available = availableTokenScopes(scopes, new Set(), new Set(['catalog:read']));
  expect(available.map((s) => s.id)).toEqual(['catalog:read', 'profile:write', 'profile:read']);
});
