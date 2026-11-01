// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { TestBed } from '@angular/core/testing';
import { KoinonFacade, KoinonI18n, provideKoinonClient } from '@fireflyframework/koinon-angular';
import { KoinonClient, type KoinonTransport } from '@fireflyframework/koinon-sdk';
import type {
  HealthComponent,
  PlatformHealth,
  SystemInformation,
} from '@fireflyframework/koinon-sdk/platform-health';
import { KoinonPlatformHealthPanel } from './platform-health-panel';
const base: HealthComponent = {
  id: 'database-primary',
  configured: true,
  status: 'passed',
  basis: 'observed',
  freshness: 'current',
  observed_at: new Date(Date.now() - 1000).toISOString(),
  expires_at: '2100-01-01T00:00:00Z',
  reason: 'DATABASE_OK',
  remediation: 'none',
  coverage: 'complete',
};
async function setup(spanish = false) {
  const report: PlatformHealth = {
    tenant_id: 'north',
    checked_at: new Date().toISOString(),
    components: [
      base,
      {
        ...base,
        id: 'model-configuration',
        status: 'unknown',
        basis: 'configuration',
        observed_at: null,
        expires_at: null,
        reason: 'MODEL_CONFIGURATION_PRESENT',
        remediation: 'review_configuration',
        coverage: 'unavailable',
      },
      {
        ...base,
        id: 'ingestion-documents',
        status: 'failed',
        reason: 'INGESTION_FAILURES',
        remediation: 'review_ingestion',
        coverage: 'partial',
        counts: { observed_total: 3, observed_failed: 1 },
      },
    ],
  };
  const info: SystemInformation = {
    tenant_id: 'north',
    checked_at: report.checked_at,
    serving_role: 'api',
    components: [
      { id: 'backend', distribution: 'firefly-koinon', version: '26.11.3', available: true },
      { id: 'framework', distribution: 'pyfly', version: '26.10.32', available: true },
    ],
    capabilities: {
      knowledge_enabled: true,
      mcp_enabled: true,
      communications_enabled: false,
      scheduled_consumers_enabled: false,
    },
    limits: [{ id: 'ingestion_raw_max_bytes', value: 268435456, unit: 'bytes', scope: 'file' }],
    artifacts: [
      {
        component: 'backend',
        kind: 'license',
        present: true,
        sha256: 'a'.repeat(64),
        content_type: 'text/plain',
      },
      { component: 'backend', kind: 'sbom', present: null },
    ],
  };
  const transport: KoinonTransport = {
    request: async <T>(_method: unknown, path: string) =>
      (path.endsWith('/health') ? report : info) as T,
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
      { id: 'north', name: 'North', roles: ['admin'], permissions: ['catalog:read', 'audit:read'] },
    ],
    workspaces: [],
    memberships: [
      {
        id: 'admin',
        subject: 'alex',
        tenant_id: 'north',
        workspace_id: null,
        role: 'admin',
        active: true,
      },
    ],
  });
  if (spanish)
    TestBed.inject(KoinonI18n).apply({
      locale: 'es-ES',
      time_zone: 'Europe/Madrid',
      response_language: 'es',
    });
  const fixture = TestBed.createComponent(KoinonPlatformHealthPanel);
  fixture.detectChanges();
  await fixture.whenStable();
  fixture.detectChanges();
  return { fixture, report, info };
}
it('separates configured models from observed checks and exposes bounded evidence details', async () => {
  const { fixture } = await setup();
  const el: HTMLElement = fixture.nativeElement;
  expect(el.textContent).toContain('Platform health');
  expect(el.textContent).not.toContain('All systems operational');
  const model = [...el.querySelectorAll<HTMLButtonElement>('.service-row')].find((button) =>
    button.textContent?.includes('Knowledge model configuration'),
  )!;
  expect(model.textContent).toContain('Not checked');
  model.click();
  fixture.detectChanges();
  expect(el.querySelector('#health-detail')?.textContent).toContain(
    'Generation and connectivity have not been tested here.',
  );
});
it('filters attention without implying observed record counts are organization totals', async () => {
  const { fixture } = await setup();
  const el: HTMLElement = fixture.nativeElement;
  const select = el.querySelector<HTMLSelectElement>('#health-filter')!;
  select.value = 'failed';
  select.dispatchEvent(new Event('change'));
  fixture.detectChanges();
  expect(el.querySelectorAll('.service-row')).toHaveLength(1);
  expect(el.querySelector('#health-detail')?.textContent).toContain('Partial coverage');
  expect(el.querySelector('#health-detail')?.textContent).toContain('Observed records');
});
it('shows real versions and unknown build and SBOM provenance without inventing links', async () => {
  const { fixture } = await setup();
  const el: HTMLElement = fixture.nativeElement;
  [...el.querySelectorAll<HTMLButtonElement>('[role=tab]')]
    .find((tab) => tab.textContent?.includes('System information'))!
    .click();
  fixture.detectChanges();
  await fixture.whenStable();
  fixture.detectChanges();
  expect(el.textContent).toContain('26.11.3');
  expect(el.textContent).toContain('26.10.32');
  expect(el.textContent).toContain('Not reported');
  expect(el.textContent).toContain('256 MiB');
  expect(el.querySelector('.artifacts')?.textContent).toContain('Unknown');
  expect(el.querySelector('.artifacts')?.querySelectorAll('a')).toHaveLength(0);
});
it('renders health reasons and administration labels in Spanish', async () => {
  const { fixture } = await setup(true);
  const el: HTMLElement = fixture.nativeElement;
  expect(el.textContent).toContain('Salud de la plataforma');
  expect(el.textContent).toContain('Requiere atención');
  expect(el.textContent).toContain('Base de datos del catálogo');
});
it('does not render a private URL or path as a package version, build revision or checksum', async () => {
  const { fixture, info } = await setup();
  const el: HTMLElement = fixture.nativeElement;
  info.components[0].version = 'postgresql://secret@internal.example/private';
  info.build_revision = '/private/build/path';
  info.artifacts[0].sha256 = '/private/license/path';
  [...el.querySelectorAll<HTMLButtonElement>('[role=tab]')]
    .find((tab) => tab.textContent?.includes('System information'))!
    .click();
  fixture.detectChanges();
  await fixture.whenStable();
  fixture.detectChanges();
  expect(el.textContent).not.toContain('secret');
  expect(el.textContent).not.toContain('/private');
  expect(el.textContent).not.toContain('internal.example');
  expect(el.textContent).toContain('Not reported');
  expect(el.querySelector('.artifacts')?.textContent).toContain('Unknown');
});
