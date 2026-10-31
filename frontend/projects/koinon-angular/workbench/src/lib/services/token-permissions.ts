// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import type { TokenScopeOptions } from '@fireflyframework/koinon-sdk';
type TokenScope = TokenScopeOptions['items'][number];
export type TokenScopeGroup = 'read' | 'write' | 'organization' | 'profile';
const resourceScopes = new Set([
  'catalog:read',
  'catalog:write',
  'knowledge:search',
  'query:execute',
  'chat:use',
  'ingest:write',
  'exports:read',
  'exports:write',
  'shares:read',
  'shares:write',
  'evidence:read',
]);
export function tokenScopeGroup(id: string): TokenScopeGroup {
  if (id === 'profile:read' || id === 'profile:write') return 'profile';
  if (!resourceScopes.has(id)) return 'organization';
  return id.endsWith(':write') ? 'write' : 'read';
}
export function availableTokenScopes(
  scopes: readonly TokenScope[],
  organizationPermissions: ReadonlySet<string>,
  resourcePermissions?: ReadonlySet<string>,
): TokenScope[] {
  return scopes.filter(
    (scope) =>
      tokenScopeGroup(scope.id) === 'profile' ||
      (tokenScopeGroup(scope.id) === 'organization'
        ? organizationPermissions.has(scope.id)
        : !resourcePermissions || resourcePermissions.has(scope.id)),
  );
}
export function tokenDependencies(
  selected: readonly string[],
  scopes: readonly TokenScope[],
): string[] {
  const options = new Map(scopes.map((scope) => [scope.id, scope]));
  const result = new Set<string>(),
    visiting = new Set<string>();
  const add = (id: string): boolean => {
    if (result.has(id)) return true;
    const option = options.get(id);
    if (!option || visiting.has(id)) return false;
    visiting.add(id);
    if (!option.dependencies.every(add)) return false;
    visiting.delete(id);
    result.add(id);
    return true;
  };
  return selected.every(add) ? [...result] : [];
}
