// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { DOCUMENT } from '@angular/common';
import { TestBed } from '@angular/core/testing';
import type { ContextResponse } from '@fireflyframework/koinon-sdk';
import { OrganizationSelection } from './organization-selection';

const context: ContextResponse = {
  subject: 'reader-one',
  tenants: [
    { id: 'north', name: 'North', roles: [], permissions: ['catalog:read'] },
    { id: 'south', name: 'South', roles: [], permissions: ['catalog:read'] },
  ],
  memberships: [],
  workspaces: [],
};
function environment(values = new Map<string, string>(), denied = false, base = '/app/') {
  TestBed.configureTestingModule({
    providers: [
      {
        provide: DOCUMENT,
        useValue: {
          baseURI: 'https://knowledge.example.test' + base,
          defaultView: {
            sessionStorage: {
              getItem(key: string) {
                if (denied) throw new Error('Denied');
                return values.get(key) ?? null;
              },
              setItem(key: string, value: string) {
                if (denied) throw new Error('Denied');
                values.set(key, value);
              },
              removeItem(key: string) {
                if (denied) throw new Error('Denied');
                values.delete(key);
              },
            },
          },
        },
      },
    ],
  });
  return TestBed.inject(OrganizationSelection);
}
it('restores a tab preference for the fresh subject before selecting a catalog context', () => {
  const values = new Map<string, string>();
  const first = environment(values);
  expect(first.resolve(context, '')).toBe('north');
  first.remember({ tenantId: 'south', resourceId: 'private-resource' });
  expect([...values.values()].map((value) => JSON.parse(value))).toEqual(['south']);
  TestBed.resetTestingModule();
  const reloaded = environment(values);
  expect(reloaded.resolve(context, '')).toBe('south');
  expect(reloaded.resolve({ ...context, tenants: [...context.tenants].reverse() }, '')).toBe(
    'south',
  );
});
it('isolates preferences by deployment base and authenticated subject', () => {
  const values = new Map<string, string>();
  const first = environment(values);
  first.resolve(context, '');
  first.remember({ tenantId: 'south' });
  expect(first.resolve({ ...context, subject: 'reader-two' }, '')).toBe('north');
  expect(first.resolve(context, '')).toBe('south');
  TestBed.resetTestingModule();
  expect(environment(values, false, '/another/').resolve(context, '')).toBe('north');
});
it('lets authorized explicit share or accepted invitation scope win over a preference', () => {
  const service = environment();
  service.resolve(context, '');
  service.remember({ tenantId: 'south' });
  expect(service.resolve(context, 'north')).toBe('north');
  expect(service.resolve(context, 'not-authorized')).toBe('north');
});
it('revalidates memory and tab preferences when a membership is removed', () => {
  const values = new Map<string, string>();
  const service = environment(values);
  service.resolve(context, '');
  service.remember({ tenantId: 'south' });
  expect(service.resolve({ ...context, tenants: [context.tenants[0]] }, '')).toBe('north');
  service.remember({ tenantId: 'south' });
  expect([...values.values()]).not.toContain('"south"');
  expect(service.resolve({ ...context, tenants: [] }, '')).toBe('');
});
for (const saved of [
  'broken',
  'null',
  '[]',
  '{}',
  '"https://other.example/?token=secret"',
  '{"tenantId":"south","token":"secret"}',
])
  it('discards malformed or authority-bearing tab state: ' + saved, () => {
    const values = new Map([['koinon.organization:/app/:reader-one', saved]]);
    expect(environment(values).resolve(context, '')).toBe('north');
    expect(values.size).toBe(0);
  });
it('uses in-memory selection for retry when tab storage is denied', () => {
  const service = environment(new Map(), true);
  expect(service.resolve(context, '')).toBe('north');
  expect(() => service.remember({ tenantId: 'south' })).not.toThrow();
  expect(service.resolve(context, '')).toBe('south');
  expect(service.resolve({ ...context, subject: 'other' }, '')).toBe('north');
});
it('ignores selection events until authenticated context has been observed', () => {
  const values = new Map<string, string>(),
    service = environment(values);
  service.remember({ tenantId: 'south' });
  expect(values.size).toBe(0);
});
