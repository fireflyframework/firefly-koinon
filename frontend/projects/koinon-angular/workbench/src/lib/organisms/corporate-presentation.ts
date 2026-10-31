// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import {
  ChangeDetectionStrategy,
  Component,
  PendingTasks,
  effect,
  inject,
  untracked,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import type { KoinonCorporatePresentation } from '../services/corporate-presentation';
import { KoinonAccount } from '../services/account';
import { KoinonOrganizationDirectory } from '../services/organization-directory';
import { KoinonButton } from '../atoms/button';
import { KoinonTextPipe, KoinonDatePipe } from '../foundations/i18n';
@Component({
  selector: 'ffk-corporate-presentation',
  imports: [FormsModule, KoinonButton, KoinonTextPipe, KoinonDatePipe],
  templateUrl: './corporate-presentation.html',
  styleUrl: './corporate-presentation.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonCorporatePresentationPanel {
  readonly state = signal<KoinonCorporatePresentation | null>(null);
  readonly directory = inject(KoinonOrganizationDirectory);
  private readonly account = inject(KoinonAccount, { optional: true });
  private readonly tasks = inject(PendingTasks);
  nameMode: 'organization' | 'personal' = 'organization';
  avatarMode: 'organization' | 'personal' = 'organization';
  constructor() {
    effect(() => {
      this.directory.contextIdentity();
      untracked(() => {
        this.nameMode = 'organization';
        this.avatarMode = 'organization';
        if (!this.directory.denied()) this.tasks.run(() => this.reload());
      });
    });
  }
  async reload() {
    const state = await this.account?.organizationPresentation();
    this.state.set(state ?? null);
    if (state && (await state.load())) {
      const value = state.presentation();
      this.nameMode = value?.name_mode ?? 'organization';
      this.avatarMode = value?.avatar_mode ?? 'organization';
    }
  }
  avatar() {
    const state = this.state();
    return state?.presentation()?.avatar_source === 'personal'
      ? (this.account?.avatar() ?? '')
      : (state?.avatar() ?? '');
  }
  save() {
    return this.state()?.save(this.nameMode, this.avatarMode);
  }
  status(value: string | undefined) {
    switch (value) {
      case 'current':
        return 'Up to date';
      case 'stale':
        return 'Last synced profile retained';
      case 'queued':
        return 'Refresh queued';
      case 'running':
        return 'Refreshing profile';
      case 'not_bound':
        return 'Sign in with your organization provider to connect your profile.';
      case 'not_configured':
        return 'Corporate profile sync is not configured.';
      case 'conflict':
        return 'Ask your organization administrator to review the profile source, then sign in again.';
      default:
        return 'Corporate profile is temporarily unavailable.';
    }
  }
  fieldLabel(field: string) {
    return (
      (
        {
          display_name: 'Display name',
          avatar: 'Photo',
          job_title: 'Job title',
          department: 'Department',
          manager: 'Manager',
        } as Record<string, string>
      )[field] ?? 'Profile field'
    );
  }
  fieldStatus(status: string) {
    return (
      (
        {
          current: 'Up to date',
          empty: 'Not set',
          unavailable: 'Not available',
          unsupported: 'Unsupported source',
          stale: 'Last synced value retained',
          not_observed: 'Not yet observed',
        } as Record<string, string>
      )[status] ?? 'Not available'
    );
  }
  fieldSource(source: string) {
    return (
      (
        {
          directory: 'Corporate directory',
          verified_claims: 'Verified sign-in claims',
          local: 'Managed locally',
          personal: 'Personal profile',
        } as Record<string, string>
      )[source] ?? 'Not available'
    );
  }
  fieldReason(code: string | null | undefined) {
    if (code === 'PROFILE_MANAGER_APP_UNSUPPORTED')
      return 'Microsoft Entra app-only connections cannot read managers.';
    if (code === 'PROFILE_ATTRIBUTE_REQUIRED')
      return 'The organization administrator needs to configure a profile attribute.';
    if (code === 'PROFILE_CLAIM_MAPPING_REQUIRED')
      return 'The organization administrator needs to configure a verified sign-in claim.';
    if (code === 'PROFILE_PHOTO_ORIGIN_DENIED')
      return 'The photo origin is not allowed by this installation.';
    return 'The provider could not supply a usable value for this field.';
  }
  canRefresh() {
    return !['not_configured', 'not_bound', 'queued', 'running', 'conflict'].includes(
      this.state()?.presentation()?.status ?? 'not_configured',
    );
  }
}
