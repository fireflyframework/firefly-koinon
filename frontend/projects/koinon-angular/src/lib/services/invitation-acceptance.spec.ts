// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { TestBed } from '@angular/core/testing';
import {
  KoinonClient,
  KoinonError,
  type KoinonTransport,
  type RequestOptions,
  type Membership,
} from '@fireflyframework/koinon-sdk';
import { KoinonFacade, provideKoinonClient } from '@fireflyframework/koinon-angular';
import { KoinonInvitationAcceptance } from '../../../settings/src/invitation-acceptance';
const preview = {
  id: 'invite',
  tenant_id: 'north',
  tenant_name: 'Northwind Research',
  workspace_id: 'space',
  workspace_name: 'Evidence review',
  role: 'editor',
  expires_at: '2026-10-28T12:00:00Z',
};
const member: Membership = {
  id: 'newgrant',
  tenant_id: 'north',
  workspace_id: 'space',
  subject: 'https://issuer.test|recipient',
  role: 'editor',
  active: true,
};
function setup(request: KoinonTransport['request']) {
  const transport: KoinonTransport = {
    request,
    stream: () => {
      throw new Error('Unexpected stream');
    },
  };
  TestBed.configureTestingModule({
    imports: [KoinonInvitationAcceptance],
    providers: [KoinonFacade, ...provideKoinonClient(new KoinonClient({ transport }), transport)],
  });
  return TestBed.createComponent(KoinonInvitationAcceptance);
}
describe('explicit invitation acceptance', () => {
  it('previews friendly scope and requires a separate acceptance POST with typed output', async () => {
    const calls: [string, RequestOptions | undefined][] = [];
    const fixture = setup(async <T>(_method: unknown, path: string, options?: RequestOptions) => {
      calls.push([path, options]);
      return (path.endsWith('inspect') ? preview : member) as T;
    });
    const accepted: Membership[] = [];
    fixture.componentRef.setInput('token', 'private-token-for-acceptance');
    fixture.componentRef.setInput('actions', {
      accepted: (value: Membership) => accepted.push(value),
      dismissed: () => undefined,
    });
    fixture.detectChanges();
    await fixture.whenStable();
    expect(calls.map((call) => call[0])).toEqual(['/invitations/inspect']);
    expect(fixture.nativeElement.textContent).toContain('Northwind Research');
    expect(fixture.nativeElement.textContent).toContain('Evidence review');
    expect(fixture.nativeElement.textContent).not.toContain('private-token-for-acceptance');
    const button = Array.from(
      fixture.nativeElement.querySelectorAll('button') as NodeListOf<HTMLButtonElement>,
    ).find((button) => button.textContent?.includes('Accept invitation'));
    button!.click();
    await fixture.whenStable();
    expect(calls[1]).toEqual([
      '/invitations/redeem',
      { body: { token: 'private-token-for-acceptance' } },
    ]);
    expect(accepted).toEqual([member]);
  });
  it('marks expired sessions for native sign-in and clears loading for an empty token', async () => {
    const fixture = setup(async () => {
      throw new KoinonError(401, 'AUTH_REQUIRED', 'Sign in');
    });
    fixture.componentRef.setInput('token', 'private-token');
    fixture.detectChanges();
    await fixture.whenStable();
    expect(TestBed.inject(KoinonFacade).authRequired()).toBe(true);
    expect(fixture.nativeElement.textContent).toContain('Sign in to review this invitation.');
    fixture.componentRef.setInput('token', '');
    fixture.detectChanges();
    await fixture.whenStable();
    expect(fixture.componentInstance.pending()).toBe(false);
    expect(fixture.componentInstance.preview()).toBeNull();
  });
});

it('lets the recipient close an unavailable invitation and uses local dismissal wording', async () => {
  const fixture = setup(async () => {
    throw new KoinonError(403, 'INVITATION_UNAVAILABLE', 'Unavailable');
  });
  let dismissed = 0;
  fixture.componentRef.setInput('token', 'private-token');
  fixture.componentRef.setInput('actions', {
    accepted: () => undefined,
    dismissed: () => {
      dismissed++;
    },
  });
  fixture.detectChanges();
  await fixture.whenStable();
  const close = Array.from(
    fixture.nativeElement.querySelectorAll('button') as NodeListOf<HTMLButtonElement>,
  ).find((button) => button.textContent?.includes('Close invitation'));
  expect(close).toBeDefined();
  close!.click();
  expect(dismissed).toBe(1);
});
