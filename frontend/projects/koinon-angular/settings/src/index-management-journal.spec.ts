// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { IndexActionJournal, INDEX_JOURNAL_KEY } from './index-management-journal';
import type { SavedIndexWrite } from './index-management-contract';
const action: SavedIndexWrite = {
  subject: 'issuer|alex',
  tenantId: 'north',
  workspaceId: 'space',
  domain: 'documents',
  createdAt: 1,
  write: {
    operation: 'create',
    targetId: null,
    key: 'stable-key',
    input: {
      workspace_id: 'space',
      domain: 'documents',
      provider_id: 'provider',
      model_id: 'embedding',
      expected_active_id: null,
      expected_connection_revision: null,
      batch_size: 32,
    },
  },
};
function storage() {
  const values = new Map<string, string>();
  return {
    values,
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => {
      values.set(key, value);
    },
    removeItem: (key: string) => {
      values.delete(key);
    },
  };
}
it('preserves an exact uncertain request/key across instances without returning another owner or scope', () => {
  const store = storage(),
    journal = new IndexActionJournal(store);
  journal.put(action);
  const restored = new IndexActionJournal(store);
  expect(restored.get(action)).toEqual(action);
  expect(restored.get({ ...action, subject: 'issuer|sam' })).toBeNull();
  expect(restored.get({ ...action, tenantId: 'south' })).toBeNull();
  expect(restored.get({ ...action, workspaceId: 'other' })).toBeNull();
  expect(restored.get({ ...action, domain: 'structured' })).toBeNull();
});
it('cannot overwrite an unresolved action with a new key or let a late result clear it', () => {
  const store = storage(),
    journal = new IndexActionJournal(store);
  journal.put(action);
  const different = { ...action, write: { ...action.write, key: 'new-key' } } as SavedIndexWrite;
  expect(() => journal.put(different)).toThrow();
  journal.clear(different);
  expect(journal.get(action)).toEqual(action);
  journal.clear(action);
  expect(journal.get(action)).toBeNull();
});
it.each([
  { ...action, write: { ...action.write, input: { ...action.write.input, secret: 'private' } } },
  {
    ...action,
    write: { ...action.write, input: { ...action.write.input, workspace_id: 'other' } },
  },
  {
    ...action,
    write: {
      ...action.write,
      input: { ...action.write.input, expected_connection_revision: true },
    },
  },
  { ...action, write: { ...action.write, input: { ...action.write.input, batch_size: 1000 } } },
  { ...action, write: { ...action.write, key: 'bad\nkey' } },
  { ...action, write: { ...action.write, operation: 'arbitrary' } },
])('rejects malformed or credential-bearing journal content before exposing a request', (value) => {
  const store = storage();
  store.values.set(INDEX_JOURNAL_KEY, JSON.stringify([value]));
  expect(() => new IndexActionJournal(store).get(action)).toThrow();
});
it('does not silently truncate a journal or proceed without durable tab storage', () => {
  const store = storage();
  store.values.set(INDEX_JOURNAL_KEY, 'x'.repeat(17000));
  expect(() => new IndexActionJournal(store).get(action)).toThrow();
  expect(() =>
    new IndexActionJournal({
      ...storage(),
      setItem: () => {
        throw new Error('blocked');
      },
    }).put(action),
  ).toThrow();
});
it('replaces only the exact unresolved activation with a reviewed forward recovery', () => {
  const store = storage(),
    journal = new IndexActionJournal(store);
  const previous: SavedIndexWrite = {
    ...action,
    write: {
      operation: 'activate',
      targetId: 'target',
      key: null,
      input: { expected_revision: 2, expected_active_id: 'old', expected_connection_revision: 4 },
    },
  };
  const recovery: SavedIndexWrite = {
    ...previous,
    createdAt: 2,
    write: {
      operation: 'activate',
      targetId: 'target',
      key: null,
      input: {
        expected_revision: 3,
        expected_active_id: 'target',
        expected_connection_revision: 4,
        recovery: 'finish',
      },
    },
  };
  journal.put(previous);
  journal.replaceAfterReview(previous, recovery);
  expect(journal.get(action)).toEqual(recovery);
  expect(() => journal.replaceAfterReview(previous, recovery)).toThrow();
  expect(() =>
    journal.replaceAfterReview(recovery, {
      ...recovery,
      write: { ...recovery.write, targetId: 'other' },
    } as SavedIndexWrite),
  ).toThrow();
});
