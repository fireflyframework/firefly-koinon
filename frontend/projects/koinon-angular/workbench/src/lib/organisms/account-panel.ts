// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import {
  Component,
  Input,
  OnInit,
  OnChanges,
  PendingTasks,
  inject,
  signal,
  ChangeDetectionStrategy,
} from '@angular/core';
import { DOCUMENT } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { KoinonAccount } from '../services/account';
import { KoinonFacade } from '../koinon-facade';
import { KoinonI18n, KoinonTextPipe, KoinonDatePipe } from '../foundations/i18n';
import { KoinonButton } from '../atoms/button';
import { KoinonFormField } from '../molecules/form-field';
import { KoinonPagination } from '../molecules/pagination';
import { KoinonAuthorizedApplicationsPanel } from './authorized-applications-panel';
@Component({
  selector: 'ffk-account-panel',
  imports: [
    FormsModule,
    KoinonTextPipe,
    KoinonDatePipe,
    KoinonButton,
    KoinonFormField,
    KoinonPagination,
    KoinonAuthorizedApplicationsPanel,
  ],
  templateUrl: './account-panel.html',
  styleUrl: './account-panel.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonAccountPanel implements OnInit, OnChanges {
  @Input() pageMode = false;
  @Input() initialTab: 'profile' | 'tokens' | 'applications' = 'profile';
  readonly account = inject(KoinonAccount);
  readonly f = inject(KoinonFacade);
  readonly i18n = inject(KoinonI18n);
  private readonly tasks = inject(PendingTasks);
  private readonly document = inject(DOCUMENT);
  readonly tab = signal<'profile' | 'tokens' | 'applications'>('profile');
  readonly initializing = signal(true);
  readonly creating = signal(false);
  readonly secret = signal('');
  readonly copied = signal(false);
  readonly formError = signal('');
  readonly revoking = signal('');
  name = '';
  locale = 'en-US';
  timeZone = 'UTC';
  responseLanguage = 'en';
  tokenName = '';
  expiryDate = '';
  scopeIds: string[] = [];
  workspaceBound = true;
  assetBound = false;
  tokenQuery = '';
  readonly timeZones = [
    ...new Set([
      'UTC',
      Intl.DateTimeFormat().resolvedOptions().timeZone,
      ...Intl.supportedValuesOf('timeZone'),
    ]),
  ];
  ngOnChanges() {
    if (!this.initializing()) this.tasks.run(() => this.showTab(this.initialTab));
  }
  ngOnInit() {
    this.tab.set(this.initialTab);
    this.tasks.run(async () => {
      try {
        await this.account.load();
        this.fillProfile();
        await this.showTab(this.initialTab);
      } finally {
        this.initializing.set(false);
      }
    });
  }
  private fillProfile() {
    const profile = this.account.profile();
    if (profile) {
      this.name = profile.display_name;
      this.locale = profile.locale;
      this.timeZone = profile.time_zone;
      this.responseLanguage = profile.response_language;
    }
  }
  async showTab(tab: 'profile' | 'tokens' | 'applications') {
    this.tab.set(tab);
    this.formError.set('');
    this.secret.set('');
    this.creating.set(false);
    if (tab === 'tokens') {
      await this.account.loadTokens({ page: 1 });
      await this.account.loadTokenScopes();
    }
  }
  async save() {
    this.formError.set('');
    if (!this.name.trim()) {
      this.formError.set('Enter a display name.');
      return;
    }
    if (
      await this.account.save({
        display_name: this.name.trim(),
        locale: this.locale,
        time_zone: this.timeZone,
        response_language: this.responseLanguage,
      })
    )
      this.fillProfile();
  }
  async avatarChanged(event: Event) {
    const input = event.target as HTMLInputElement,
      file = input.files?.[0];
    if (file) await this.account.uploadAvatar(file);
    input.value = '';
  }
  initials() {
    return (this.account.profile()?.display_name || 'Your account')
      .split(/\s/)
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0])
      .join('')
      .toUpperCase();
  }
  beginToken() {
    this.tokenName = '';
    this.scopeIds = [];
    this.workspaceBound = !!this.f.workspaceId();
    this.assetBound = false;
    this.expiryDate = new Date(
      Date.now() +
        Math.max(0, Math.min(30, this.account.tokenScopes()?.max_lifetime_days ?? 30) - 1) *
          86400000,
    )
      .toISOString()
      .slice(0, 10);
    this.creating.set(true);
    this.formError.set('');
    this.secret.set('');
    this.copied.set(false);
  }
  toggleScope(id: string, selected: boolean) {
    if (!selected) {
      this.scopeIds = this.scopeIds.filter((value) => value !== id);
      return;
    }
    const scopes = this.account.tokenScopes()?.items ?? [],
      ids = new Set(this.scopeIds);
    const add = (key: string) => {
      if (ids.has(key)) return;
      ids.add(key);
      for (const dependency of scopes.find((value) => value.id === key)?.dependencies ?? [])
        add(dependency);
    };
    add(id);
    this.scopeIds = [...ids];
  }
  requiredScope(id: string) {
    return this.scopeIds.some(
      (selected) =>
        selected !== id &&
        this.account
          .tokenScopes()
          ?.items.find((scope) => scope.id === selected)
          ?.dependencies.includes(id),
    );
  }
  async createToken() {
    this.formError.set('');
    if (!this.tokenName.trim() || !this.scopeIds.length || !this.expiryDate) {
      this.formError.set('Enter a name, expiry date and at least one permission.');
      return;
    }
    const expiresAt = this.expiryDate + 'T23:59:59Z',
      remaining = new Date(expiresAt).getTime() - Date.now(),
      maximum = this.account.tokenScopes()?.max_lifetime_days ?? 0;
    if (!Number.isFinite(remaining) || remaining <= 0 || remaining > maximum * 86400000) {
      this.formError.set('Choose an expiry date within the allowed lifetime.');
      return;
    }
    const created = await this.account.createToken({
      name: this.tokenName.trim(),
      tenant_id: this.f.tenantId(),
      scopes: this.scopeIds,
      expires_at: expiresAt,
      workspace_ids: this.workspaceBound && this.f.workspaceId() ? [this.f.workspaceId()] : null,
      asset_ids: this.assetBound && this.f.selected() ? [this.f.selected()!.id] : null,
    });
    if (created) {
      this.secret.set(created.token);
      this.creating.set(false);
    }
  }
  async copyToken() {
    try {
      const clipboard = this.document.defaultView?.navigator.clipboard;
      if (!clipboard) throw new Error('Clipboard is unavailable');
      await clipboard.writeText(this.secret());
      this.copied.set(true);
    } catch {
      this.formError.set('Copy was blocked. Select and copy the token manually.');
    }
  }
  clearSecret() {
    this.secret.set('');
    this.copied.set(false);
  }
  async revoke(id: string) {
    if (await this.account.revokeToken(id)) this.revoking.set('');
  }
  selectedAsset() {
    const entry = this.f.selected();
    return entry && ['document', 'dataset'].includes(entry.kind) ? entry : null;
  }
  tenantName(id: string) {
    return (
      this.f.context()?.tenants.find((row) => row.id === id)?.name || this.i18n.text('Organization')
    );
  }
  workspaceName() {
    return (
      this.f.context()?.workspaces.find((row) => row.id === this.f.workspaceId())?.name ||
      'Current workspace'
    );
  }
}
