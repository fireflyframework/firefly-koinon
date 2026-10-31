// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import {
  ChangeDetectionStrategy,
  Component,
  EventEmitter,
  Input,
  Output,
  inject,
} from '@angular/core';
import { FormsModule, ControlContainer, NgForm } from '@angular/forms';
import { KoinonTextPipe } from '@fireflyframework/koinon-angular';
import type {
  CorporateProfileSyncPolicy,
  CorporateProfileFieldCapability,
  KeycloakProfileAttributes,
  OrganizationProfileFields,
} from '@fireflyframework/koinon-sdk';
@Component({
  selector: 'ffk-corporate-profile-policy',
  imports: [FormsModule, KoinonTextPipe],
  viewProviders: [
    {
      provide: ControlContainer,
      useFactory: () => inject(NgForm, { skipSelf: true, optional: true }),
    },
  ],
  templateUrl: './corporate-profile-policy.html',
  styleUrl: './corporate-profile-policy.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonCorporateProfilePolicy {
  @Input() value: CorporateProfileSyncPolicy | null = null;
  @Input() kind?: string;
  @Input() claims: OrganizationProfileFields = {};
  @Output() claimsChange = new EventEmitter<OrganizationProfileFields>();
  @Input() capabilities: CorporateProfileFieldCapability[] = [];
  @Input() disabled = false;
  @Output() valueChange = new EventEmitter<CorporateProfileSyncPolicy | null>();
  readonly positionFields = [
    {
      key: 'job_title_source',
      claim: 'job_title',
      attribute: 'job_title',
      label: 'Job title',
      claimLabel: 'Job title claim',
      attributeLabel: 'Job title attribute',
      options: [
        { value: 'job_title', label: 'Job title' },
        { value: 'title', label: 'Title' },
      ],
    },
    {
      key: 'unit_source',
      claim: 'unit_external_key',
      attribute: 'department',
      label: 'Department',
      claimLabel: 'Unit reference claim',
      attributeLabel: 'Department attribute',
      options: [
        { value: 'unit_external_key', label: 'Organization unit reference' },
        { value: 'department', label: 'Department reference' },
      ],
    },
    {
      key: 'manager_source',
      claim: 'manager_external_subject',
      attribute: 'manager',
      label: 'Manager',
      claimLabel: 'Manager reference claim',
      attributeLabel: 'Manager reference attribute',
      options: [{ value: 'manager_external_subject', label: 'Manager identity reference' }],
    },
  ] as const;
  updateInterval(value: number | null) {
    this.update({ interval_seconds: value === null ? 0 : Math.round(value * 60) });
  }
  claim(key: keyof OrganizationProfileFields, value: string) {
    if (!this.disabled) this.claimsChange.emit({ ...this.claims, [key]: value || null });
  }
  source(key: 'job_title_source' | 'unit_source' | 'manager_source') {
    return this.value?.[key] ?? (key === 'manager_source' ? 'verified_claims' : 'directory');
  }
  configuredClaim(key: keyof OrganizationProfileFields) {
    return this.claims[key] ?? '';
  }
  existingClaim(field: (typeof this.positionFields)[number]) {
    return (
      !!this.claims[field.claim] &&
      !field.options.some((option) => option.value === this.claims[field.claim])
    );
  }
  enable(enabled: boolean) {
    if (this.disabled) return;
    this.valueChange.emit(
      enabled
        ? {
            interval_seconds: 900,
            allow_personal_overrides: true,
            name_source: 'directory',
            avatar_source: 'directory',
            job_title_source: 'directory',
            unit_source: 'directory',
            manager_source: 'verified_claims',
            google_department: 'department',
            keycloak_attributes: {},
          }
        : null,
    );
  }
  update(patch: Partial<CorporateProfileSyncPolicy>) {
    if (!this.disabled && this.value) this.valueChange.emit({ ...this.value, ...patch });
  }
  positionSource(
    key: 'job_title_source' | 'unit_source' | 'manager_source',
    value: 'directory' | 'verified_claims' | 'local',
  ) {
    this.update({ [key]: value });
  }
  attribute(key: keyof KeycloakProfileAttributes, value: string) {
    this.update({
      keycloak_attributes: { ...this.value?.keycloak_attributes, [key]: value.trim() || null },
    });
  }
  fieldLabel(field: CorporateProfileFieldCapability['field']) {
    return {
      display_name: 'Display name',
      avatar: 'Photo',
      job_title: 'Job title',
      department: 'Department',
      manager: 'Manager',
    }[field];
  }
  sourceLabel(source: CorporateProfileFieldCapability['source']) {
    return {
      directory: 'Corporate directory',
      verified_claims: 'Verified sign-in claims',
      local: 'Managed locally',
      personal: 'Personal profile',
    }[source];
  }
  capabilityMessage(code: string | null | undefined) {
    if (code === 'PROFILE_MANAGER_APP_UNSUPPORTED')
      return 'Microsoft Entra app-only connections cannot read managers.';
    if (code === 'PROFILE_ATTRIBUTE_REQUIRED')
      return 'Configure the corresponding Keycloak attribute.';
    if (code === 'PROFILE_CLAIM_MAPPING_REQUIRED') return 'Select a verified sign-in claim above.';
    return 'This field is unavailable with the saved configuration.';
  }
}
