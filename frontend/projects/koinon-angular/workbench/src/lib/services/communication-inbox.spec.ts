// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { TestBed } from '@angular/core/testing';
import { KoinonNotificationInbox } from '../../../../communications/inbox/notification-inbox';
import { KoinonNotificationPreferences } from '../../../../communications/preferences/notification-preferences';
const notice = {
  id: 'notice-id',
  kind: 'access_removed' as const,
  title: 'Workspace role removed',
  body: 'Your Viewer role in Research operations was removed. Other roles may still grant access.',
  created_at: '2026-10-31T12:00:00Z',
  read_at: null,
  organization_name: 'Research operations',
  target: { kind: 'none' as const, id: '' },
};
describe('Own notification inbox', () => {
  it('shows an access removal without requiring current organization membership', () => {
    const fixture = TestBed.createComponent(KoinonNotificationInbox);
    fixture.componentRef.setInput('page', {
      items: [notice],
      page: 2,
      page_size: 25,
      total: 67,
      pages: 3,
    });
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Workspace role removed');
    expect(fixture.nativeElement.textContent).toContain('Other roles may still grant access.');
    expect(fixture.nativeElement.textContent).toContain('67');
  });
  it('emits server paging/filter requests rather than slicing local items', () => {
    const fixture = TestBed.createComponent(KoinonNotificationInbox);
    const requests: unknown[] = [];
    fixture.componentInstance.filterChanged.subscribe((value) => requests.push(value));
    fixture.componentInstance.changePage(3);
    fixture.componentInstance.read = 'unread';
    fixture.componentInstance.applyFilters();
    expect(requests).toEqual([
      { page: 3, page_size: 25, read: 'all', kind: '' },
      { page: 1, page_size: 25, read: 'unread', kind: '' },
    ]);
  });
  it('only emits safe typed internal targets and marks a specific notice read', () => {
    const fixture = TestBed.createComponent(KoinonNotificationInbox);
    const targets: unknown[] = [];
    const reads: string[] = [];
    fixture.componentInstance.targetRequested.subscribe((value) => targets.push(value));
    fixture.componentInstance.readRequested.subscribe((value) => reads.push(value));
    fixture.componentInstance.open(notice);
    fixture.componentInstance.open({
      ...notice,
      target: { kind: 'workspace', id: 'https://foreign.test' },
    });
    fixture.componentInstance.open({
      ...notice,
      target: { kind: 'workspace', id: 'workspace-id' },
    });
    fixture.componentInstance.markRead(notice);
    expect(targets).toEqual([{ kind: 'workspace', id: 'workspace-id' }]);
    expect(reads).toEqual(['notice-id']);
  });
});
describe('Personal notification preferences', () => {
  const preferences = {
    revision: 4,
    locale: 'en-US',
    time_zone: 'Europe/Madrid',
    digest: 'off' as const,
    allowed_digests: ['off', 'daily', 'weekly'] as ('off' | 'daily' | 'weekly')[],
    rules: [
      {
        kind: 'access_removed' as const,
        label: 'Access and security',
        description: 'Required access updates.',
        required: true,
        inbox: true,
        email: true,
        email_available: true,
      },
      {
        kind: 'digest' as const,
        label: 'Knowledge updates',
        description: 'A summary of optional updates.',
        required: false,
        inbox: true,
        email: false,
        email_available: true,
      },
    ],
  };
  it('locks required rules and preserves their channels even if form state is tampered with', async () => {
    const fixture = TestBed.createComponent(KoinonNotificationPreferences);
    fixture.componentRef.setInput('preferences', preferences);
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();
    const required = Array.from(
      fixture.nativeElement.querySelectorAll('.required-rule input'),
    ) as HTMLInputElement[];
    expect(required.length).toBe(2);
    expect(required.every((input) => input.disabled)).toBe(true);
    fixture.componentInstance.rules[0].inbox = false;
    let saved: unknown;
    fixture.componentInstance.saved.subscribe((value) => (saved = value));
    fixture.componentInstance.save();
    expect(saved).toEqual({
      expected_revision: 4,
      admin_summaries: null,
      notification_locale: null,
      digest: 'off',
      schedule: { local_time: '09:00', weekday: 0, day_of_month: 1 },
      rules: [
        { kind: 'access_removed', inbox: true, email: true },
        { kind: 'digest', inbox: true, email: false },
      ],
    });
  });
  it('resets its form to a new server revision and cannot invent an unsupported digest', () => {
    const fixture = TestBed.createComponent(KoinonNotificationPreferences);
    fixture.componentRef.setInput('preferences', preferences);
    fixture.detectChanges();
    fixture.componentInstance.digest = 'weekly';
    fixture.componentRef.setInput('preferences', {
      ...preferences,
      revision: 5,
      digest: 'daily',
      allowed_digests: ['off', 'daily'],
    });
    fixture.detectChanges();
    expect(fixture.componentInstance.digest).toBe('daily');
    fixture.componentInstance.digest = 'weekly';
    let saved = false;
    fixture.componentInstance.saved.subscribe(() => (saved = true));
    fixture.componentInstance.save();
    expect(saved).toBe(false);
  });
});

it('previews a monthly local schedule without saving and rejects invalid calendar input', () => {
  const fixture = TestBed.createComponent(KoinonNotificationPreferences);
  fixture.componentRef.setInput('preferences', {
    revision: 2,
    rules: [],
    digest: 'monthly',
    allowed_digests: ['off', 'weekly', 'monthly'],
    schedule: { local_time: '08:30', weekday: 0, day_of_month: 31 },
    locale: 'en-US',
    time_zone: 'Europe/Madrid',
  });
  fixture.detectChanges();
  const previews: unknown[] = [];
  const saves: unknown[] = [];
  fixture.componentInstance.previewRequested.subscribe((v) => previews.push(v));
  fixture.componentInstance.saved.subscribe((v) => saves.push(v));
  fixture.componentInstance.save(true);
  expect(previews).toEqual([
    {
      expected_revision: 2,
      admin_summaries: null,
      notification_locale: null,
      rules: [],
      digest: 'monthly',
      schedule: { local_time: '08:30', weekday: 0, day_of_month: 31 },
    },
  ]);
  expect(saves).toEqual([]);
  fixture.componentInstance.schedule.day_of_month = 32;
  fixture.componentInstance.save();
  expect(saves).toEqual([]);
});

it('inherits the organization or installation notification language instead of the implicit profile default', () => {
  const fixture = TestBed.createComponent(KoinonNotificationPreferences);
  fixture.componentRef.setInput('preferences', {
    revision: 1,
    rules: [],
    digest: 'off',
    allowed_digests: ['off'],
    locale: 'en-US',
    time_zone: 'Europe/Madrid',
    notification_locale: null,
    effective_locale: 'es-ES',
    locale_origin: 'installation',
  });
  fixture.detectChanges();
  expect(fixture.componentInstance.notificationLocale).toBe('');
  let saved: unknown;
  fixture.componentInstance.saved.subscribe((v) => (saved = v));
  fixture.componentInstance.save();
  expect(saved).toMatchObject({ notification_locale: null });
  fixture.componentInstance.notificationLocale = 'en-US';
  fixture.componentInstance.save();
  expect(saved).toMatchObject({ notification_locale: 'en-US' });
});

it('allows an administrator to opt out of optional organization summaries while preserving mandatory security notices', () => {
  const fixture = TestBed.createComponent(KoinonNotificationPreferences);
  fixture.componentRef.setInput('preferences', {
    revision: 7,
    rules: [
      {
        kind: 'security',
        label: 'Security',
        description: 'Required',
        required: true,
        inbox: true,
        email: true,
        email_available: true,
      },
    ],
    digest: 'off',
    allowed_digests: ['off'],
    locale: 'en-US',
    time_zone: 'UTC',
    admin_summaries: null,
    admin_summaries_available: true,
    admin_summaries_enabled: true,
  });
  fixture.detectChanges();
  fixture.componentInstance.adminSummaries = 'off';
  fixture.componentInstance.rules[0].email = false;
  let saved: unknown;
  fixture.componentInstance.saved.subscribe((value) => (saved = value));
  fixture.componentInstance.save();
  expect(saved).toMatchObject({
    admin_summaries: false,
    rules: [{ kind: 'security', inbox: true, email: true }],
  });
  fixture.componentRef.setInput('preferences', {
    ...fixture.componentInstance.preferences,
    admin_summaries: false,
    admin_summaries_available: false,
  });
  fixture.detectChanges();
  fixture.componentInstance.adminSummaries = 'on';
  fixture.componentInstance.save();
  expect(saved).toMatchObject({ admin_summaries: false });
});
it('requests an actual email preview without saving and hides it when the draft changes', () => {
  const fixture = TestBed.createComponent(KoinonNotificationPreferences);
  fixture.componentRef.setInput('preferences', {
    revision: 1,
    rules: [],
    digest: 'weekly',
    allowed_digests: ['off', 'weekly'],
    locale: 'en-US',
    time_zone: 'UTC',
  });
  fixture.detectChanges();
  const previews: unknown[] = [],
    saves: unknown[] = [];
  fixture.componentInstance.emailPreviewRequested.subscribe((value) => previews.push(value));
  fixture.componentInstance.saved.subscribe((value) => saves.push(value));
  fixture.componentInstance.previewEmail();
  expect(previews).toHaveLength(1);
  expect(previews[0]).toMatchObject({
    preferences: { digest: 'weekly' },
    window: { time_zone: 'UTC' },
  });
  expect(saves).toEqual([]);
  fixture.componentRef.setInput('emailPreview', {
    subject: 'A real rendered preview',
    sender_name: 'Team',
    heading: 'Summary',
    paragraphs: [],
    action_label: 'Open',
    footer: 'Footer',
  });
  fixture.detectChanges();
  expect(fixture.componentInstance.matchingEmailPreview()).not.toBeNull();
  fixture.componentInstance.notificationLocale = 'es-ES';
  expect(fixture.componentInstance.matchingEmailPreview()).toBeNull();
  fixture.componentInstance.emailWindow = null;
  fixture.componentInstance.previewEmail();
  expect(previews).toHaveLength(1);
});

it('only enables the optional email summary channel when the person explicitly chooses a cadence',()=>{const fixture=TestBed.createComponent(KoinonNotificationPreferences);fixture.componentRef.setInput('preferences',{revision:1,rules:[{kind:'digest',label:'Summary',description:'Optional',required:false,inbox:true,email:false,email_available:true}],digest:'weekly',allowed_digests:['off','weekly','monthly'],locale:'en-US',time_zone:'UTC'});fixture.detectChanges();expect(fixture.componentInstance.rules[0].email).toBe(false);fixture.componentInstance.changeDigest('monthly');expect(fixture.componentInstance.rules[0].email).toBe(true);fixture.componentInstance.rules[0].email=false;let saved:unknown;fixture.componentInstance.saved.subscribe(value=>saved=value);fixture.componentInstance.save();expect(saved).toMatchObject({digest:'monthly',rules:[{kind:'digest',inbox:true,email:false}]});});
