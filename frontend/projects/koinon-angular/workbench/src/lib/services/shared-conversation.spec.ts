// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { TestBed } from '@angular/core/testing';
import { signal } from '@angular/core';
import {
  KoinonClient,
  KoinonError,
  type KoinonTransport,
  type HttpMethod,
} from '@fireflyframework/koinon-sdk';
import { KoinonClientContext, KoinonFacade } from '@fireflyframework/koinon-angular';
import { KoinonSharedConversation } from '../../../../chat/page/src/artifacts/shared-conversation';
const snapshot = {
  share: {
    id: 'share',
    title: 'Reviewed snapshot',
    revision: 'a'.repeat(64),
    status: 'active',
    created_at: '2026-10-27T00:00:00Z',
    expires_at: '2099-01-01T00:00:00Z',
  },
  messages: [
    {
      id: 'message',
      role: 'user',
      text: '<script>Saved message text only</script>',
      status: 'completed',
      revision: 'b'.repeat(64),
      created_at: '2026-10-27T10:00:00Z',
      presentation: { locale: 'en-US', time_zone: 'UTC', response_language: 'en' },
    },
  ],
  sources: [
    {
      id: 'citation',
      asset_id: 'asset',
      title: 'Verified report',
      kind: 'document',
      availability: 'available',
      used_revision: 'a'.repeat(64),
      current_revision: 'a'.repeat(64),
      quote: 'Verified source quotation',
      page: 2,
    },
  ],
  source_manifest_complete: true,
};
async function mount(request: KoinonTransport['request']) {
  const facade = {
    context: signal({ subject: 'recipient' }),
    tenantId: signal('north'),
    workspaceId: signal('w'),
    projectId: signal('p'),
    authRequired: signal(false),
    permissions: signal(new Set(['shares:read', 'evidence:read', 'catalog:read'])),
  };
  const transport: KoinonTransport = {
    request,
    stream: () => {
      throw Error('Unexpected stream');
    },
  };
  TestBed.configureTestingModule({
    imports: [KoinonSharedConversation],
    providers: [
      { provide: KoinonFacade, useValue: facade },
      {
        provide: KoinonClientContext,
        useValue: { revision: signal(0), get: () => new KoinonClient({ transport }) },
      },
    ],
  });
  const fixture = TestBed.createComponent(KoinonSharedConversation);
  fixture.componentRef.setInput('shareId', 'share');
  fixture.detectChanges();
  await fixture.whenStable();
  fixture.detectChanges();
  return { fixture, facade };
}
it('reads only the authenticated shared snapshot and renders saved text, times and source references', async () => {
  const paths: string[] = [];
  const { fixture } = await mount(async <T>(_method: HttpMethod, path: string) => {
    paths.push(path);
    return snapshot as T;
  });
  expect(paths).toEqual(['/tenants/north/shares/share']);
  expect(fixture.nativeElement.textContent).toContain('Saved message text only');
  expect(fixture.nativeElement.textContent).toContain('Conversation author');
  expect(fixture.nativeElement.querySelector('script')).toBeNull();
  expect(fixture.nativeElement.querySelector('time[datetime="2026-10-27T10:00:00Z"]')).toBeTruthy();
  const sources = [...fixture.nativeElement.querySelectorAll('button')].find(
    (button) => button.textContent?.trim() === 'View sources',
  ) as HTMLButtonElement;
  sources.click();
  fixture.detectChanges();
  await fixture.whenStable();
  expect(fixture.nativeElement.textContent).toContain('Verified report');
  expect(fixture.nativeElement.textContent).toContain('Verified source quotation');
  expect(paths).toHaveLength(1);
  fixture.destroy();
});
for (const [code, status, title] of [
  ['SHARE_EXPIRED', 410, 'This share has expired.'],
  ['SHARE_REVOKED', 410, 'This share was revoked.'],
  ['EVIDENCE_UNAVAILABLE', 403, 'Your account cannot open this share.'],
] as const)
  it('shows the authorized recipient state ' + code, async () => {
    const { fixture } = await mount(async () => {
      throw new KoinonError(status, code, 'Share unavailable');
    });
    expect(fixture.nativeElement.textContent).toContain(title);
    expect(fixture.nativeElement.textContent).not.toContain('Saved message text only');
    const close = fixture.nativeElement.querySelector(
      'button[aria-label="Close shared messages"]',
    ) as HTMLButtonElement;
    expect(close).toBeTruthy();
    fixture.destroy();
  });
it('clears snapshot text and invokes the explicit host action when context changes', async () => {
  const { fixture, facade } = await mount(async <T>() => snapshot as T);
  const closed = vi.fn();
  fixture.componentRef.setInput('actions', { closed, resourceRequested: vi.fn() });
  fixture.detectChanges();
  facade.tenantId.set('south');
  fixture.detectChanges();
  await fixture.whenStable();
  expect(fixture.nativeElement.textContent).not.toContain('Saved message text only');
  expect(closed).toHaveBeenCalledOnce();
  fixture.destroy();
});
