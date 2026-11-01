// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import type { SavedIndexWrite } from './index-management-contract';
export const INDEX_JOURNAL_KEY = 'koinon:index-actions:v1';
type Scope = Pick<SavedIndexWrite, 'subject' | 'tenantId' | 'workspaceId' | 'domain'>;
const object = (value: unknown): value is Record<string, unknown> =>
  !!value && typeof value === 'object' && !Array.isArray(value);
const text = (value: unknown, max: number): value is string =>
  typeof value === 'string' && value.length > 0 && value.length <= max;
const positive = (value: unknown, max = 2147483646) =>
  Number.isSafeInteger(value) && Number(value) > 0 && Number(value) <= max;
const nullableId = (value: unknown) => value === null || text(value, 64);
const nullableRevision = (value: unknown) => value === null || positive(value);
function fields(value: Record<string, unknown>, required: string[], optional: string[] = []) {
  return (
    required.every((key) => Object.hasOwn(value, key)) &&
    Object.keys(value).every((key) => required.includes(key) || optional.includes(key))
  );
}
function valid(value: unknown): value is SavedIndexWrite {
  if (
    !object(value) ||
    !fields(value, ['subject', 'tenantId', 'workspaceId', 'domain', 'createdAt', 'write']) ||
    !text(value['subject'], 4096) ||
    !text(value['tenantId'], 64) ||
    !text(value['workspaceId'], 64) ||
    !['documents', 'structured'].includes(String(value['domain'])) ||
    !Number.isSafeInteger(value['createdAt']) ||
    Number(value['createdAt']) < 0
  )
    return false;
  const write = value['write'];
  if (!object(write) || !fields(write, ['operation', 'input', 'targetId', 'key'])) return false;
  const input = write['input'];
  if (!object(input)) return false;
  if (write['operation'] === 'create')
    return (
      write['targetId'] === null &&
      text(write['key'], 255) &&
      /^[!-~]+$/.test(write['key']) &&
      fields(
        input,
        [
          'workspace_id',
          'domain',
          'provider_id',
          'model_id',
          'expected_active_id',
          'expected_connection_revision',
        ],
        ['batch_size', 'expected_dimensions'],
      ) &&
      input['workspace_id'] === value['workspaceId'] &&
      input['domain'] === value['domain'] &&
      text(input['provider_id'], 64) &&
      text(input['model_id'], 255) &&
      nullableId(input['expected_active_id']) &&
      nullableRevision(input['expected_connection_revision']) &&
      (input['batch_size'] === undefined || positive(input['batch_size'], 64)) &&
      (input['expected_dimensions'] == null ||
        (positive(input['expected_dimensions'], 4096) &&
          Number(input['expected_dimensions']) >= 64))
    );
  if (!text(write['targetId'], 64) || !positive(input['expected_revision'])) return false;
  if (write['operation'] === 'resume')
    return (
      text(write['key'], 255) &&
      /^[!-~]+$/.test(write['key']) &&
      fields(input, ['expected_revision'])
    );
  if (write['key'] !== null) return false;
  if (write['operation'] === 'cancel') return fields(input, ['expected_revision']);
  return (
    write['operation'] === 'activate' &&
    fields(
      input,
      ['expected_revision', 'expected_active_id', 'expected_connection_revision'],
      ['recovery'],
    ) &&
    nullableId(input['expected_active_id']) &&
    nullableRevision(input['expected_connection_revision']) &&
    (input['recovery'] == null ||
      ['finish', 'restore_previous'].includes(String(input['recovery'])))
  );
}
function same(a: Scope, b: Scope) {
  return (
    a.subject === b.subject &&
    a.tenantId === b.tenantId &&
    a.workspaceId === b.workspaceId &&
    a.domain === b.domain
  );
}
export class IndexActionJournal {
  constructor(private readonly storage: Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>) {}
  private read(): SavedIndexWrite[] {
    const raw = this.storage.getItem(INDEX_JOURNAL_KEY);
    if (raw === null) return [];
    if (new TextEncoder().encode(raw).length > 16384)
      throw new Error('Index action journal exceeds its bound');
    const value: unknown = JSON.parse(raw);
    if (!Array.isArray(value) || value.length > 8 || !value.every(valid))
      throw new Error('Index action journal is unavailable');
    return value;
  }
  get(scope: Scope) {
    const rows = this.read().filter((row) => same(row, scope));
    if (rows.length > 1) throw new Error('Index action journal is ambiguous');
    return rows[0] ?? null;
  }
  put(value: SavedIndexWrite) {
    if (!valid(value)) throw new Error('Index action request is invalid');
    const rows = this.read(),
      existing = rows.find((row) => same(row, value));
    if (existing && JSON.stringify(existing) !== JSON.stringify(value))
      throw new Error('An index action is unresolved');
    const next = JSON.stringify(existing ? rows : [...rows, value]);
    if ((!existing && rows.length >= 8) || new TextEncoder().encode(next).length > 16384)
      throw new Error('Index action journal is full');
    this.storage.setItem(INDEX_JOURNAL_KEY, next);
  }
  clear(value: SavedIndexWrite) {
    const rows = this.read(),
      next = rows.filter(
        (row) => !same(row, value) || JSON.stringify(row) !== JSON.stringify(value),
      );
    if (next.length === rows.length) return;
    if (next.length) this.storage.setItem(INDEX_JOURNAL_KEY, JSON.stringify(next));
    else this.storage.removeItem(INDEX_JOURNAL_KEY);
  }
  replaceAfterReview(previous: SavedIndexWrite, next: SavedIndexWrite) {
    if (
      !valid(next) ||
      !same(previous, next) ||
      previous.write.operation !== 'activate' ||
      next.write.operation !== 'activate' ||
      previous.write.targetId !== next.write.targetId ||
      !next.write.input.recovery ||
      next.write.input.expected_revision <= previous.write.input.expected_revision
    )
      throw new Error('Review a current recovery action');
    const rows = this.read(),
      index = rows.findIndex(
        (row) => same(row, previous) && JSON.stringify(row) === JSON.stringify(previous),
      );
    if (index < 0) throw new Error('The saved action changed');
    rows[index] = next;
    const value = JSON.stringify(rows);
    if (new TextEncoder().encode(value).length > 16384)
      throw new Error('Index action journal is full');
    this.storage.setItem(INDEX_JOURNAL_KEY, value);
  }
}
