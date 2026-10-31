// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import type { OrganizationPerson, OrganizationPersonPatch } from '@fireflyframework/koinon-sdk';
export type PositionFields = Pick<OrganizationPersonPatch, 'job_title' | 'unit_id' | 'manager_id'>;
export function positionPatch(
  person: OrganizationPerson,
  draft: PositionFields,
  manageLocally: boolean,
): PositionFields {
  const before: PositionFields = {
    job_title: person.job_title ?? null,
    unit_id: person.unit?.id ?? null,
    manager_id: person.manager?.id ?? null,
  };
  const result: PositionFields = {};
  for (const field of ['job_title', 'unit_id', 'manager_id'] as const)
    if (
      (manageLocally || !person.managed_fields?.includes(field)) &&
      draft[field] !== before[field]
    )
      result[field] = draft[field];
  return result;
}
