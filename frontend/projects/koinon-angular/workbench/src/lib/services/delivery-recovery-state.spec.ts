// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { createCommunicationsApi } from '@fireflyframework/koinon-sdk/communications';
import { DeliveryRecoveryState } from '../../../../communications/admin/delivery-recovery-state';
import { DeliveryRecoveryJournal } from '../../../../communications/admin/delivery-recovery-journal';
function fixture() {
  let scope = { key: 'credential-one', subject: 'alex', tenantId: 'north', allowed: true };
  const rows = new Map<string, string>();
  const journal = new DeliveryRecoveryJournal({
    getItem: (k) => rows.get(k) ?? null,
    setItem: (k, v) => {
      rows.set(k, v);
    },
    removeItem: (k) => {
      rows.delete(k);
    },
  });
  const options = {
    delivery_id: 'original',
    generation: 2,
    submission_status: 'unknown',
    attempt_count: 1,
    can_inspect: true,
    inspection_reason: null,
    provider_binding_state: 'verified',
    can_recover_welcome: true,
    recovery_reason: null,
    contact_id: 'approved-contact',
    contact_revision: 3,
    possible_original_late_arrival: true,
  };
  let uncertain = false;
  const calls: { method: string; path: string; body: unknown; headers: unknown }[] = [];
  const api = createCommunicationsApi({
    stream: () => {
      throw Error('Unexpected stream');
    },
    request: async <T>(
      method: string,
      path: string,
      request: { body?: unknown; headers?: unknown } = {},
    ) => {
      calls.push({ method, path, body: request.body, headers: request.headers });
      if (method === 'GET')
        return (path.endsWith('/recovery') ? options : { items: [], has_more: false }) as T;
      if (uncertain) throw new TypeError('Private network failure');
      return (
        path.endsWith('/welcome-recovery')
          ? {
              original_delivery_id: 'original',
              delivery_id: 'new-welcome',
              status: 'queued',
              possible_original_late_arrival: true,
            }
          : {
              id: 'observation',
              delivery_id: 'original',
              operation_state: 'accepted',
              recipient_state: 'not_observed',
              source: 'operation_lookup',
              checked_at: null,
              reason_code: null,
            }
      ) as T;
    },
  });
  const make = () => new DeliveryRecoveryState({ scope: () => scope, api: () => api, journal });
  return {
    options,
    state: make(),
    make,
    journal,
    calls,
    scope: (change: Partial<typeof scope>) => {
      scope = { ...scope, ...change };
    },
    uncertain: (value: boolean) => {
      uncertain = value;
    },
  };
}
it('reads saved observations without contacting the provider or sending another welcome', async () => {
  const f = fixture();
  await f.state.open('original');
  expect(f.state.view().options?.generation).toBe(2);
  expect(f.calls.every((call) => call.method === 'GET')).toBe(true);
  await f.state.review('welcome');
  await f.state.confirm(false);
  expect(f.calls.every((call) => call.method === 'GET')).toBe(true);
  await f.state.confirm(true);
  expect(f.calls.filter((call) => call.method === 'POST')).toHaveLength(1);
  expect(f.state.view().acknowledgment?.delivery_id).toBe('new-welcome');
  expect(f.state.view().pending).toEqual([]);
});
it('retains an ambiguous exact request and requires fresh authorization before explicit same-key reconciliation', async () => {
  const f = fixture();
  await f.state.open('original');
  await f.state.review('welcome');
  f.uncertain(true);
  await f.state.confirm(true);
  const saved = f.state.view().pending[0];
  expect(saved).toBeTruthy();
  f.scope({ key: 'credential-two' });
  f.state.sync();
  expect(f.state.view().pending).toEqual([]);
  const restored = f.make();
  await restored.open('original');
  expect(restored.view().pending).toHaveLength(1);
  expect(f.calls.filter((call) => call.method === 'POST')).toHaveLength(1);
  await restored.reviewSaved(restored.view().pending[0]);
  f.uncertain(false);
  await restored.confirm(true);
  const posts = f.calls.filter((call) => call.method === 'POST');
  expect(posts).toHaveLength(2);
  expect(posts[1].body).toEqual(posts[0].body);
  expect(posts[1].headers).toEqual(posts[0].headers);
  f.scope({ subject: 'other', key: 'another-account' });
  restored.sync();
  expect(restored.view().options).toBeNull();
  expect(restored.view().pending).toEqual([]);
});

it('rejects a forged delivery or an incomplete approved contact before exposing recovery', async () => {
  const f = fixture();
  f.options.delivery_id = 'other';
  await f.state.open('original');
  expect(f.state.view().options).toBeNull();
  f.options.delivery_id = 'original';
  f.options.contact_revision = 0;
  await f.state.open('original');
  expect(f.state.view().options).toBeNull();
  expect(f.calls.every((c) => c.method === 'GET')).toBe(true);
});
it('refuses a changed generation before sending a reviewed welcome', async () => {
  const f = fixture();
  await f.state.open('original');
  await f.state.review('welcome');
  f.options.generation++;
  await f.state.confirm(true);
  expect(f.calls.every((c) => c.method === 'GET')).toBe(true);
  expect(f.state.view().error).toContain('changed');
  expect(f.state.view().pending).toEqual([]);
});
it('hides prior observations and pending review immediately after administrator authority is lost', async () => {
  const f = fixture();
  await f.state.open('original');
  await f.state.review('welcome');
  f.scope({ allowed: false });
  expect(f.state.view().review).toBeNull();
  expect(f.state.view().options).toBeNull();
  await f.state.confirm(true);
  expect(f.calls.every((c) => c.method === 'GET')).toBe(true);
});
it('records provider acceptance without claiming recipient delivery', async () => {
  const f = fixture();
  await f.state.open('original');
  await f.state.review('inspect');
  await f.state.confirm(false);
  expect(f.state.view().history[0].operation_state).toBe('accepted');
  expect(f.state.view().history[0].recipient_state).toBe('not_observed');
  expect(f.state.view().notice).toContain('does not confirm');
  expect(f.state.view().pending).toEqual([]);
  expect(f.calls.filter((c) => c.method === 'POST')).toHaveLength(1);
});
