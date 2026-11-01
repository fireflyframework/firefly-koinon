// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { TestBed, DeferBlockState } from '@angular/core/testing';
import { KoinonInvitationComposer } from '../../../../communications/invitations/invitation-composer';
const recipient = {
  recipient_ref: 'scoped-recipient-reference',
  display_name: 'Alex Rivera',
  email: 'alex@example.test',
  provider_label: 'Organization directory',
  delivery_address_status: 'verified_directory' as const,
  eligibility: 'eligible' as const,
  eligibility_reason: '',
};
function setup() {
  TestBed.configureTestingModule({ imports: [KoinonInvitationComposer] });
  const fixture = TestBed.createComponent(KoinonInvitationComposer);
  fixture.componentRef.setInput('contextKey', 'actor:organization:revision');
  fixture.componentRef.setInput('recipients', { items: [recipient], next_cursor: null });
  fixture.componentRef.setInput('roles', [
    { id: 'viewer', label: 'Viewer', description: 'Read shared knowledge.' },
  ]);
  fixture.componentRef.setInput('scopes', [{ id: 'workspace', name: 'Research operations' }]);
  fixture.detectChanges();
  return fixture;
}
describe('Recipient-bound invitation composer', () => {
  it('requires an eligible directory selection before choosing access', () => {
    const fixture = setup();
    const buttons = () =>
      Array.from(fixture.nativeElement.querySelectorAll('button')) as HTMLButtonElement[];
    const next = buttons().find((button) => button.textContent?.trim() === 'Continue')!;
    expect(next.disabled).toBe(true);
    buttons()
      .find((button) => button.textContent?.includes('alex@example.test'))!
      .click();
    fixture.detectChanges();
    expect(next.disabled).toBe(false);
    next.click();
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('h2')?.textContent).toContain('Choose access');
  });
  it('cannot select a missing or unverified delivery address', () => {
    const fixture = setup();
    fixture.componentRef.setInput('recipients', {
      items: [
        {
          ...recipient,
          delivery_address_status: 'unverified',
          eligibility: 'unavailable',
          eligibility_reason: 'Verify the address in the identity provider.',
        },
      ],
      next_cursor: null,
    });
    fixture.detectChanges();
    const row = fixture.nativeElement.querySelector('.recipient-choice') as HTMLButtonElement;
    expect(row.disabled).toBe(true);
    expect(fixture.nativeElement.textContent).toContain(
      'Verify the address in the identity provider.',
    );
    fixture.componentInstance.selectRecipient({
      ...recipient,
      delivery_address_status: 'unverified',
    });
    expect(fixture.componentInstance.selected()).toBeNull();
  });
  it('requests a preview with an opaque recipient reference and immutable grant fields only', () => {
    const fixture = setup();
    const component = fixture.componentInstance;
    let requested: unknown;
    component.previewRequested.subscribe((value) => (requested = value));
    component.selectRecipient(recipient);
    component.advance();
    component.scopeId = 'workspace';
    component.advance();
    expect(requested).toEqual({
      recipient_ref: recipient.recipient_ref,
      role: 'viewer',
      workspace_id: 'workspace',
      expires_in_hours: 24,
    });
    expect(component.step()).toBe('review');
    expect(fixture.nativeElement.textContent).not.toContain('Invitation sent');
  });
  it('requires a matching server preview before emitting a send request', () => {
    const fixture = setup();
    const component = fixture.componentInstance;
    let sends = 0;
    component.submitted.subscribe(() => sends++);
    component.selectRecipient(recipient);
    component.advance();
    component.scopeId = 'workspace';
    component.advance();
    component.submit();
    expect(sends).toBe(0);
    fixture.componentRef.setInput('preview', {
      draft: component.draft(),
      subject: 'Invitation to Research',
      sender_name: 'Research team',
      heading: 'You have been invited',
      paragraphs: ['Use your existing organization account.'],
      action_label: 'Review invitation',
      footer: 'Research operations',
    });
    fixture.detectChanges();
    component.role = 'editor';
    component.submit();
    expect(sends).toBe(0);
    component.role = 'viewer';
    component.submit();
    expect(sends).toBe(1);
    component.submit();
    expect(sends).toBe(1);
  });
  it('clears selected recipient and preview eligibility when the identity context changes', () => {
    const fixture = setup();
    const component = fixture.componentInstance;
    component.selectRecipient(recipient);
    component.advance();
    fixture.componentRef.setInput('contextKey', 'different-actor:organization:revision');
    fixture.detectChanges();
    expect(component.selected()).toBeNull();
    expect(component.step()).toBe('person');
  });
});

it('renders message content as text rather than executable email markup', async () => {
  const fixture = setup();
  const component = fixture.componentInstance;
  component.selectRecipient(recipient);
  component.advance();
  component.scopeId = 'workspace';
  component.advance();
  fixture.componentRef.setInput('preview', {
    draft: component.draft(),
    subject: 'Invitation',
    sender_name: 'Research',
    heading: 'Welcome',
    paragraphs: ['<img src=x onerror=alert(1)>'],
    action_label: 'Review invitation',
    footer: 'Research',
  });
  fixture.detectChanges();
  for (const block of await fixture.getDeferBlocks()) await block.render(DeferBlockState.Complete);
  await fixture.whenStable();
  fixture.detectChanges();
  expect(fixture.nativeElement.querySelector('.email-body p img')).toBeNull();
  expect(fixture.nativeElement.querySelector('.email-body')?.textContent).toContain(
    '<img src=x onerror=alert(1)>',
  );
});

it('allows an existing organization person to review a different workspace grant', () => {
  const fixture = setup();
  const component = fixture.componentInstance;
  component.selectRecipient({ ...recipient, eligibility: 'already_has_access' });
  expect(component.selected()?.recipient_ref).toBe(recipient.recipient_ref);
  component.advance();
  expect(component.step()).toBe('access');
});

it('cannot submit email when the server has not reported a ready delivery capability', () => {
  const fixture = setup(),
    component = fixture.componentInstance;
  component.selectRecipient(recipient);
  component.advance();
  component.scopeId = 'workspace';
  component.advance();
  fixture.componentRef.setInput('preview', {
    draft: component.draft(),
    subject: 'Invite',
    sender_name: 'Team',
    heading: 'Welcome',
    paragraphs: [],
    action_label: 'Review',
    footer: 'Team',
  });
  fixture.componentRef.setInput('deliveryAvailable', false);
  fixture.detectChanges();
  let submitted = 0;
  component.submitted.subscribe(() => submitted++);
  component.submit();
  expect(submitted).toBe(0);
  fixture.componentRef.setInput('deliveryAvailable', true);
  fixture.detectChanges();
  component.submit();
  expect(submitted).toBe(1);
});
