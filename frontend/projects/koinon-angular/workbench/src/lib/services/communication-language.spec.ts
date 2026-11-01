// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { TestBed } from '@angular/core/testing';
import { KoinonI18n } from '@fireflyframework/koinon-angular';
import { KoinonInvitationComposer } from '../../../../communications/invitations/invitation-composer';
import { KoinonRecipientInvitation } from '../../../../communications/invitations/recipient-invitation';
import { KoinonNotificationInbox } from '../../../../communications/inbox/notification-inbox';
import { KoinonCommunicationsAdmin } from '../../../../communications/admin/communications-admin';
import { KoinonNotificationTrigger } from '../../../../communications/notification-trigger';
function spanish() {
  TestBed.inject(KoinonI18n).apply({
    locale: 'es-ES',
    time_zone: 'Europe/Madrid',
    response_language: 'es',
  });
}
it('loads invitation vocabulary within its feature without opening another settings panel', () => {
  const fixture = TestBed.createComponent(KoinonInvitationComposer);
  spanish();
  fixture.detectChanges();
  expect(fixture.nativeElement.textContent).toContain('Elige una persona');
  expect(fixture.nativeElement.textContent).toContain('Busca en el directorio conectado');
});
it('localizes the wrong-account recovery action without revealing recipient details', () => {
  const fixture = TestBed.createComponent(KoinonRecipientInvitation);
  spanish();
  fixture.componentRef.setInput('problem', 'wrong_account');
  fixture.detectChanges();
  expect(fixture.nativeElement.textContent).toContain('Cambiar cuenta');
});
it('localizes own notification and admin navigation with independent lazy vocabulary', () => {
  const fixture = TestBed.createComponent(KoinonNotificationInbox);
  spanish();
  fixture.detectChanges();
  expect(fixture.nativeElement.textContent).toContain('Tus notificaciones');
  const admin = TestBed.createComponent(KoinonCommunicationsAdmin);
  admin.detectChanges();
  expect(admin.nativeElement.textContent).toContain('Historial de envíos');
});
it('announces unread notifications in the profile language', () => {
  const fixture = TestBed.createComponent(KoinonNotificationTrigger);
  spanish();
  fixture.componentRef.setInput('unread', 3);
  fixture.detectChanges();
  expect(fixture.nativeElement.querySelector('button').getAttribute('aria-label')).toBe(
    'Notificaciones, 3 sin leer',
  );
});
