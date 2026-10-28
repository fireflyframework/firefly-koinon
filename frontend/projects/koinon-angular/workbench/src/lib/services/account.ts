// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { Injectable, OnDestroy, effect, inject, signal } from '@angular/core';
import type {
  UserProfile,
  ProfileInput,
  PersonalToken,
  PersonalTokenInput,
  TokenScopeOptions,
  Page,
} from '@fireflyframework/koinon-sdk';
import { KoinonClientContext } from './client-context';
import { KoinonFacade } from '../koinon-facade';
import { KoinonI18n } from '../foundations/i18n';
@Injectable()
export class KoinonAccount implements OnDestroy {
  private readonly clients = inject(KoinonClientContext);
  private readonly f = inject(KoinonFacade);
  private readonly i18n = inject(KoinonI18n);
  private epoch = 0;
  private key = '';
  private avatarObjectUrl = '';
  private avatarRevision = 0;
  readonly profile = signal<UserProfile | null>(null);
  readonly avatar = signal('');
  readonly pending = signal(false);
  readonly error = signal('');
  readonly notice = signal('');
  readonly tokens = signal<Page<PersonalToken>>({ items: [] });
  readonly tokenScopes = signal<TokenScopeOptions | null>(null);
  readonly tokenFilter = signal({ page: 1, page_size: 25, q: '', status: 'active' });
  constructor() {
    this.key = this.contextKey();
    effect(() => this.syncIdentity());
  }
  private contextKey() {
    return (this.f.context()?.subject ?? '') + ':' + this.clients.revision();
  }
  private syncIdentity() {
    const key = this.contextKey();
    if (key === this.key) return;
    this.key = key;
    ++this.epoch;
    this.profile.set(null);
    this.tokens.set({ items: [] });
    this.tokenScopes.set(null);
    this.error.set('');
    this.notice.set('');
    this.pending.set(false);
    this.clearAvatar();
    this.i18n.apply({ locale: 'en-US', time_zone: 'UTC', response_language: 'en' });
  }
  private clearAvatar() {
    ++this.avatarRevision;
    if (this.avatarObjectUrl) URL.revokeObjectURL(this.avatarObjectUrl);
    this.avatarObjectUrl = '';
    this.avatar.set('');
  }
  private accept(profile: UserProfile) {
    if (
      !['subject', 'display_name', 'locale', 'time_zone', 'response_language'].every(
        (key) => typeof profile[key as keyof UserProfile] === 'string',
      )
    )
      throw new Error('Your profile response is incomplete.');
    this.profile.set(profile);
    this.i18n.apply(profile);
  }
  private async perform<T>(
    operation: () => Promise<T>,
    apply: ((value: T) => void) | undefined,
    notice = '',
  ): Promise<T | null> {
    this.syncIdentity();
    const epoch = this.epoch;
    this.pending.set(true);
    this.error.set('');
    this.notice.set('');
    try {
      const value = await operation();
      if (epoch !== this.epoch || this.key !== this.contextKey()) return null;
      apply?.(value);
      this.notice.set(notice);
      return value;
    } catch (error) {
      if (epoch === this.epoch) {
        if (error instanceof Error && 'status' in error && error.status === 401)
          this.f.authRequired.set(true);
        this.error.set(
          error instanceof Error ? error.message : 'Your account could not be updated.',
        );
      }
      return null;
    } finally {
      if (epoch === this.epoch) this.pending.set(false);
    }
  }
  async load() {
    const profile = await this.perform(
      () => this.clients.get().profile.get(),
      (value) => this.accept(value),
    );
    if (profile) await this.loadAvatar(profile);
    return profile;
  }
  async save(input: ProfileInput) {
    return !!(await this.perform(
      () => this.clients.get().profile.update(input),
      (value) => this.accept(value),
      'Profile saved.',
    ));
  }
  private async loadAvatar(profile: UserProfile) {
    this.clearAvatar();
    if (!profile.avatar_version) return;
    const epoch = this.epoch,
      request = this.avatarRevision;
    try {
      const blob = await this.clients.get().profile.avatar();
      if (
        epoch !== this.epoch ||
        this.key !== this.contextKey() ||
        request !== this.avatarRevision ||
        profile.avatar_version !== this.profile()?.avatar_version
      )
        return;
      this.avatarObjectUrl = URL.createObjectURL(blob);
      this.avatar.set(this.avatarObjectUrl);
    } catch {
      if (epoch === this.epoch && request === this.avatarRevision) this.clearAvatar();
    }
  }
  async uploadAvatar(file: File) {
    if (!['image/png', 'image/jpeg', 'image/webp'].includes(file.type) || file.size > 2097152) {
      this.error.set('Choose a PNG, JPEG or WebP image no larger than 2 MiB.');
      return false;
    }
    const profile = await this.perform(
      () => this.clients.get().profile.uploadAvatar(file),
      (value) => this.accept(value),
      'Profile photo updated.',
    );
    if (profile) await this.loadAvatar(profile);
    return !!profile;
  }
  async removeAvatar() {
    return !!(await this.perform(
      () => this.clients.get().profile.deleteAvatar(),
      (profile) => {
        this.accept(profile);
        this.clearAvatar();
      },
      'Profile photo removed.',
    ));
  }
  async loadTokens(
    filter: Partial<{ page: number; page_size: number; q: string; status: string }> = {},
  ) {
    this.tokenFilter.update((value) => ({ ...value, ...filter }));
    return this.perform(
      () => this.clients.get().tokens.list({ query: this.tokenFilter() }),
      (value) => this.tokens.set(value),
    );
  }
  async loadTokenScopes() {
    return this.perform(
      () => this.clients.get().tokens.scopes(this.f.tenantId(), this.f.workspaceId() || undefined),
      (value) => this.tokenScopes.set(value),
    );
  }
  async createToken(input: PersonalTokenInput) {
    const token = await this.perform(() => this.clients.get().tokens.create(input), undefined);
    if (token) await this.loadTokens({ page: 1 });
    return token;
  }
  async revokeToken(id: string) {
    const revoked = await this.perform(() => this.clients.get().tokens.revoke(id), undefined);
    if (revoked === null) return false;
    await this.loadTokens();
    this.notice.set('Token revoked.');
    return true;
  }
  ngOnDestroy() {
    ++this.epoch;
    this.clearAvatar();
  }
}
