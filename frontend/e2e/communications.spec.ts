// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
// Controlled HTTP fixtures qualify the compiled host and request contract, not email delivery.
import { test, expect, type Page } from '@playwright/test';
import { mkdir, readFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { mockService, context as baseContext } from './fixtures';
import { DEFAULT_BRANDING } from '../projects/koinon-angular/workbench/src/lib/services/branding-values';
import type { ActivitySummary, EmailPreview } from '@fireflyframework/koinon-sdk';
const browserErrors = new WeakMap<Page, string[]>();
const externalRequests = new WeakMap<Page, string[]>();
test.afterEach(async ({ page }) => {
  expect(browserErrors.get(page) ?? []).toEqual([]);
  expect(externalRequests.get(page) ?? []).toEqual([]);
});
const invitationId = '4d2d21dd-bd63-44a0-9afb-205b38209bf4';
const schedule = { local_time: '09:00', weekday: 0, day_of_month: 1 };
const rules = [
  { kind: 'security', required: true, inbox: true, email: true, email_available: true },
  { kind: 'digest', required: false, inbox: true, email: true, email_available: true },
];
const preferences = {
  revision: 3,
  admin_summaries: null,
  admin_summaries_available: true,
  admin_summaries_enabled: true,
  rules,
  digest: 'weekly',
  allowed_digests: ['off', 'daily', 'weekly', 'monthly'],
  locale: 'en-US',
  time_zone: 'Europe/Madrid',
  schedule,
  notification_locale: null,
  effective_locale: 'en-US',
  locale_origin: 'organization',
  next_run_at: '2026-11-02T08:00:00Z',
  next_run_local: '2026-11-02 09:00 CET',
};
async function fixture(page: Page, ready = true) {
  const errors: string[] = [];
  browserErrors.set(page, errors);
  const external: string[] = [];
  externalRequests.set(page, external);
  page.on('request', (request) => {
    const url = new URL(request.url());
    if (url.hostname !== '127.0.0.1' && !['data:', 'blob:'].includes(url.protocol))
      external.push(url.origin);
  });
  page.on('pageerror', (error) => errors.push(error.message));
  page.on('console', (message) => {
    if (message.type() === 'error' && message.text().startsWith('ERROR'))
      errors.push(message.text());
  });
  await page.route('**/*', (route) => {
    const url = new URL(route.request().url());
    return url.hostname === '127.0.0.1' || ['data:', 'blob:'].includes(url.protocol)
      ? route.continue()
      : route.abort();
  });
  await mockService(page);
  const writes: { path: string; method: string; body: unknown; csrf: string | undefined }[] = [];
  let preview: EmailPreview = {
    subject: 'Invitation to Knowledge operations',
    sender_name: 'Knowledge operations',
    recipient_display_name: 'Alex Rivera',
    recipient_email: 'alex@example.test',
    heading: 'Join Knowledge operations',
    paragraphs: ['You are invited to read shared knowledge.'],
    action_label: 'Review invitation',
    footer: 'Your organization manages access.',
    product_name: 'koinon',
    accent_color: '#855414',
    branding: DEFAULT_BRANDING,
    rendered_html: '',
    rendered_text: '',
    organization_name: 'Knowledge operations',
    workspace_name: 'Shared research',
    effective_locale: 'en-US',
    locale_origin: 'organization',
    powered_by: 'Powered by koinon',
    copyright: '© 2026 Firefly Software Foundation',
    usage_summary: null,
  };
  const actual = process.env['KOINON_EMAIL_PREVIEW_FIXTURE'];
  if (actual) {
    if (!actual.endsWith('.json')) throw Error('Use the generated email JSON fixture');
    preview = JSON.parse(await readFile(actual, 'utf8')) as EmailPreview;
    preview.rendered_html = await readFile(actual.replace(/\.json$/, '.preview.html'), 'utf8');
  }
  let usage: EmailPreview = preview;
  const usagePath = process.env['KOINON_USAGE_PREVIEW_FIXTURE'];
  if (usagePath) {
    usage = JSON.parse(await readFile(usagePath, 'utf8')) as EmailPreview;
    usage.rendered_html = await readFile(usagePath.replace(/\.json$/, '.preview.html'), 'utf8');
  }
  const observed = (value: number) => ({ value, status: 'observed' as const });
  const summary: ActivitySummary = usage.activity_summary ?? {
    tenant_id: 'tenant-one',
    audience: 'personal',
    window: {
      start_at: '2026-10-01T00:00:00Z',
      end_at: '2026-10-08T00:00:00Z',
      time_zone: 'Europe/Madrid',
    },
    coverage: { observed_since: null, complete_window: false },
    knowledge: { created: observed(8), updated: observed(15), consulted: observed(34) },
    top_projects: [
      {
        project_id: 'research',
        workspace_id: 'workspace-one',
        name: 'Shared research',
        knowledge: { created: observed(8), updated: observed(15), consulted: observed(34) },
      },
    ],
    daily_activity: [],
    mcp: {
      requests: observed(42),
      tool_calls: observed(38),
      succeeded: observed(36),
      failed: observed(2),
      rejected: observed(0),
      average_duration_ms: observed(320),
      p95_duration_ms: observed(650),
    },
    models: {
      input_tokens: { value: null, status: 'unavailable' },
      output_tokens: { value: null, status: 'unavailable' },
      embedding_tokens: { value: null, status: 'unavailable' },
      cost: { amount: null, status: 'unavailable' },
    },
  };
  await page.route('**/bff/api/v1/**', async (route) => {
    const request = route.request(),
      url = new URL(request.url()),
      path = url.pathname.replace('/bff/api/v1', ''),
      method = request.method();
    const json = (value: unknown, status = 200) =>
      route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(value) });
    if (path === '/context')
      return json({
        ...baseContext,
        tenants: baseContext.tenants.map((value) => ({
          ...value,
          permissions: [...value.permissions, 'activity:read'],
        })),
        memberships: [
          {
            id: 'admin',
            tenant_id: 'tenant-one',
            workspace_id: null,
            subject: baseContext.subject,
            role: 'admin',
            active: true,
          },
        ],
      });
    if (
      !path.includes('/communications/') &&
      !path.includes('/invitations/email') &&
      !path.startsWith('/notifications') &&
      !path.includes('/activity/')
    )
      return route.fallback();
    if (method !== 'GET')
      writes.push({
        path,
        method,
        body: request.postData() ? request.postDataJSON() : null,
        csrf: request.headers()['x-xsrf-token'],
      });
    if (path.endsWith('/capabilities'))
      return json({
        state: ready ? 'ready' : 'disabled',
        provider_label: 'Configured email service',
        sender_name: 'Knowledge operations',
        sender_address: 'notifications@example.test',
        reply_to: null,
        sender_options: [
          {
            id: 'default',
            display_name: 'Knowledge operations',
            address: 'notifications@example.test',
          },
        ],
        public_address_configured: true,
        public_url: 'https://knowledge.example',
        acceptance_base: '/auth/invitations/email',
        issues: [],
        effective_locale: 'en-US',
        locale_origin: 'organization',
      });
    if (path.endsWith('/recipient-providers'))
      return json({
        items: [{ id: 'directory-one', display_name: 'Organization directory' }],
        total: 1,
        page: 1,
        page_size: 20,
        pages: 1,
      });
    if (path.endsWith('/recipients'))
      return json({
        items: [
          {
            recipient_ref: 'opaque-scoped-recipient-reference',
            display_name: preview.recipient_display_name,
            email: preview.recipient_email,
            provider_label: 'Organization directory',
            delivery_address_status: 'verified_directory',
            eligibility: 'eligible',
            eligibility_reason: null,
          },
        ],
        next_cursor: null,
      });
    if (path.endsWith('/invitations/email/preview')) return json(preview);
    if (path.endsWith('/invitations/email'))
      return method === 'GET'
        ? json({ items: [], total: 0, page: 1, page_size: 25, pages: 0 })
        : json(
            {
              id: invitationId,
              tenant_id: 'tenant-one',
              workspace_id: 'workspace-one',
              organization_name: 'Knowledge operations',
              workspace_name: 'Shared research',
              role: 'viewer',
              recipient_display_name: preview.recipient_display_name,
              recipient_email: preview.recipient_email,
              provider_label: 'Organization directory',
              created_at: '2026-10-31T12:00:00Z',
              expires_at: '2026-11-01T12:00:00Z',
              status: 'pending',
              accepted_at: null,
              declined_at: null,
              revoked_at: null,
              delivery: {
                id: 'delivery',
                status: 'queued',
                queued_at: '2026-10-31T12:00:00Z',
                last_attempt_at: null,
                next_attempt_at: null,
                next_resend_at: null,
                failure_code: null,
              },
              allowed_actions: ['revoke'],
            },
            201,
          );
    if (path.endsWith('/unread-count')) return json({ unread: 7 });
    if (path === '/notifications')
      return json({
        items: [
          {
            id: 'notice',
            kind: 'security',
            title: 'Access token revoked',
            body: 'A personal access token was revoked. No credential is included.',
            created_at: '2026-10-31T12:00:00Z',
            read_at: null,
            tenant_id: 'tenant-one',
            organization_name: 'Knowledge operations',
            target: { kind: 'none', id: null },
          },
        ],
        total: 1,
        page: 1,
        page_size: 25,
        pages: 1,
      });
    if (path.endsWith('/preferences/email-preview')) return json(usage);
    if (path.includes('/activity/'))
      return json({
        ...summary,
        tenant_id: 'tenant-one',
        audience: path.endsWith('/administration') ? 'organization_administrators' : 'personal',
        window: request.postDataJSON(),
      });
    if (path.endsWith('/preferences/preview')) {
      const input = request.postDataJSON();
      return json({
        digest: input.digest,
        schedule: input.schedule,
        time_zone: 'Europe/Madrid',
        next_run_at: '2026-11-30T08:30:00Z',
        next_run_local: '2026-11-30 09:30 CET',
        window_start: '2026-10-31T08:30:00Z',
        window_end: '2026-11-30T08:30:00Z',
        dst_policy: 'first_valid_minute_earlier_fold',
      });
    }
    if (path.endsWith('/preferences'))
      return json(
        method === 'PATCH'
          ? {
              ...preferences,
              effective_locale: usage.effective_locale,
              locale_origin: usage.locale_origin,
              ...request.postDataJSON(),
              revision: 4,
            }
          : {
              ...preferences,
              effective_locale: usage.effective_locale,
              locale_origin: usage.locale_origin,
            },
      );
    if (path.endsWith('/policy'))
      return json({
        revision: 4,
        sender_id: 'default',
        rules,
        digest_enabled: true,
        can_update: true,
        allowed_digests: ['off', 'weekly', 'monthly'],
        default_digest: 'weekly',
        default_schedule: schedule,
        default_locale: null,
        admin_summaries: [],
      });
    if (path.endsWith('/deliveries'))
      return json({ items: [], total: 0, page: 1, page_size: 25, pages: 0 });
    return json({ code: 'UNEXPECTED_FIXTURE_ROUTE' }, 404);
  });
  return { writes, preview };
}
async function capture(page: Page, name: string) {
  const directory = process.env['KOINON_COMMUNICATIONS_CAPTURE_DIR'];
  if (directory) {
    await mkdir(directory, { recursive: true });
    await page.screenshot({ path: resolve(directory, name + '.png') });
  }
}
for (const width of [1440, 390])
  test(`recipient-bound invitation uses the actual lazy host at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 });
    const state = await fixture(page);
    await page.goto('/');
    if (width < 700)
      await page.getByRole('button', { name: 'Open navigation', exact: true }).click();
    await page.getByRole('button', { name: 'Settings', exact: true }).click();
    if (width < 700)
      await page
        .getByRole('combobox', { name: 'Settings section', exact: true })
        .selectOption('access');
    else await page.getByRole('button', { name: 'Access', exact: true }).click();
    await page.getByRole('button', { name: 'Invite person', exact: true }).click();
    const wizard = page.locator('ffk-invitation-composer');
    await expect(wizard.getByRole('heading', { name: 'Choose a person' })).toBeVisible();
    await wizard.getByLabel('Search identity directory').fill('Alex');
    await wizard.getByRole('button', { name: 'Search', exact: true }).click();
    await wizard
      .getByRole('button', { name: new RegExp(state.preview.recipient_display_name) })
      .click();
    await wizard.getByRole('button', { name: 'Continue', exact: true }).click();
    await wizard.getByLabel('Access scope').selectOption('workspace-one');
    await capture(page, 'host-invitation-access-' + width);
    await wizard.getByRole('button', { name: 'Review invitation', exact: true }).click();
    await expect(page.locator('ffk-email-preview')).toBeVisible();
    await capture(page, 'host-invitation-preview-' + width);
    await wizard.getByRole('button', { name: 'Send invitation', exact: true }).click();
    await expect(wizard.getByRole('heading', { name: 'Invitation queued' })).toBeVisible();
    const sent = state.writes.filter((row) => row.path.endsWith('/invitations/email'));
    expect(sent).toHaveLength(1);
    expect(sent[0].body).toMatchObject({
      recipient_ref: 'opaque-scoped-recipient-reference',
      workspace_id: 'workspace-one',
      role: 'viewer',
    });
    expect(sent[0].csrf).toBe('synthetic-csrf+token');
    expect(JSON.stringify(sent[0].body)).not.toContain('token');
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
      true,
    );
  });
for (const width of [1440, 390])
  test(`account navigation previews monthly scheduling without saving at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 1000 });
    const state = await fixture(page);
    await page.goto('/account/notification-preferences');
    const form = page.locator('ffk-notification-preferences');
    await expect(form.getByRole('heading', { name: 'Notification preferences' })).toBeVisible();
    await form
      .getByRole('combobox', { name: 'Email summary', exact: true })
      .selectOption('monthly');
    await form.getByLabel('Local send time').fill('09:30');
    await form.getByLabel('Day of the month').fill('31');
    await form.getByRole('button', { name: 'Preview next summary' }).click();
    await expect(form.getByRole('status')).toContainText('9:30');
    await expect(form.getByRole('status').locator('time').first()).toHaveAttribute(
      'datetime',
      '2026-11-30T08:30:00Z',
    );
    expect(state.writes.some((row) => row.method === 'PATCH')).toBe(false);
    await capture(page, 'host-preferences-monthly-' + width);
    await form.getByRole('button', { name: 'Save preferences' }).click();
    expect(state.writes.filter((row) => row.method === 'PATCH')).toHaveLength(1);
  });
test('disabled email preserves in-app notifications and shows readiness instead of delivery success', async ({
  page,
}) => {
  await fixture(page, false);
  await page.goto('/account/notifications');
  await expect(page.getByRole('heading', { name: 'Your notifications' })).toBeVisible();
  await expect(page.getByText('Access token revoked', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  await page.getByRole('button', { name: 'Communications', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Communications', exact: true })).toBeVisible();
  await expect(
    page.locator('ffk-communications-admin').getByText('Disabled', { exact: true }),
  ).toBeVisible();
});

for (const width of [1440, 390])
  test(`past knowledge summary and actual rendered usage email at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1100 });
    const state = await fixture(page);
    await page.goto('/');
    if (width < 700)
      await page.getByRole('button', { name: 'Open navigation', exact: true }).click();
    await page.getByRole('button', { name: 'Activity', exact: true }).click();
    const activity = page.locator('ffk-activity-panel');
    await expect(activity.getByRole('heading', { name: 'Your knowledge activity' })).toBeVisible();
    await expect(activity.getByRole('heading', { name: 'Top projects' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Processing jobs' })).toBeVisible();
    await capture(page, 'host-knowledge-activity-' + width);
    await activity.getByLabel('Summary audience').selectOption('administrative');
    await activity.getByRole('button', { name: 'View summary' }).click();
    await expect(
      activity.getByRole('heading', { name: 'Organization knowledge activity' }),
    ).toBeVisible();
    expect(
      state.writes.filter((row) => row.path.endsWith('/activity/administration')),
    ).toHaveLength(1);
    await page.goto('/account/notification-preferences');
    const preferences = page.locator('ffk-notification-preferences');
    await preferences.getByLabel('Receive administrator summaries').selectOption('off');
    await preferences.getByRole('button', { name: 'Preview summary email', exact: true }).click();
    const email = preferences.locator('ffk-email-preview');
    await expect(email).toBeVisible();
    await email.scrollIntoViewIfNeeded();
    await capture(page, 'host-usage-email-' + width);
    if (process.env['KOINON_USAGE_PREVIEW_FIXTURE']) {
      const frame = email.frameLocator('iframe');
      await expect(frame.getByText('Powered by koinon', { exact: true })).toBeVisible();
      await expect(frame.locator('h1')).toHaveCSS('font-family', /Manrope|Inter/);
      await expect(frame.locator('a[href],area[href],meta[http-equiv=refresh]')).toHaveCount(0);
      if (await frame.locator('a').count()) await frame.locator('a').first().click();
      await expect(frame.getByText('Powered by koinon', { exact: true })).toBeVisible();
      await email.getByRole('button', { name: 'Plain text', exact: true }).click();
      await expect(email.locator('pre')).toContainText('Firefly Software Foundation');
      await capture(page, 'host-usage-text-' + width);
    } else {
      await expect(email).toContainText('Powered by koinon');
      await expect(email).toContainText('Firefly Software Foundation');
    }
    expect(state.writes.some((row) => row.method === 'PATCH')).toBe(false);
    expect(state.writes.find((row) => row.path.endsWith('/email-preview'))?.body).toMatchObject({
      tenant_id: 'tenant-one',
      preferences: { admin_summaries: false },
    });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
      true,
    );
  });
for (const width of [1440, 390])
  test(`administrator daily weekly and monthly schedules are independent at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 1100 });
    const state = await fixture(page);
    await page.goto('/');
    if (width < 700)
      await page.getByRole('button', { name: 'Open navigation', exact: true }).click();
    await page.getByRole('button', { name: 'Settings', exact: true }).click();
    if (width < 700)
      await page
        .getByRole('combobox', { name: 'Settings section', exact: true })
        .selectOption('communications');
    else await page.getByRole('button', { name: 'Communications', exact: true }).click();
    const admin = page.locator('ffk-communications-admin');
    await admin.getByRole('button', { name: 'Policies', exact: true }).click();
    const schedules = admin.locator('.administrator-summaries');
    await schedules.getByRole('checkbox', { name: 'Daily', exact: true }).check();
    await schedules.getByRole('checkbox', { name: 'Weekly', exact: true }).check();
    await schedules.getByRole('checkbox', { name: 'Monthly', exact: true }).check();
    await schedules.getByLabel('Local send time').nth(0).fill('08:00');
    await schedules.getByLabel('Local send time').nth(1).fill('09:00');
    await schedules.getByLabel('Local send time').nth(2).fill('10:00');
    await schedules.getByLabel('Day of the month').fill('31');
    await schedules.scrollIntoViewIfNeeded();
    await capture(page, 'host-administrator-cadences-' + width);
    await admin.getByRole('button', { name: 'Save policy', exact: true }).click();
    expect(state.writes.find((row) => row.path.endsWith('/policy'))?.body).toMatchObject({
      admin_summaries: [
        { cadence: 'daily', schedule: { local_time: '08:00' } },
        { cadence: 'weekly', schedule: { local_time: '09:00' } },
        { cadence: 'monthly', schedule: { local_time: '10:00', day_of_month: 31 } },
      ],
    });
  });
