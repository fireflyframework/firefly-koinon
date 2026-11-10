// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import type { ContextResponse } from '@fireflyframework/koinon-sdk';

export function activityAdministrator(
  context: ContextResponse | null,
  tenantId: string,
  now: number,
): boolean {
  return !!context?.memberships.some(
    (grant) =>
      grant.subject === context.subject &&
      grant.active &&
      grant.tenant_id === tenantId &&
      !grant.workspace_id &&
      grant.role === 'admin' &&
      (!grant.expires_at || Date.parse(grant.expires_at) > now),
  );
}
