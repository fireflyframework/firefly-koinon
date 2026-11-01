// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { TestBed } from '@angular/core/testing';
import { KoinonRecipientInvitation } from '../../../../communications/invitations/recipient-invitation';
const invitation = {
  id: 'invitation-uuid',
  organization_name: 'Research operations',
  workspace_name: 'Shared research',
  role_name: 'Viewer',
  role_description: 'Read shared knowledge.',
  expires_at: '2026-11-02T12:00:00Z',
  status: 'pending' as const,
  can_accept: true,
  can_decline: true,
};
it('requires an authenticated recipient review and prevents duplicate accept submissions', () => {
  const fixture = TestBed.createComponent(KoinonRecipientInvitation);
  const accepted: string[] = [];
  fixture.componentInstance.accepted.subscribe((id) => accepted.push(id));
  fixture.componentInstance.accept();
  expect(accepted).toEqual([]);
  fixture.componentRef.setInput('review', invitation);
  fixture.detectChanges();
  fixture.componentInstance.accept();
  fixture.componentInstance.accept();
  expect(accepted).toEqual(['invitation-uuid']);
});
it('cannot replay an accepted invitation or accept while the wrong account is signed in', () => {
  const fixture = TestBed.createComponent(KoinonRecipientInvitation);
  let accepted = false;
  fixture.componentInstance.accepted.subscribe(() => (accepted = true));
  fixture.componentRef.setInput('review', { ...invitation, status: 'accepted' });
  fixture.detectChanges();
  fixture.componentInstance.accept();
  expect(accepted).toBe(false);
  fixture.componentRef.setInput('review', invitation);
  fixture.componentRef.setInput('problem', 'wrong_account');
  fixture.detectChanges();
  fixture.componentInstance.accept();
  expect(accepted).toBe(false);
  expect(fixture.nativeElement.textContent).not.toContain('Research operations');
  expect(fixture.nativeElement.textContent).toContain('Switch account');
});
it('requires an explicit decline confirmation and sends the noncredential invitation id only', () => {
  const fixture = TestBed.createComponent(KoinonRecipientInvitation);
  fixture.componentRef.setInput('review', invitation);
  fixture.detectChanges();
  const declined: string[] = [];
  fixture.componentInstance.declined.subscribe((id) => declined.push(id));
  fixture.componentInstance.decline();
  expect(declined).toEqual([]);
  fixture.componentInstance.confirmDecline.set(true);
  fixture.componentInstance.decline();
  expect(declined).toEqual(['invitation-uuid']);
});
