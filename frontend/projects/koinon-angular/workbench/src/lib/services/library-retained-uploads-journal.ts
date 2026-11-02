// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import type { RetainedUploadRequest } from './library-retained-uploads-contract';
const KEY = 'koinon:retained-upload-actions:v1';
const FIELDS = [
  'subject',
  'tenantId',
  'batchId',
  'itemId',
  'operation',
  'expectedRevision',
  'key',
] as const;
const text = (value: unknown, max: number): value is string =>
  typeof value === 'string' &&
  value.length > 0 &&
  value.length <= max &&
  Array.from(value).every(
    (character) => character.charCodeAt(0) >= 32 && character.charCodeAt(0) !== 127,
  );
function valid(value: unknown): value is RetainedUploadRequest {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false;
  const row = value as Record<string, unknown>;
  if (
    Object.keys(row).length !== FIELDS.length ||
    !FIELDS.every((k) => Object.hasOwn(row, k)) ||
    !text(row['subject'], 4096) ||
    !text(row['tenantId'], 64) ||
    !text(row['batchId'], 64) ||
    !text(row['key'], 255) ||
    !/^[!-~]+$/.test(row['key']) ||
    !Number.isSafeInteger(row['expectedRevision']) ||
    Number(row['expectedRevision']) < 1 ||
    Number(row['expectedRevision']) > 2147483647
  )
    return false;
  return ['submit', 'cancel'].includes(String(row['operation']))
    ? row['itemId'] === null
    : [
        'recover_original',
        'reconcile',
        'retry_processing',
        'finalize_publication',
        'acknowledge_commit',
      ].includes(String(row['operation'])) && text(row['itemId'], 64);
}
const same = (a: RetainedUploadRequest, b: RetainedUploadRequest) =>
  FIELDS.every((field) => a[field] === b[field]);
export class RetainedUploadJournal {
  constructor(private readonly storage: Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>) {}
  private read(): RetainedUploadRequest[] {
    const raw = this.storage.getItem(KEY);
    if (raw === null) return [];
    if (new TextEncoder().encode(raw).length > 16384)
      throw Error('Retained upload action journal exceeds its bound');
    const rows: unknown = JSON.parse(raw);
    if (
      !Array.isArray(rows) ||
      rows.length > 8 ||
      !rows.every(valid) ||
      new Set(rows.map((row) => row.key)).size !== rows.length
    )
      throw Error('Retained upload action journal is invalid');
    return rows;
  }
  // A saved request is advisory; callers must authorize the exact batch on the server first.
  forBatch(subject: string, tenantId: string, batchId: string) {
    return this.read().filter(
      (row) => row.subject === subject && row.tenantId === tenantId && row.batchId === batchId,
    );
  }
  put(action: RetainedUploadRequest) {
    if (!valid(action)) throw Error('Retained upload request is invalid');
    const rows = this.read(),
      existing = rows.find((row) => row.key === action.key);
    if (existing && !same(existing, action)) throw Error('Saved upload action differs');
    if (!existing) rows.push(action);
    const raw = JSON.stringify(rows);
    if (rows.length > 8 || new TextEncoder().encode(raw).length > 16384)
      throw Error('Retained upload action journal is full');
    this.storage.setItem(KEY, raw);
  }
  clear(action: RetainedUploadRequest) {
    const rows = this.read(),
      next = rows.filter((row) => !same(row, action));
    if (rows.length === next.length) return;
    if (next.length) this.storage.setItem(KEY, JSON.stringify(next));
    else this.storage.removeItem(KEY);
  }
}
