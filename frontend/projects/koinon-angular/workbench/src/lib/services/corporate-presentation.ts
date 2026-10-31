// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { Injectable, OnDestroy, computed, effect, inject, signal } from '@angular/core';
import type {
  OrganizationPresentation,
  OrganizationPresentationInput,
} from '@fireflyframework/koinon-sdk';
import { KoinonOrganizationDirectory } from './organization-directory';
@Injectable()
export class KoinonCorporatePresentation implements OnDestroy {
  readonly directory = inject(KoinonOrganizationDirectory);
  private destroyed = false;
  private writeEpoch = 0;
  private key = this.directory.contextIdentity();
  private readonly value = signal<OrganizationPresentation | null>(null);
  private readonly photo = signal('');
  readonly notice = signal('');
  readonly presentation = computed(() =>
    !this.destroyed && this.key === this.directory.contextIdentity() ? this.value() : null,
  );
  readonly avatar = computed(() => (this.presentation() ? this.photo() : ''));
  readonly loading = computed(() => this.directory.busy().has('corporate-presentation'));
  readonly pending = computed(() => this.directory.pending());
  constructor() {
    effect(() => this.sync());
  }
  private clearPhoto() {
    if (this.photo()) URL.revokeObjectURL(this.photo());
    this.photo.set('');
  }
  private sync() {
    const key = this.directory.contextIdentity();
    if (key === this.key) return;
    this.key = key;
    this.value.set(null);
    this.notice.set('');
    this.clearPhoto();
  }
  async load() {
    this.sync();
    if (this.destroyed || this.pending()) return false;
    const epoch = this.writeEpoch;
    const loaded = await this.directory.run(
      'corporate-presentation',
      (signal) =>
        this.directory.clients
          .get()
          .corporateProfiles.presentation(this.directory.f.tenantId(), this.directory.scope(), {
            signal,
          }),
      (value) => {
        if (this.destroyed || epoch !== this.writeEpoch) return;
        this.clearPhoto();
        this.value.set(value.tenant_id === this.directory.f.tenantId() ? value : null);
      },
    );
    if (loaded && epoch === this.writeEpoch) await this.loadPhoto();
    return loaded;
  }
  private loadPhoto() {
    const value = this.presentation();
    if (!value?.profile_id || !value.avatar_version || value.avatar_source === 'personal')
      return Promise.resolve(false);
    return this.directory.run(
      'corporate-presentation-photo',
      (signal) =>
        this.directory.clients
          .get()
          .organizationPeople.avatar(value.tenant_id, value.profile_id!, this.directory.scope(), {
            signal,
          }),
      (download) => {
        if (this.presentation() !== value || download.not_modified) return;
        this.clearPhoto();
        this.photo.set(URL.createObjectURL(download.blob));
      },
      true,
    );
  }
  async save(
    nameMode: NonNullable<OrganizationPresentationInput['name_mode']>,
    avatarMode: NonNullable<OrganizationPresentationInput['avatar_mode']>,
  ) {
    this.sync();
    const value = this.presentation();
    if (
      !value ||
      this.pending() ||
      value.revision === undefined ||
      (!value.allow_personal_overrides && (nameMode === 'personal' || avatarMode === 'personal'))
    )
      return false;
    this.notice.set('');
    ++this.writeEpoch;
    const saved = await this.directory.run(
      'write',
      (signal) =>
        this.directory.clients
          .get()
          .corporateProfiles.updatePresentation(
            value.tenant_id,
            { expected_revision: value.revision!, name_mode: nameMode, avatar_mode: avatarMode },
            this.directory.scope(),
            { signal },
          ),
      (result) => {
        if (this.presentation() !== value || result.tenant_id !== value.tenant_id) return;
        this.value.set(result);
        this.clearPhoto();
        this.notice.set('Organization presentation saved.');
      },
    );
    if (saved) await this.loadPhoto();
    return saved;
  }
  refresh() {
    this.sync();
    const value = this.presentation();
    if (
      !value ||
      this.pending() ||
      ['not_configured', 'not_bound', 'queued', 'running', 'conflict'].includes(
        value.status ?? 'not_configured',
      )
    )
      return Promise.resolve(false);
    this.notice.set('');
    ++this.writeEpoch;
    return this.directory.run(
      'write',
      (signal) =>
        this.directory.clients
          .get()
          .corporateProfiles.refreshSelf(value.tenant_id, {}, this.directory.scope(), { signal }),
      (result) => {
        if (this.presentation() !== value || result.tenant_id !== value.tenant_id) return;
        this.value.set({
          ...value,
          status: result.status,
          last_attempt_at: result.last_attempt_at,
        });
        this.notice.set(
          result.status === 'queued' || result.status === 'running'
            ? 'Profile refresh queued. Check the status shortly.'
            : 'Profile refresh status updated.',
        );
      },
    );
  }
  ngOnDestroy() {
    this.destroyed = true;
    this.value.set(null);
    this.notice.set('');
    this.clearPhoto();
  }
}
