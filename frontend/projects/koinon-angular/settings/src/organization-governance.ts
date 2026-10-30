// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { ChangeDetectionStrategy, Component, OnInit, PendingTasks, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import {
  KoinonButton,
  KoinonTextPipe,
  KoinonDatePipe,
  KoinonPagination,
  friendlyStatus,
} from '@fireflyframework/koinon-angular';
import { KoinonOrganizationDirectory } from '@fireflyframework/koinon-angular/workbench';
@Component({
  selector: 'ffk-organization-governance',
  imports: [FormsModule, KoinonButton, KoinonTextPipe, KoinonDatePipe, KoinonPagination],
  templateUrl: './organization-governance.html',
  styleUrl: './organization-directory.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonOrganizationGovernance implements OnInit {
  readonly s = inject(KoinonOrganizationDirectory);
  private readonly tasks = inject(PendingTasks);
  visibility: 'administrators' | 'shared_workspaces' = 'administrators';
  providerId = '';
  enabled = false;
  titleClaim = '';
  unitClaim = '';
  managerClaim = '';
  ngOnInit() {
    this.tasks.run(async () => {
      await this.s.loadSettings();
      this.visibility = this.s.settings()?.visibility ?? 'administrators';
      if (this.canMap()) await this.s.loadProviders();
    });
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
    this.s.mapping.set(null);
    return this.s.loadProviders(page);
  }
  async chooseProvider() {
    if (this.s.pending()) return;
    if (!this.providerId) {
      this.s.mapping.set(null);
      return;
    }
    await this.s.loadMapping(this.providerId);
    const mapping = this.s.mapping();
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
      fields: {
        job_title: this.titleClaim || null,
        unit_external_key: this.unitClaim || null,
        manager_external_subject: this.managerClaim || null,
      },
    });
  }
}
