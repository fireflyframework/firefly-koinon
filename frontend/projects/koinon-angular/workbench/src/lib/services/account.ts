// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import {
  Injectable,
  OnDestroy,
  EnvironmentInjector,
  computed,
  effect,
  inject,
  signal,
  untracked,
} from '@angular/core';
import type {
  UserProfile,
  ProfileInput,
  PersonalToken,
  PersonalTokenInput,
  TokenScopeOptions,
  Page,
} from '@fireflyframework/koinon-sdk';
import { organizationContextKey } from './organization-directory-context';
import { KoinonClientContext } from './client-context';
import { KoinonFacade } from '../koinon-facade';
import type { AccountOrganization } from './account-organization';
import { KoinonI18n } from '../foundations/i18n';
const ACCOUNT_ERROR = 'Your account could not be updated.';
@Injectable()
export class KoinonAccount implements OnDestroy {
  private readonly clients = inject(KoinonClientContext);
  private readonly f = inject(KoinonFacade);
  private readonly i18n = inject(KoinonI18n);
  private readonly environment = inject(EnvironmentInjector);
  private readonly organization = signal<AccountOrganization | null>(null);
  private organizationKey = '';
  private organizationLoading: Promise<
    import('./corporate-presentation').KoinonCorporatePresentation | null
  > | null = null;
  private destroyed = false;
  readonly organizationName = computed(() => {
    const value = this.currentOrganization()?.presentation();
    return value?.name_source === 'organization' ? (value.display_name ?? '') : null;
  });
  readonly effectiveAvatar = computed(() => {
    const state = this.currentOrganization(),
      presentation = state?.presentation();
    return presentation?.avatar_source === 'organization' ? state!.avatar() : this.avatar();
  });
  private currentOrganization() {
    return this.organizationKey === this.operationKey()
      ? (this.organization()?.state ?? null)
      : null;
  }
  async organizationPresentation() {
    const key = this.operationKey();
    if (key !== this.organizationKey) {
      this.organization()?.destroy();
      this.organization.set(null);
      this.organizationLoading = null;
      this.organizationKey = key;
    }
    if (this.destroyed || !this.f.context()?.subject || !this.f.tenantId()) return null;
    return (this.organizationLoading ??= import('./account-organization')
      .then((module) => {
        if (this.destroyed || key !== this.operationKey()) return null;
        const runtime = module.createAccountOrganization(this.environment, this.f, this.clients);
        this.organization.set(runtime);
        return runtime.state;
      })
      .catch(() => {
        if (key === this.operationKey()) this.organizationLoading = null;
        return null;
      }));
  }
  private epoch = 0;
  private key = '';
  private tokenKey = '';
  private operations: import('./account-operations').AccountOperations | null = null;
  private operationsLoading: Promise<
    import('./account-operations').AccountOperations | null
  > | null = null;
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
    this.tokenKey = this.operationKey();
    effect(() => {
      const key = this.operationKey();
      if (key !== this.tokenKey) {
        this.tokenKey = key;
        this.clearTokenContext();
      }
      untracked(() => {
        void this.organizationPresentation().then((state) => state?.load());
      });
    });
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
    this.clearTokenContext();
    this.clearAvatar();
    this.i18n.apply({ locale: 'en-US', time_zone: 'UTC', response_language: 'en' });
  }
  private clearTokenContext() {
    this.tokens.set({ items: [] });
    this.tokenScopes.set(null);
    this.error.set('');
    this.notice.set('');
    this.pending.set(false);
  }
  private clearAvatar() {
    this.operations?.media.clear();
    this.avatar.set('');
  }
  private operationKey() {
    return this.destroyed ? '' : organizationContextKey(this.f, this.clients);
  }
  private async operationRuntime(tokenScope = false) {
    this.syncIdentity();
    const identity = () => (tokenScope ? this.operationKey() : this.contextKey());
    const key = identity();
    try {
      const runtime = await (this.operationsLoading ??= import('./account-operations').then(
        (module) => {
          if (this.destroyed) return null;
          return (this.operations = module.createAccountOperations(
            this.clients,
            this.f,
            this,
            () => this.operationKey(),
            () => this.contextKey(),
            (value) => this.accept(value),
            this.perform.bind(this),
          ));
        },
      ));
      return !this.destroyed && key === identity() ? runtime : null;
    } catch {
      this.operationsLoading = null;
      if (!this.destroyed && key === identity()) this.error.set(ACCOUNT_ERROR);
      return null;
    }
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
    tokenScope = false,
  ): Promise<T | null> {
    this.syncIdentity();
    const epoch = this.epoch,
      key = tokenScope ? this.operationKey() : this.contextKey();
    const current = () =>
      epoch === this.epoch && key === (tokenScope ? this.operationKey() : this.contextKey());
    this.pending.set(true);
    this.error.set('');
    this.notice.set('');
    const runtime = await this.operationRuntime(tokenScope);
    if (!runtime || !current()) {
      if (current()) this.pending.set(false);
      return null;
    }
    return runtime.run(operation, apply, notice, current);
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
    const media = (await this.operationRuntime())?.media;
    if (profile.avatar_version === this.profile()?.avatar_version) await media?.load(profile);
  }
  async uploadAvatar(file: File) {
    return (await this.operationRuntime())?.media.upload(file) ?? false;
  }
  async removeAvatar() {
    return (await this.operationRuntime())?.media.remove() ?? false;
  }
  async loadTokens(
    filter: Partial<{ page: number; page_size: number; q: string; status: string }> = {},
  ) {
    return (await this.operationRuntime(true))?.tokens.load(filter) ?? null;
  }
  async loadTokenScopes() {
    return (await this.operationRuntime(true))?.tokens.scopes() ?? null;
  }
  async createToken(input: PersonalTokenInput) {
    return (await this.operationRuntime(true))?.tokens.create(input) ?? null;
  }
  async revokeToken(id: string) {
    return (await this.operationRuntime(true))?.tokens.revoke(id) ?? false;
  }
  ngOnDestroy() {
    this.destroyed = true;
    this.organization()?.destroy();
    this.organization.set(null);
    ++this.epoch;
    this.operations?.media.destroy();
    this.avatar.set('');
  }
}
