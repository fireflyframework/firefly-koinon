// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { TestBed } from '@angular/core/testing';
import { signal } from '@angular/core';
import { KoinonOrganizationDirectory } from '@fireflyframework/koinon-angular/workbench';
import { KoinonOrganizationGovernance } from './organization-governance';

describe('corporate profile configuration', () => {
  it('preserves a saved directory profile policy when updating verified sign-in claims', () => {
    const policy = {
      interval_seconds: 1800,
      allow_personal_overrides: false,
      name_source: 'directory',
      avatar_source: 'directory',
      job_title_source: 'directory',
      unit_source: 'local',
      manager_source: 'verified_claims',
      google_department: 'department',
      keycloak_attributes: { picture: 'company_picture' },
    };
    let input: unknown;
    TestBed.configureTestingModule({
      providers: [
        {
          provide: KoinonOrganizationDirectory,
          useValue: {
            mapping: signal({ provider_id: 'company', revision: 4, profile_sync: policy }),
            saveMapping: (_id: string, value: unknown) => {
              input = value;
            },
          },
        },
      ],
    });
    const component = TestBed.createComponent(KoinonOrganizationGovernance).componentInstance;
    component.providerId = 'company';
    component.enabled = true;
    component.titleClaim = 'title';
    component.saveMapping();
    expect(input).toMatchObject({ expected_revision: 4, profile_sync: policy });
  });
});

it('explains directory profile synchronization and provider limits before configuration', async () => {
  TestBed.configureTestingModule({
    providers: [
      {
        provide: KoinonOrganizationDirectory,
        useValue: {
          f: { tenantPermissions: signal(new Set(['identity:manage'])) },
          settings: signal({ visibility: 'administrators' }),
          pending: signal(false),
          busy: signal(new Set()),
          error: signal(''),
          notice: signal(''),
          providers: signal({
            items: [{ id: 'company', name: 'Company', kind: 'entra', status: 'active' }],
          }),
          mapping: signal({ provider_id: 'company', revision: 4, profile_capabilities: [] }),
          loadSettings: async () => true,
          loadProviders: async () => true,
        },
      },
    ],
  });
  const fixture = TestBed.createComponent(KoinonOrganizationGovernance);
  fixture.componentInstance.providerId = 'company';
  fixture.detectChanges();
  await fixture.whenStable();
  fixture.detectChanges();
  const profiles = Array.from(
    fixture.nativeElement.querySelectorAll('[role=tab]') as NodeListOf<HTMLButtonElement>,
  ).find((tab) => tab.textContent?.trim() === 'Corporate profiles');
  profiles!.click();
  fixture.detectChanges();
  expect(fixture.nativeElement.textContent).toContain('Update method');
  expect(fixture.nativeElement.textContent).toContain(
    'Microsoft Entra app-only connections cannot read managers.',
  );
});
import { KoinonCorporateProfilePolicy } from './corporate-profile-policy';
it('keeps Entra manager directory source disabled and distinguishes capability requirements from consent', () => {
  const fixture = TestBed.createComponent(KoinonCorporateProfilePolicy);
  fixture.componentRef.setInput('kind', 'entra');
  fixture.componentRef.setInput('value', { manager_source: 'verified_claims' });
  fixture.componentRef.setInput('capabilities', [
    {
      field: 'manager',
      source: 'directory',
      supported: false,
      code: 'PROFILE_MANAGER_APP_UNSUPPORTED',
      required_permissions: ['User.Read.All'],
    },
  ]);
  fixture.detectChanges();
  const label = Array.from(
    fixture.nativeElement.querySelectorAll('label') as NodeListOf<HTMLLabelElement>,
  ).find((label) => label.textContent?.trim().startsWith('Manager'));
  const option = (label?.control as HTMLSelectElement)?.querySelector(
    'option[value="directory"]',
  ) as HTMLOptionElement;
  expect(option.disabled).toBe(true);
  expect(fixture.nativeElement.textContent).toContain(
    'They do not confirm that provider consent has been granted.',
  );
});
it('requires explicit Keycloak photo attribute and documents the installation origin restriction', () => {
  const fixture = TestBed.createComponent(KoinonCorporateProfilePolicy);
  fixture.componentRef.setInput('kind', 'keycloak');
  fixture.componentRef.setInput('value', { keycloak_attributes: {} });
  fixture.detectChanges();
  const label = Array.from(
    fixture.nativeElement.querySelectorAll('label') as NodeListOf<HTMLLabelElement>,
  ).find((label) => label.textContent?.trim() === 'Photo attribute');
  expect(label?.querySelector('input')).toBeInstanceOf(HTMLInputElement);
  expect(fixture.nativeElement.textContent).toContain('HTTPS origin allowed by this installation');
});
it('separates visibility from corporate profiles and hides claim controls for directory-owned fields', async () => {
  TestBed.configureTestingModule({
    providers: [
      {
        provide: KoinonOrganizationDirectory,
        useValue: {
          f: { tenantPermissions: signal(new Set(['identity:manage'])) },
          settings: signal({ visibility: 'administrators' }),
          pending: signal(false),
          busy: signal(new Set()),
          error: signal(''),
          notice: signal(''),
          providers: signal({
            items: [{ id: 'company', name: 'Company', kind: 'entra', status: 'active' }],
          }),
          mapping: signal({
            provider_id: 'company',
            revision: 4,
            enabled: true,
            profile_sync: {
              job_title_source: 'directory',
              unit_source: 'local',
              manager_source: 'verified_claims',
            },
            fields: { job_title: 'title', manager_external_subject: 'manager_external_subject' },
            profile_capabilities: [],
          }),
          loadSettings: async () => true,
          loadProviders: async () => true,
        },
      },
    ],
  });
  const fixture = TestBed.createComponent(KoinonOrganizationGovernance);
  fixture.componentInstance.providerId = 'company';
  fixture.componentInstance.titleClaim = 'title';
  fixture.detectChanges();
  await fixture.whenStable();
  fixture.detectChanges();
  const tabs = Array.from(
    fixture.nativeElement.querySelectorAll('[role="tab"]') as NodeListOf<HTMLButtonElement>,
  );
  expect(tabs.map((tab) => tab.textContent?.trim())).toEqual([
    'Directory visibility',
    'Corporate profiles',
  ]);
  tabs[1]!.click();
  fixture.detectChanges();
  await fixture.whenStable();
  fixture.detectChanges();
  const labels = Array.from(
    fixture.nativeElement.querySelectorAll('label') as NodeListOf<HTMLLabelElement>,
  );
  expect(labels.some((label) => label.textContent?.trim().startsWith('Job title claim'))).toBe(
    false,
  );
  expect(
    labels.some((label) => label.textContent?.trim().startsWith('Manager reference claim')),
  ).toBe(true);
  const source = fixture.nativeElement.querySelector(
    '#profile-source-job_title_source',
  ) as HTMLSelectElement;
  source.value = 'verified_claims';
  source.dispatchEvent(new Event('change'));
  fixture.detectChanges();
  await fixture.whenStable();
  fixture.detectChanges();
  expect(
    Array.from(
      fixture.nativeElement.querySelectorAll('label') as NodeListOf<HTMLLabelElement>,
    ).some((label) => label.textContent?.trim().startsWith('Job title claim')),
  ).toBe(true);
  expect(fixture.componentInstance.titleClaim).toBe('title');
  source.value = 'directory';
  source.dispatchEvent(new Event('change'));
  fixture.detectChanges();
  await fixture.whenStable();
  fixture.detectChanges();
  expect(fixture.componentInstance.titleClaim).toBe('title');
  expect(
    Array.from(
      fixture.nativeElement.querySelectorAll('label') as NodeListOf<HTMLLabelElement>,
    ).some((label) => label.textContent?.trim().startsWith('Job title claim')),
  ).toBe(false);
  const interval = fixture.nativeElement.querySelector(
    'input[name="sync-interval"]',
  ) as HTMLInputElement;
  interval.value = '0';
  interval.dispatchEvent(new Event('input'));
  fixture.detectChanges();
  await fixture.whenStable();
  fixture.detectChanges();
  expect(
    (fixture.nativeElement.querySelector('.profile-save button') as HTMLButtonElement)?.disabled,
  ).toBe(true);
  tabs[1]!.dispatchEvent(new KeyboardEvent('keydown', { key: 'Home', bubbles: true }));
  fixture.detectChanges();
  await fixture.whenStable();
  fixture.detectChanges();
  expect(tabs[0]!.getAttribute('aria-selected')).toBe('true');
  expect(tabs[0]!.tabIndex).toBe(0);
  tabs[0]!.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true }));
  fixture.detectChanges();
  await fixture.whenStable();
  fixture.detectChanges();
  expect(tabs[1]!.getAttribute('aria-selected')).toBe('true');
});
