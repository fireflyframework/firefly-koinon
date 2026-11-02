// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import type {
  DeliveryInspectionInput,
  WelcomeRecoveryInput,
} from '@fireflyframework/koinon-sdk/communications';
export type DeliveryWrite = {
  subject: string;
  tenantId: string;
  deliveryId: string;
  key: string;
} & (
  | { operation: 'inspect'; input: DeliveryInspectionInput }
  | { operation: 'welcome'; input: WelcomeRecoveryInput }
);
export const DELIVERY_JOURNAL_KEY = 'koinon:delivery-recovery-actions:v1';
const object = (v: unknown): v is Record<string, unknown> =>
  !!v && typeof v === 'object' && !Array.isArray(v);
const text = (v: unknown, max: number): v is string =>
  typeof v === 'string' &&
  v.length > 0 &&
  v.length <= max &&
  Array.from(v).every((c) => c.charCodeAt(0) >= 32 && c.charCodeAt(0) !== 127);
const integer = (v: unknown, min: number) => Number.isSafeInteger(v) && Number(v) >= min;
const fields = (v: Record<string, unknown>, names: string[]) =>
  Object.keys(v).length === names.length && names.every((n) => Object.hasOwn(v, n));
function valid(v: unknown): v is DeliveryWrite {
  if (
    !object(v) ||
    !fields(v, ['subject', 'tenantId', 'deliveryId', 'key', 'operation', 'input']) ||
    !text(v['subject'], 4096) ||
    !text(v['tenantId'], 64) ||
    !text(v['deliveryId'], 64) ||
    !text(v['key'], 255) ||
    !/^[!-~]+$/.test(v['key']) ||
    !object(v['input'])
  )
    return false;
  const input = v['input'];
  if (!integer(input['expected_generation'], 0)) return false;
  return v['operation'] === 'inspect'
    ? fields(input, ['expected_generation'])
    : v['operation'] === 'welcome' &&
        fields(input, [
          'expected_generation',
          'contact_id',
          'expected_contact_revision',
          'reason',
          'acknowledge_possible_duplicate',
        ]) &&
        text(input['contact_id'], 64) &&
        integer(input['expected_contact_revision'], 1) &&
        input['reason'] === 'recipient_reported_not_received' &&
        input['acknowledge_possible_duplicate'] === true;
}
export class DeliveryRecoveryJournal {
  constructor(private readonly storage: Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>) {}
  private read(): DeliveryWrite[] {
    const raw = this.storage.getItem(DELIVERY_JOURNAL_KEY);
    if (raw === null) return [];
    if (new TextEncoder().encode(raw).length > 16384)
      throw Error('Delivery request journal exceeds its bound');
    const rows: unknown = JSON.parse(raw);
    if (
      !Array.isArray(rows) ||
      rows.length > 8 ||
      !rows.every(valid) ||
      new Set(rows.map((r) => r.key)).size !== rows.length
    )
      throw Error('Invalid delivery request journal');
    return rows;
  }
  forDelivery(subject: string, tenantId: string, deliveryId: string) {
    return this.read().filter(
      (v) => v.subject === subject && v.tenantId === tenantId && v.deliveryId === deliveryId,
    );
  }
  put(value: DeliveryWrite) {
    if (!valid(value)) throw Error('Invalid delivery request');
    const rows = this.read(),
      old = rows.find((v) => v.key === value.key);
    if (old && JSON.stringify(old) !== JSON.stringify(value))
      throw Error('Delivery request key changed');
    if (!old) rows.push(value);
    const raw = JSON.stringify(rows);
    if (rows.length > 8 || new TextEncoder().encode(raw).length > 16384)
      throw Error('Delivery request journal is full');
    this.storage.setItem(DELIVERY_JOURNAL_KEY, raw);
  }
  clear(value: DeliveryWrite) {
    const rows = this.read(),
      next = rows.filter((v) => v.key !== value.key || JSON.stringify(v) !== JSON.stringify(value));
    if (next.length === rows.length) return;
    if (next.length) this.storage.setItem(DELIVERY_JOURNAL_KEY, JSON.stringify(next));
    else this.storage.removeItem(DELIVERY_JOURNAL_KEY);
  }
}
