// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import type { AuditFilter } from '@fireflyframework/koinon-sdk';
export interface AuditDraft {
  q: string;
  action: string;
  from: string;
  through: string;
  sort: string;
  subject: string;
  personName: string;
}
export interface AuditChip {
  id: 'q' | 'action' | 'dates' | 'subject' | 'sort';
  label: string;
  value: string;
}
export function emptyAuditDraft(): AuditDraft {
  return { q: '', action: '', from: '', through: '', sort: 'newest', subject: '', personName: '' };
}
export function auditDirty(draft: AuditDraft, applied: AuditDraft): boolean {
  return (
    JSON.stringify({ ...draft, q: draft.q.trim() }) !==
    JSON.stringify({ ...applied, q: applied.q.trim() })
  );
}
export function auditRequest(applied: AuditDraft, page = 1, pageSize = 25): AuditFilter {
  if (applied.from && applied.through && applied.from > applied.through)
    throw new RangeError('Choose an end date on or after the start date.');
  return {
    q: applied.q.trim(),
    action: applied.action,
    subject: applied.subject,
    from_date: applied.from,
    through_date: applied.through,
    page,
    page_size: pageSize,
    sort: applied.sort === 'action' ? 'action' : 'created_at',
    order: applied.sort === 'newest' ? 'desc' : 'asc',
  };
}
export function auditChips(applied: AuditDraft): AuditChip[] {
  const chips: AuditChip[] = [];
  if (applied.q.trim()) chips.push({ id: 'q', label: 'Search', value: applied.q.trim() });
  if (applied.action) chips.push({ id: 'action', label: 'Action', value: applied.action });
  if (applied.from || applied.through)
    chips.push({
      id: 'dates',
      label: 'Date range',
      value: [applied.from || '…', applied.through || '…'].join(' – '),
    });
  if (applied.subject) chips.push({ id: 'subject', label: 'Person', value: applied.personName });
  if (applied.sort !== 'newest')
    chips.push({
      id: 'sort',
      label: 'Sort by',
      value: applied.sort === 'oldest' ? 'Oldest first' : 'Action',
    });
  return chips;
}
