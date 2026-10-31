// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { TestBed } from '@angular/core/testing';
import { signal } from '@angular/core';
import {
  KoinonClient,
  type KoinonTransport,
  type HttpMethod,
  type RequestOptions,
} from '@fireflyframework/koinon-sdk';
import { KoinonClientContext, KoinonFacade } from '@fireflyframework/koinon-angular';
import { KoinonExportDialog } from '../../../../chat/page/src/artifacts/export-dialog';
import { KoinonShareReview } from '../../../../chat/page/src/artifacts/share-review';
import { KoinonSourceDrawer } from '../../../../chat/page/src/artifacts/source-drawer';
const revision = 'a'.repeat(64);
const reviewed = {
  id: 'review',
  revision,
  kind: 'conversation',
  format: 'markdown',
  title: 'Reviewed notes',
  message_count: 1,
  source_count: 0,
  completeness: 'selected_messages',
  messages: [
    { id: 'm', role: 'user', text: 'Exact selected notes', status: 'completed', revision },
  ],
  sources: [],
  source_manifest_complete: true,
  expires_at: '2099-01-01T00:00:00Z',
};
function providers(request: KoinonTransport['request']) {
  const transport: KoinonTransport = {
    request,
    stream: () => {
      throw Error('Unexpected stream');
    },
  };
  const facade = {
    context: signal({ subject: 'owner' }),
    tenantId: signal('north'),
    workspaceId: signal('w'),
    projectId: signal('p'),
    authRequired: signal(false),
    permissions: signal(
      new Set(['exports:read', 'exports:write', 'shares:read', 'shares:write', 'evidence:read']),
    ),
  };
  return {
    facade,
    values: [
      { provide: KoinonFacade, useValue: facade },
      {
        provide: KoinonClientContext,
        useValue: { revision: signal(0), get: () => new KoinonClient({ transport }) },
      },
    ],
  };
}
function button(element: HTMLElement, label: string) {
  const value = [...element.querySelectorAll<HTMLButtonElement>('button')].find(
    (row) => row.textContent?.trim() === label,
  );
  if (!value) throw Error('Button missing: ' + label);
  return value;
}
it('requires explicit review and create actions before offering a persisted export', async () => {
  const calls: { method: HttpMethod; path: string; options: RequestOptions }[] = [];
  const setup = providers(
    async <T>(method: HttpMethod, path: string, options: RequestOptions = {}) => {
      calls.push({ method, path, options });
      return (
        path.endsWith('/reviews')
          ? reviewed
          : {
              id: 'export',
              kind: 'conversation',
              format: 'markdown',
              title: 'Reviewed notes',
              status: 'ready',
              revision,
              completeness: 'selected_messages',
              created_at: '2026-10-27T00:00:00Z',
              expires_at: '2099-01-01T00:00:00Z',
            }
      ) as T;
    },
  );
  TestBed.configureTestingModule({ imports: [KoinonExportDialog], providers: setup.values });
  const fixture = TestBed.createComponent(KoinonExportDialog);
  fixture.componentRef.setInput('open', true);
  fixture.componentRef.setInput('selection', {
    kind: 'conversation',
    thread_id: 'thread',
    message_ids: ['m'],
  });
  fixture.detectChanges();
  await fixture.whenStable();
  expect(calls).toHaveLength(0);
  button(fixture.nativeElement, 'Review export').click();
  await fixture.whenStable();
  fixture.detectChanges();
  expect(calls).toHaveLength(1);
  expect(fixture.nativeElement.textContent).toContain('Exact selected notes');
  expect(fixture.componentInstance.state.exportRecord()).toBeNull();
  button(fixture.nativeElement, 'Create export').click();
  await fixture.whenStable();
  fixture.detectChanges();
  expect(calls[1].options.body).toEqual({ review_id: 'review', expected_revision: revision });
  expect(button(fixture.nativeElement, 'Download')).toBeTruthy();
  fixture.destroy();
});
it('keeps share review separate from creation and offers no implicit host link', async () => {
  const calls: string[] = [];
  const setup = providers(async <T>(_method: HttpMethod, path: string) => {
    calls.push(path);
    return (
      path.endsWith('/reviews')
        ? reviewed
        : {
            id: 'share',
            title: 'Reviewed notes',
            revision,
            status: 'active',
            recipient_policy: 'organization_current_acl',
            created_at: '2026-10-27T00:00:00Z',
            expires_at: '2099-01-01T00:00:00Z',
          }
    ) as T;
  });
  TestBed.configureTestingModule({ imports: [KoinonShareReview], providers: setup.values });
  const fixture = TestBed.createComponent(KoinonShareReview);
  fixture.componentRef.setInput('open', true);
  fixture.componentRef.setInput('selection', { thread_id: 'thread', message_ids: ['m'] });
  fixture.detectChanges();
  await fixture.whenStable();
  expect(calls).toHaveLength(0);
  button(fixture.nativeElement, 'Review shared content').click();
  await fixture.whenStable();
  fixture.detectChanges();
  expect(fixture.nativeElement.textContent).toContain('Exact selected notes');
  expect(calls).toHaveLength(1);
  button(fixture.nativeElement, 'Create share').click();
  await fixture.whenStable();
  fixture.detectChanges();
  expect(fixture.componentInstance.link()).toBe('');
  expect(fixture.nativeElement.textContent).toContain('No sharing link is configured.');
  fixture.destroy();
});
it('requires a fresh explicit choice before sharing an answer that used personal memory', async () => {
  const bodies: unknown[] = [];
  const setup = providers(async <T>(_method: HttpMethod, path: string, options?: RequestOptions) => {
    if (path.endsWith('/reviews')) return { ...reviewed, remembered_context_present: true } as T;
    bodies.push(options?.body);
    return { id: 'share', title: 'Reviewed notes', revision, status: 'active',
      created_at: '2026-10-31T00:00:00Z', expires_at: '2099-01-01T00:00:00Z' } as T;
  });
  TestBed.configureTestingModule({ imports: [KoinonShareReview], providers: setup.values });
  const fixture = TestBed.createComponent(KoinonShareReview);
  fixture.componentRef.setInput('open', true);
  fixture.componentRef.setInput('selection', { thread_id: 'thread', message_ids: ['m'] });
  fixture.detectChanges();
  button(fixture.nativeElement, 'Review shared content').click();
  await fixture.whenStable(); fixture.detectChanges();
  expect(button(fixture.nativeElement, 'Create share').disabled).toBe(true);
  expect(bodies).toHaveLength(0);
  const consent = fixture.nativeElement.querySelector('input[name=rememberedContextConsent]') as HTMLInputElement;
  expect(consent).not.toBeNull();
  expect(consent.checked).toBe(false);
  consent.click(); await fixture.whenStable(); fixture.detectChanges();
  expect(button(fixture.nativeElement, 'Create share').disabled).toBe(false);
  button(fixture.nativeElement, 'Review shared content').click();
  await fixture.whenStable(); fixture.detectChanges();
  expect((fixture.nativeElement.querySelector('input[name=rememberedContextConsent]') as HTMLInputElement).checked).toBe(false);
  expect(button(fixture.nativeElement, 'Create share').disabled).toBe(true);
  (fixture.nativeElement.querySelector('input[name=rememberedContextConsent]') as HTMLInputElement).click();
  await fixture.whenStable(); fixture.detectChanges();
  button(fixture.nativeElement, 'Create share').click();
  await fixture.whenStable(); fixture.detectChanges();
  expect(bodies).toEqual([{ review_id: 'review', expected_revision: revision,
    expires_in_hours: 24, recipient_policy: 'organization_current_acl', include_remembered_context: true }]);
  fixture.destroy();
});
it('clears a supplied source manifest when the authorized context changes', async () => {
  const setup = providers(async <T>() => ({}) as T);
  TestBed.configureTestingModule({ imports: [KoinonSourceDrawer], providers: setup.values });
  const fixture = TestBed.createComponent(KoinonSourceDrawer);
  fixture.componentRef.setInput('open', true);
  fixture.componentRef.setInput('manifest', {
    revision,
    complete: true,
    sources: [
      {
        id: 'source',
        asset_id: 'asset',
        title: 'Authorized report',
        kind: 'document',
        availability: 'available',
        quote: '<script>text only</script>',
      },
    ],
    omissions: [],
  });
  fixture.detectChanges();
  await fixture.whenStable();
  expect(fixture.nativeElement.textContent).toContain('Authorized report');
  expect(fixture.nativeElement.querySelector('script')).toBeNull();
  let closed = 0;
  fixture.componentInstance.closed.subscribe(() => closed++);
  setup.facade.tenantId.set('south');
  fixture.detectChanges();
  await fixture.whenStable();
  expect(fixture.nativeElement.textContent).not.toContain('Authorized report');
  expect(closed).toBeGreaterThan(0);
  fixture.destroy();
});
it('preserves the created share when the host supplies its management URL later', async () => {
  const setup = providers(async <T>() => ({}) as T);
  TestBed.configureTestingModule({ imports: [KoinonShareReview], providers: setup.values });
  const fixture = TestBed.createComponent(KoinonShareReview);
  fixture.componentRef.setInput('open', true);
  fixture.detectChanges();
  await fixture.whenStable();
  fixture.componentInstance.state.shareRecord.set({
    id: 'share',
    title: 'Reviewed notes',
    revision,
    status: 'active',
    recipient_policy: 'organization_current_acl',
    created_at: '2026-10-27T00:00:00Z',
    expires_at: '2099-01-01T00:00:00Z',
  });
  fixture.componentRef.setInput('managementBaseUrl', 'https://knowledge.example.test/app/');
  fixture.detectChanges();
  await fixture.whenStable();
  expect(fixture.componentInstance.state.shareRecord()?.id).toBe('share');
  expect(fixture.componentInstance.link()).toBe(
    'https://knowledge.example.test/app/#share=share&tenant=north',
  );
  fixture.destroy();
});
