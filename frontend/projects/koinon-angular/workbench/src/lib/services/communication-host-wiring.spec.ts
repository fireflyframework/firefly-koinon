// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import {
  KoinonFacade,
  KoinonClientContext,
  KOINON_TRANSPORT,
} from '@fireflyframework/koinon-angular';
import { KoinonError } from '@fireflyframework/koinon-sdk';
import { KoinonNotificationCenter } from '../../../../communications/inbox/notification-center';
import { KoinonEmailInvitationAcceptance } from '../../../../communications/invitations/email-acceptance';
const uuid = '4d2d21dd-bd63-44a0-9afb-205b38209bf4';
function connect(request: (method: string, path: string) => Promise<unknown>) {
  const facade = {
    context: signal({ subject: 'alice', tenants: [], workspaces: [], memberships: [] }),
    tenantId: signal(''),
    authRequired: signal(false),
  };
  TestBed.configureTestingModule({
    providers: [
      { provide: KoinonFacade, useValue: facade },
      {
        provide: KoinonClientContext,
        useValue: { revision: signal(0), getTransport: () => ({ request }) },
      },
      { provide: KOINON_TRANSPORT, useValue: { request } },
    ],
  });
  return facade;
}
it('loads the subject-owned inbox without organization membership and marks a notice through its real API route', async () => {
  const calls: string[] = [];
  connect(async (method, path) => {
    calls.push(method + ' ' + path);
    return method === 'GET'
      ? {
          items: [
            {
              id: 'n',
              kind: 'access_removed',
              title: 'Access removed',
              body: 'Your role changed.',
              created_at: '2026-10-31T00:00:00Z',
              read_at: null,
              tenant_id: 'former',
              organization_name: 'Former team',
              target: { kind: 'none', id: null },
            },
          ],
          page: 1,
          page_size: 25,
          pages: 1,
          total: 1,
        }
      : { id: 'n', read_at: '2026-10-31T01:00:00Z' };
  });
  const fixture = TestBed.createComponent(KoinonNotificationCenter);
  fixture.detectChanges();
  await fixture.whenStable();
  await fixture.componentInstance.markRead('n');
  fixture.detectChanges();
  expect(calls).toContain('GET /notifications');
  expect(calls).toContain('POST /notifications/n/read');
  expect(fixture.componentInstance.page()?.items[0]?.read_at).toBe('2026-10-31T01:00:00Z');
});
it('never renders invitation details when the current recipient binding is denied', async () => {
  connect(async () => {
    throw new KoinonError(403, 'INVITATION_RECIPIENT_MISMATCH', 'private error');
  });
  const fixture = TestBed.createComponent(KoinonEmailInvitationAcceptance);
  fixture.componentRef.setInput('invitationId', uuid);
  fixture.detectChanges();
  await fixture.whenStable();
  fixture.detectChanges();
  expect(fixture.componentInstance.review()).toBeNull();
  expect(fixture.componentInstance.problem()).toBe('wrong_account');
  expect(fixture.nativeElement.textContent).not.toContain('private error');
  expect(fixture.nativeElement.textContent).toContain('current account');
});
it('accepts the bound invitation once and cannot replay it after terminal success', async () => {
  let accepts = 0;
  connect(async (method) => {
    if (method === 'POST') {
      accepts++;
      return { id: 'member', tenant_id: 'org', workspace_id: null };
    }
    return {
      id: uuid,
      tenant_id: 'org',
      organization_name: 'Team',
      workspace_id: null,
      workspace_name: null,
      role: 'viewer',
      expires_at: '2026-11-01T00:00:00Z',
      status: 'pending',
      can_accept: true,
      can_decline: true,
      binding: 'directory_identity',
    };
  });
  const fixture = TestBed.createComponent(KoinonEmailInvitationAcceptance);
  fixture.componentRef.setInput('invitationId', uuid);
  fixture.detectChanges();
  await fixture.whenStable();
  await fixture.componentInstance.accept();
  await fixture.componentInstance.accept();
  expect(accepts).toBe(1);
  expect(fixture.componentInstance.review()?.status).toBe('accepted');
});
