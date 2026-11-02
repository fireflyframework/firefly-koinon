// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { RetainedUploadJournal } from './library-retained-uploads-journal';
import type { RetainedUploadRequest } from './library-retained-uploads-contract';
const action: RetainedUploadRequest = {
  subject: 'alex',
  tenantId: 'north',
  batchId: 'batch',
  itemId: 'item',
  operation: 'recover_original',
  expectedRevision: 2,
  key: 'original-key',
};
function setup() {
  const values = new Map<string, string>();
  return {
    values,
    journal: new RetainedUploadJournal({
      getItem: (key) => values.get(key) ?? null,
      setItem: (key, value) => {
        values.set(key, value);
      },
      removeItem: (key) => {
        values.delete(key);
      },
    }),
  };
}
it('retains exact action fields without original filenames, content or credentials', () => {
  const { journal, values } = setup();
  journal.put(action);
  expect(journal.forBatch('alex', 'north', 'batch')).toEqual([action]);
  expect(journal.forBatch('sam', 'north', 'batch')).toEqual([]);
  expect(journal.forBatch('alex', 'south', 'batch')).toEqual([]);
  expect([...values.values()].join('')).not.toMatch(/filename|content|token|endpoint/);
});
it('rejects arbitrary fields and conflicting reuse of a saved key', () => {
  const { journal } = setup();
  expect(() => journal.put({ ...action, token: 'secret' } as RetainedUploadRequest)).toThrow();
  journal.put(action);
  expect(() => journal.put({ ...action, expectedRevision: 3 })).toThrow();
  journal.clear({ ...action, key: 'other-key' });
  expect(journal.forBatch('alex', 'north', 'batch')).toEqual([action]);
  journal.clear(action);
  expect(journal.forBatch('alex', 'north', 'batch')).toEqual([]);
});
it('preserves unresolved entries rather than evicting them at the storage bound', () => {
  const { journal } = setup();
  for (let i = 0; i < 8; i++) journal.put({ ...action, key: 'key-' + i, batchId: 'batch-' + i });
  expect(() => journal.put({ ...action, key: 'extra' })).toThrow();
  expect(journal.forBatch('alex', 'north', 'batch-0')).toHaveLength(1);
});
