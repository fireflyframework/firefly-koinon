// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { TestBed } from '@angular/core/testing';
import {
  KoinonClient,
  type KoinonTransport,
  type RequestOptions,
} from '@fireflyframework/koinon-sdk';
import { KoinonFacade, provideKoinonClient } from '@fireflyframework/koinon-angular';
import { KoinonAuditPanel } from '../../../settings/src/audit-panel';
describe('Audit activity controls', () => {
  it('requests real pages and actor filters while preserving raw time in details', async () => {
    const calls: RequestOptions[] = [];
    const transport: KoinonTransport = {
      request: async <T>(_method: unknown, _path: string, options?: RequestOptions) => {
        calls.push(options ?? {});
        return {
          items: [
            {
              id: 'event',
              subject: 'issuer|person',
              action: 'membership.created',
              resource_id: 'resource',
              details: { role: 'editor' },
              created_at: '2026-10-27T15:30:00Z',
            },
          ],
          actors: {
            'issuer|person': { subject: 'issuer|person', display_name: 'Research colleague' },
          },
          total: 31,
          page: options?.query?.['page'] ?? 1,
          page_size: 25,
          pages: 2,
        } as T;
      },
      stream: () => {
        throw new Error('Unexpected stream');
      },
    };
    TestBed.configureTestingModule({
      imports: [KoinonAuditPanel],
      providers: [KoinonFacade, ...provideKoinonClient(new KoinonClient({ transport }), transport)],
    });
    const facade = TestBed.inject(KoinonFacade);
    facade.tenantId.set('north');
    const fixture = TestBed.createComponent(KoinonAuditPanel);
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();
    const element: HTMLElement = fixture.nativeElement;
    expect(element.querySelectorAll('form form').length).toBe(0);
    expect(element.textContent).toContain('Research colleague');
    const personButton = element.querySelector<HTMLButtonElement>('button.person');
    expect(personButton).not.toBeNull();
    expect(personButton?.textContent ?? '').not.toContain('issuer|person');
    expect(element.textContent).not.toContain('2026-10-27T15:30:00Z');
    const next = element.querySelector<HTMLButtonElement>(
      'button[aria-label="Next audit activity page"]',
    );
    expect(next).not.toBeNull();
    next?.click();
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();
    expect(calls.at(-1)?.query?.['page']).toBe(2);
    element.querySelector<HTMLButtonElement>('button.person')?.click();
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();
    expect(calls.at(-1)?.query?.['subject']).toBe('issuer|person');
    expect(calls.at(-1)?.query?.['page']).toBe(1);
    const selectedPage = calls.at(-1)?.query?.['page'];
    element.querySelector<HTMLButtonElement>('button.event-open')?.click();
    fixture.detectChanges();
    expect(element.querySelector('dialog[open]')).not.toBeNull();
    expect(element.textContent).toContain('2026-10-27T15:30:00Z');
    fixture.componentInstance.closeDetails();
    fixture.detectChanges();
    expect(calls.at(-1)?.query?.['page']).toBe(selectedPage);
    fixture.componentInstance.query = 'unapplied draft';
    fixture.componentInstance.load(2);
    await fixture.whenStable();
    fixture.detectChanges();
    expect(calls.at(-1)?.query?.['q'] ?? '').toBe('');
    expect(fixture.componentInstance.draftChanged()).toBe(true);
    fixture.componentInstance.from = '2026-10-28';
    fixture.componentInstance.through = '2026-10-01';
    const before = calls.length;
    fixture.componentInstance.apply();
    fixture.detectChanges();
    expect(calls.length).toBe(before);
    expect(element.textContent).toContain('Choose an end date on or after the start date.');
  });
});
