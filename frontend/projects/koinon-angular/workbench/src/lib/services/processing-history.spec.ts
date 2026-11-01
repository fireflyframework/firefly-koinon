// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { TestBed } from '@angular/core/testing';
import { signal } from '@angular/core';
import { describe, expect, it, vi } from 'vitest';
import { KoinonFacade, KoinonClientContext } from '@fireflyframework/koinon-angular';
import type { KoinonTransport, RequestOptions } from '@fireflyframework/koinon-sdk';
import { KoinonProcessingHistory } from '../../../../activity/processing-history';
function setup() {
  const request = vi.fn(async (_method: string, _path: string, options: RequestOptions) => ({
    observed_at: '2026-11-01T00:00:00Z',
    next_page: options.body && (options.body as { page: number }).page === 1 ? 2 : null,
    items: [
      {
        id: 'attempt',
        resource_id: 'document',
        operation: 'document.replace',
        state: 'failed',
        updated_at: '2026-11-01T00:00:00Z',
        availability: {
          read: { state: 'ready' },
          search: { state: 'pending' },
          revision: { source_version_id: 'serving-old' },
        },
      },
    ],
  }));
  const transport = signal<KoinonTransport | null>({ request } as unknown as KoinonTransport);
  const revision = signal(0);
  const context = signal({ subject: 'actor-a' });
  const facade = {
    context,
    tenantId: signal('tenant'),
    workspaceId: signal('space'),
    tenantPermissions: () => new Set(['jobs:manage']),
    entries: () => [{ id: 'document', name: 'Controlled document' }],
  };
  TestBed.configureTestingModule({
    providers: [
      { provide: KoinonFacade, useValue: facade },
      { provide: KoinonClientContext, useValue: { revision, getTransport: () => transport() } },
    ],
  });
  const fixture = TestBed.createComponent(KoinonProcessingHistory);
  fixture.detectChanges();
  return { fixture, request, transport, revision, context };
}
describe('current administrator processing observations', () => {
  it('uses bounded scoped paging and displays serving availability separately from failed attempts', async () => {
    const { fixture, request } = setup();
    await vi.waitFor(() => {
      fixture.detectChanges();
      expect(fixture.nativeElement.textContent).toContain('Controlled document');
    });
    expect(fixture.nativeElement.textContent).toContain('Needs attention');
    expect(fixture.nativeElement.textContent).toContain(
      'Text remains available from the observed version',
    );
    expect(request.mock.calls[0]![2].body).toEqual({
      page: 1,
      page_size: 25,
      workspace_id: 'space',
    });
    await fixture.componentInstance.load(2);
    expect(request.mock.calls[1]![2].body).toEqual({
      page: 2,
      page_size: 25,
      workspace_id: 'space',
    });
    fixture.destroy();
  });
  it('removes old-actor observations immediately when the matching transport is missing', async () => {
    const { fixture, request, transport, revision, context } = setup();
    await vi.waitFor(() => expect(fixture.componentInstance.current()?.items.length).toBe(1));
    context.set({ subject: 'actor-b' });
    transport.set(null);
    revision.update((x) => x + 1);
    expect(fixture.componentInstance.current()).toBeNull();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).not.toContain('Controlled document');
    expect(request).toHaveBeenCalledOnce();
    fixture.destroy();
  });
});
