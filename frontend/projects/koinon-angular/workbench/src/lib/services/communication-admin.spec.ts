// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { TestBed } from '@angular/core/testing';
import { KoinonCommunicationsAdmin } from '../../../../communications/admin/communications-admin';
const record = {
  id: 'delivery-id',
  kind: 'invitation' as const,
  recipient_display: 'Alex Rivera',
  scope_name: 'Research operations',
  status: 'sent' as const,
  created_at: '2026-10-31T12:00:00Z',
  last_attempt_at: '2026-10-31T12:00:01Z',
  next_attempt_at: null,
  attempt_count: 1,
  failure_code: null,
  safe_explanation: null,
  can_retry: false,
};
describe('Communications administration', () => {
  it('explains missing sender or public address configuration without inventing readiness', () => {
    const fixture = TestBed.createComponent(KoinonCommunicationsAdmin);
    fixture.componentRef.setInput('readiness', {
      state: 'not_configured',
      provider_label: 'SMTP',
      sender_name: '',
      sender_address: '',
      reply_to: null,
      public_address_configured: false,
      issues: [
        {
          code: 'PUBLIC_ADDRESS_REQUIRED',
          explanation: 'Configure the public application address before sending invitations.',
        },
      ],
    });
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Needs configuration');
    expect(fixture.nativeElement.textContent).toContain(
      'Configure the public application address before sending invitations.',
    );
    expect(fixture.nativeElement.textContent).not.toContain('Email service ready');
  });
  it('keeps sent distinct from proven delivered and uses server pagination', () => {
    const fixture = TestBed.createComponent(KoinonCommunicationsAdmin);
    fixture.componentRef.setInput('deliveries', {
      items: [record],
      page: 2,
      page_size: 25,
      total: 91,
      pages: 4,
    });
    fixture.componentInstance.tab.set('history');
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Accepted by email service');
    expect(fixture.nativeElement.querySelector('tbody')?.textContent).not.toContain('Delivered');
    let filter: unknown;
    fixture.componentInstance.filterChanged.subscribe((value) => (filter = value));
    fixture.componentInstance.changePage(4);
    expect(filter).toEqual({ page: 4, page_size: 25, status: '', kind: '', from: '', to: '' });
  });
  it('does not emit a retry for a record without server permission', () => {
    const fixture = TestBed.createComponent(KoinonCommunicationsAdmin);
    const attempts: string[] = [];
    fixture.componentInstance.retryRequested.subscribe((value) => attempts.push(value));
    fixture.componentInstance.retry(record);
    expect(attempts).toEqual([]);
    fixture.componentInstance.retry({ ...record, status: 'failed', can_retry: true });
    expect(attempts).toEqual(['delivery-id']);
  });
  it('preserves mandatory policy channels and includes the expected server revision', () => {
    const fixture = TestBed.createComponent(KoinonCommunicationsAdmin);
    fixture.componentRef.setInput('policy', {
      revision: 9,
      digest_enabled: false,
      can_update: true,
      rules: [
        {
          kind: 'access_removed',
          label: 'Access removed',
          description: 'Mandatory access notices.',
          required: true,
          inbox: true,
          email: true,
          email_available: true,
        },
      ],
    });
    fixture.detectChanges();
    fixture.componentInstance.rules[0].email = false;
    let saved: unknown;
    fixture.componentInstance.policyChanged.subscribe((value) => (saved = value));
    fixture.componentInstance.savePolicy();
    expect(saved).toEqual({
      expected_revision: 9,
      admin_summaries: [],
      default_locale: null,
      sender_id: null,
      digest_enabled: false,
      allowed_digests: ['off'],
      default_digest: 'off',
      default_schedule: { local_time: '09:00', weekday: 0, day_of_month: 1 },
      rules: [{ kind: 'access_removed', inbox: true, email: true }],
    });
  });
});

it('cannot save a sender that is absent from operator-verified choices', () => {
  const fixture = TestBed.createComponent(KoinonCommunicationsAdmin);
  fixture.componentRef.setInput('policy', {
    revision: 4,
    sender_id: 'unavailable-sender',
    rules: [],
    digest_enabled: false,
    can_update: true,
  });
  fixture.componentRef.setInput('readiness', {
    state: 'ready',
    provider_label: 'SMTP',
    sender_name: 'Research',
    sender_address: 'notifications@example.test',
    reply_to: null,
    public_address_configured: true,
    sender_options: [],
    issues: [],
  });
  fixture.detectChanges();
  let saved = false;
  fixture.componentInstance.policyChanged.subscribe(() => (saved = true));
  fixture.componentInstance.savePolicy();
  expect(saved).toBe(false);
});

it('preserves all three administrator cadences and their independent local schedules', () => {
  const fixture = TestBed.createComponent(KoinonCommunicationsAdmin);
  fixture.componentRef.setInput('policy', {
    revision: 5,
    sender_id: null,
    rules: [],
    digest_enabled: false,
    can_update: true,
    allowed_digests: ['off'],
    default_digest: 'off',
    default_schedule: { local_time: '09:00', weekday: 0, day_of_month: 1 },
    default_locale: null,
    admin_summaries: [
      { cadence: 'weekly', schedule: { local_time: '08:30', weekday: 4, day_of_month: 1 } },
    ],
  });
  fixture.detectChanges();
  fixture.componentInstance.toggleAdminCadence('daily', true);
  fixture.componentInstance.toggleAdminCadence('monthly', true);
  fixture.componentInstance.updateAdminSchedule('monthly', {
    local_time: '10:00',
    weekday: 0,
    day_of_month: 31,
  });
  let saved: unknown;
  fixture.componentInstance.policyChanged.subscribe((value) => (saved = value));
  fixture.componentInstance.savePolicy();
  expect(saved).toMatchObject({
    admin_summaries: [
      { cadence: 'weekly', schedule: { local_time: '08:30', weekday: 4, day_of_month: 1 } },
      { cadence: 'daily', schedule: { local_time: '09:00', weekday: 0, day_of_month: 1 } },
      { cadence: 'monthly', schedule: { local_time: '10:00', weekday: 0, day_of_month: 31 } },
    ],
  });
});
