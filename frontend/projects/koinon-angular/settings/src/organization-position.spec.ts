// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { positionPatch } from './organization-position-fields';
import type { OrganizationPerson } from '@fireflyframework/koinon-sdk';
const person: OrganizationPerson = {
  id: 'p1',
  display_name: 'Alex',
  revision: 2,
  job_title: 'Engineer',
  unit: { id: 'u1', name: 'Platform', kind: 'team' },
  manager: { id: 'm1', display_name: 'Sam' },
  managed_fields: ['job_title'],
};
describe('organization position changes', () => {
  it('does not send managed or unchanged fields during a local edit', () => {
    expect(
      positionPatch(person, { job_title: 'Principal', unit_id: 'u2', manager_id: 'm1' }, false),
    ).toEqual({ unit_id: 'u2' });
  });
  it('allows explicit local ownership while preserving deliberate clearing', () => {
    expect(
      positionPatch(person, { job_title: 'Principal', unit_id: 'u1', manager_id: null }, true),
    ).toEqual({ job_title: 'Principal', manager_id: null });
  });
});
