// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import type { KoinonFacade } from '../koinon-facade';
import type { KoinonClientContext } from './client-context';
export function organizationContextKey(facade: KoinonFacade, clients: KoinonClientContext): string {
  return JSON.stringify([
    facade.context()?.subject,
    facade.tenantId(),
    facade.workspaceId(),
    clients.revision(),
    [...facade.tenantPermissions()].sort(),
    [...facade.permissions()].sort(),
  ]);
}
