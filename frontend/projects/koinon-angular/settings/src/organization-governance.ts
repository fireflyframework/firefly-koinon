// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  PendingTasks,
  inject,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import {
  KoinonButton,
  KoinonTextPipe,
  KoinonDatePipe,
  KoinonPagination,
  KoinonIcon,
  friendlyStatus,
} from '@fireflyframework/koinon-angular';
import type {
  CorporateProfileSyncPolicy,
  OrganizationProfileFields,
} from '@fireflyframework/koinon-sdk';
import { KoinonCorporateProfilePolicy } from './corporate-profile-policy';
import { KoinonOrganizationDirectory } from '@fireflyframework/koinon-angular/workbench';
@Component({
  selector: 'ffk-organization-governance',
  imports: [
    FormsModule,
    KoinonButton,
    KoinonTextPipe,
    KoinonDatePipe,
    KoinonPagination,
    KoinonIcon,
    KoinonCorporateProfilePolicy,
  ],
  templateUrl: './organization-governance.html',
  styleUrl: './organization-governance.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonOrganizationGovernance implements OnInit {
  readonly s = inject(KoinonOrganizationDirectory);
  private readonly tasks = inject(PendingTasks);
  readonly section = signal<'visibility' | 'profiles'>('visibility');
  readonly tabs = [
    { id: 'visibility', label: 'Directory visibility', icon: 'users' },
    { id: 'profiles', label: 'Corporate profiles', icon: 'link' },
  ] as const;
  visibility: 'administrators' | 'shared_workspaces' = 'administrators';
  providerId = '';
  enabled = false;
  titleClaim = '';
  unitClaim = '';
  managerClaim = '';
  profileSync: CorporateProfileSyncPolicy | null | undefined;
  ngOnInit() {
    this.tasks.run(async () => {
      await this.s.loadSettings();
      this.visibility = this.s.settings()?.visibility ?? 'administrators';
    });
  }
  openSection(section: 'visibility' | 'profiles') {
    if (this.s.pending() || (section === 'profiles' && !this.canMap())) return;
    this.section.set(section);
    if (section === 'profiles' && !this.s.providers()) this.tasks.run(() => this.s.loadProviders());
  }
  tabKey(event: KeyboardEvent) {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key) || this.s.pending()) return;
    event.preventDefault();
    this.openSection(
      event.key === 'Home'
        ? 'visibility'
        : event.key === 'End'
          ? 'profiles'
          : this.section() === 'visibility'
            ? 'profiles'
            : 'visibility',
    );
    const parent = (event.currentTarget as HTMLElement).parentElement;
    queueMicrotask(() => parent?.querySelector<HTMLButtonElement>('[aria-selected=true]')?.focus());
  }
  policy() {
    return this.profileSync === undefined
      ? (this.s.mapping()?.profile_sync ?? null)
      : this.profileSync;
  }
  claims(): OrganizationProfileFields {
    return {
      job_title: this.titleClaim || null,
      unit_external_key: this.unitClaim || null,
      manager_external_subject: this.managerClaim || null,
    };
  }
  setClaims(value: OrganizationProfileFields) {
    this.titleClaim = value.job_title ?? '';
    this.unitClaim = value.unit_external_key ?? '';
    this.managerClaim = value.manager_external_subject ?? '';
  }
  retry() {
    return this.section() === 'profiles'
      ? this.providerId
        ? this.chooseProvider()
        : this.s.loadProviders()
      : this.s.loadSettings();
  }
  readonly status = friendlyStatus;
  selectedProvider() {
    return this.s.providers()?.items.find((provider) => provider.id === this.providerId);
  }
  canMap() {
    return this.s.f.tenantPermissions().has('identity:manage');
  }
  providerPage(page: number) {
    if (this.s.pending()) return Promise.resolve(false);
    this.providerId = '';
    this.profileSync = undefined;
    this.s.mapping.set(null);
    return this.s.loadProviders(page);
  }
  async chooseProvider() {
    if (this.s.pending()) return;
    this.profileSync = undefined;
    if (!this.providerId) {
      this.s.mapping.set(null);
      return;
    }
    const selected = this.providerId;
    if (!(await this.s.loadMapping(selected)) || this.providerId !== selected) return;
    const mapping = this.s.mapping();
    if (mapping?.provider_id !== selected) return;
    this.enabled = mapping?.enabled ?? false;
    this.titleClaim = mapping?.fields?.job_title ?? '';
    this.unitClaim = mapping?.fields?.unit_external_key ?? '';
    this.managerClaim = mapping?.fields?.manager_external_subject ?? '';
  }
  saveMapping() {
    const mapping = this.s.mapping();
    if (!mapping) return;
    return this.s.saveMapping(this.providerId, {
      expected_revision: mapping.revision ?? 0,
      enabled: this.enabled,
      profile_sync:
        this.profileSync === undefined ? (mapping.profile_sync ?? null) : this.profileSync,
      fields: {
        job_title: this.titleClaim || null,
        unit_external_key: this.unitClaim || null,
        manager_external_subject: this.managerClaim || null,
      },
    });
  }
}
