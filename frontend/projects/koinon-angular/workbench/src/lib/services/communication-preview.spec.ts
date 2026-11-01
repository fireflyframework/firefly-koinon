// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { TestBed } from '@angular/core/testing';
import { DEFAULT_BRANDING } from '@fireflyframework/koinon-angular/workbench';
import { KoinonEmailPreview } from '../../../../communications/email-preview/email-preview';
it('uses the validated light email palette even when the surrounding app is dark', () => {
  const fixture = TestBed.createComponent(KoinonEmailPreview);
  fixture.componentRef.setInput('value', {
    draft: {
      recipient_ref: 'opaque-reference',
      role: 'viewer',
      workspace_id: null,
      expires_in_hours: 24,
    },
    subject: 'Invitation',
    sender_name: 'Research',
    product_name: 'Research',
    heading: 'Welcome',
    paragraphs: ['<img src=x onerror=alert(1)>'],
    action_label: 'Review invitation',
    footer: 'Research',
    branding: { ...DEFAULT_BRANDING, product_name: 'Research' },
  });
  fixture.detectChanges();
  const body = fixture.nativeElement.querySelector('.email-body') as HTMLElement;
  expect(body.style.getPropertyValue('--koinon-brand-surface')).toBe('#ffffff');
  expect(body.style.getPropertyValue('--koinon-brand-action')).toBe('#ffb34a');
  expect(body.style.getPropertyValue('--koinon-brand-action_text')).toBe('#10110f');
  expect(body.querySelector('p img')).toBeNull();
  expect(body.textContent).toContain('<img src=x onerror=alert(1)>');
});

it('keeps mandatory origin attribution independent of customized branding', () => {
  const fixture = TestBed.createComponent(KoinonEmailPreview);
  fixture.componentRef.setInput('value', {
    subject: 'Invite',
    sender_name: 'Custom',
    heading: 'Welcome',
    paragraphs: [],
    action_label: 'Review',
    footer: 'Custom footer',
    branding: { ...DEFAULT_BRANDING, product_name: 'Custom' },
    organization_name: 'Research',
    workspace_name: 'Shared sources',
    draft: {
      recipient_ref: 'opaque-reference',
      role: 'viewer',
      workspace_id: 'workspace',
      expires_in_hours: 24,
    },
  });
  fixture.detectChanges();
  expect(fixture.nativeElement.textContent).toContain('Powered by koinon');
  expect(fixture.nativeElement.textContent).toContain('Firefly Software Foundation');
  expect(fixture.nativeElement.textContent).toContain('Shared sources');
});
it('isolates actual renderer HTML in an opaque scriptless frame with tracking and navigation disabled', () => {
  const fixture = TestBed.createComponent(KoinonEmailPreview);
  fixture.componentRef.setInput('value', {
    subject: 'Invite',
    sender_name: 'Custom',
    heading: 'Welcome',
    paragraphs: [],
    action_label: 'Review',
    footer: 'Footer',
    rendered_html:
      '<html><head><meta http-equiv="refresh" content="0;url=https://foreign.invalid/refresh"></head><body style="font-family:Manrope,Arial,sans-serif;color:#272820"><a href="https://foreign.invalid/navigation" target="_blank">Open</a><script>window.parent.secret=1</script><img src="https://foreign.invalid/tracker"/></body></html>',
    rendered_text: 'Plain message',
    draft: {
      recipient_ref: 'opaque-reference',
      role: 'viewer',
      workspace_id: null,
      expires_in_hours: 24,
    },
  });
  fixture.detectChanges();
  const frame = fixture.nativeElement.querySelector('iframe') as HTMLIFrameElement;
  expect(frame.getAttribute('sandbox')).toBe('');
  expect(frame.getAttribute('referrerpolicy')).toBe('no-referrer');
  expect(frame.getAttribute('srcdoc')).toContain("default-src 'none'");
  expect(frame.getAttribute('srcdoc')).toContain('img-src data:');
  expect(frame.getAttribute('srcdoc')).not.toContain('href=');
  expect(frame.getAttribute('srcdoc')).not.toContain('foreign.invalid/refresh');
  expect(frame.getAttribute('srcdoc')).not.toContain('<script>');
  expect(frame.getAttribute('srcdoc')).toContain(
    'font-family:Manrope,Arial,sans-serif;color:#272820',
  );
});
