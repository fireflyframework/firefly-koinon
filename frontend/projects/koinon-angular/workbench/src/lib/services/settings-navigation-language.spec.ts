// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { TestBed } from '@angular/core/testing';
import { KoinonClient, type KoinonTransport } from '@fireflyframework/koinon-sdk';
import { KoinonFacade, KoinonI18n, provideKoinonClient } from '@fireflyframework/koinon-angular';
import { KoinonSettingsPage } from '@fireflyframework/koinon-angular/settings';
it('translates organization navigation before a directory view has been opened', async () => {
  const transport: KoinonTransport = {
    request: async <T>() =>
      ({ providers: [], provider_types: [], connections: [], checks: [] }) as T,
    stream: () => {
      throw new Error('Unexpected stream');
    },
  };
  TestBed.configureTestingModule({
    providers: [KoinonFacade, ...provideKoinonClient(new KoinonClient({ transport }), transport)],
  });
  const f = TestBed.inject(KoinonFacade);
  f.tenantId.set('north');
  f.context.set({
    subject: 'alex',
    tenants: [
      {
        id: 'north',
        name: 'North',
        roles: ['admin'],
        permissions: ['members:write', 'providers:write'],
      },
    ],
    memberships: [],
    workspaces: [],
    workspace_permissions: {},
  });
  TestBed.inject(KoinonI18n).apply({ locale: 'es-ES', time_zone: 'UTC', response_language: 'es' });
  const fixture = TestBed.createComponent(KoinonSettingsPage);
  fixture.detectChanges();
  await fixture.whenStable();
  fixture.detectChanges();
  expect(fixture.componentInstance.section()).toBe('providers');
  expect(fixture.nativeElement.querySelector('.settings-navigation').textContent).toContain(
    'Estructura de la organización',
  );
});
