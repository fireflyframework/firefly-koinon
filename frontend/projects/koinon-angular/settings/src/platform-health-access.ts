// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import type { ContextResponse } from '@fireflyframework/koinon-sdk';

export function platformHealthAccess(
  context: ContextResponse | null,
  tenantId: string,
  now = Date.now(),
): boolean {
  const permissions = context?.tenants.find((tenant) => tenant.id === tenantId)?.permissions ?? [];
  return (
    !!tenantId &&
    !!context?.subject &&
    permissions.includes('catalog:read') &&
    permissions.includes('audit:read') &&
    context.memberships.some(
      (grant) =>
        grant.subject === context.subject &&
        grant.tenant_id === tenantId &&
        grant.workspace_id === null &&
        grant.role === 'admin' &&
        grant.active === true &&
        (grant.expires_at == null || Date.parse(grant.expires_at) > now),
    )
  );
}
