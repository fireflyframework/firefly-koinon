// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import type { KoinonFacade } from '@fireflyframework/koinon-angular';

export function canCurateKnowledge(facade: KoinonFacade, workspaceId: string) {
  const permissions = new Set(facade.permissions());
  const context = facade.context();
  const workspace = (context?.workspaces ?? []).find((entry) => entry.id === workspaceId &&
    entry.tenant_id === facade.tenantId() && entry.kind === 'workspace' && entry.status !== 'archived');
  const scoped = workspace ? context?.workspace_permissions?.[workspaceId] : undefined;
  if (Array.isArray(scoped) && scoped.every((permission) => typeof permission === 'string'))
    for (const permission of scoped) permissions.add(permission);
  return Boolean(facade.tenantId() && context?.subject && !facade.authRequired() &&
    ['chat:use', 'catalog:read', 'catalog:write', 'ingest:write'].every((permission) => permissions.has(permission)));
}
