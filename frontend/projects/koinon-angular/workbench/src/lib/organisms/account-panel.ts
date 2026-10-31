// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import {
  Component,
  Input,
  OnInit,
  OnChanges,
  PendingTasks,
  inject,
  signal,
  computed,
  effect,
  untracked,
  ChangeDetectionStrategy,
} from '@angular/core';
import { DOCUMENT } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { KoinonOrganizationInformation } from './organization-information';
import { KoinonPhotoDraft } from '../services/photo-draft';
import { KoinonClientContext } from '../services/client-context';
import { KoinonAccount } from '../services/account';
import { KoinonFacade } from '../koinon-facade';
import { KoinonI18n, KoinonTextPipe, KoinonDatePipe } from '../foundations/i18n';
import { KoinonButton } from '../atoms/button';
import { KoinonFormField } from '../molecules/form-field';
import { KoinonPagination } from '../molecules/pagination';
import { KoinonAuthorizedApplicationsPanel } from './authorized-applications-panel';
import {
  availableTokenScopes,
  tokenDependencies,
  tokenScopeGroup,
  type TokenScopeGroup,
} from '../services/token-permissions';
@Component({
  selector: 'ffk-account-panel',
  imports: [
    FormsModule,
    KoinonOrganizationInformation,
    KoinonTextPipe,
    KoinonDatePipe,
    KoinonButton,
    KoinonFormField,
    KoinonPagination,
    KoinonAuthorizedApplicationsPanel,
  ],
  providers: [KoinonPhotoDraft],
  templateUrl: './account-panel.html',
  styleUrl: './account-panel.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonAccountPanel implements OnInit, OnChanges {
  @Input() pageMode = false;
  @Input() initialTab: 'profile' | 'tokens' | 'applications' = 'profile';
  readonly account = inject(KoinonAccount);
  readonly photo = inject(KoinonPhotoDraft);
  readonly f = inject(KoinonFacade);
  readonly i18n = inject(KoinonI18n);
  private readonly tasks = inject(PendingTasks);
  private readonly document = inject(DOCUMENT);
  private readonly clients = inject(KoinonClientContext, { optional: true });
  readonly tab = signal<'profile' | 'tokens' | 'applications'>('profile');
  readonly initializing = signal(true);
  readonly creating = signal(false);
  private readonly issuedSecret = signal('');
  private secretIdentity = '';
  readonly secret = computed(() => {
    const value = this.issuedSecret();
    return this.secretIdentity === this.tokenIdentity() ? value : '';
  });
  readonly copied = signal(false);
  readonly formError = signal('');
  readonly revoking = signal('');
  readonly scopeNotice = signal('');
  readonly scopeGroups: { id: TokenScopeGroup; name: string }[] = [
    { id: 'read', name: 'Read & ask' },
    { id: 'write', name: 'Create & maintain knowledge' },
    { id: 'organization', name: 'Manage organization' },
    { id: 'profile', name: 'Your profile' },
  ];
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
  private tokenContext = { subject: '', tenant: '', workspace: '', asset: '' };
  readonly timeZones = [
    ...new Set([
      'UTC',
      Intl.DateTimeFormat().resolvedOptions().timeZone,
      ...Intl.supportedValuesOf('timeZone'),
    ]),
  ];
  private tokenIdentity() {
    return JSON.stringify([
      this.f.context()?.subject,
      this.f.tenantId(),
      this.clients?.revision(),
      this.workspaceBound ? this.f.workspaceId() : null,
      this.assetBound ? this.selectedAsset()?.id : null,
      this.availableScopes()
        .map((scope) => scope.id)
        .sort(),
    ]);
  }
  constructor() {
    effect(() => {
      const key = this.tokenIdentity();
      untracked(() => {
        if (this.secretIdentity && key !== this.secretIdentity) {
          this.issuedSecret.set('');
          this.secretIdentity = '';
          this.copied.set(false);
        }
      });
    });
  }
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
    this.issuedSecret.set('');
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
  languageName(value: string) {
    if (value === 'auto') return this.i18n.text('Automatic');
    try {
      return (
        new Intl.DisplayNames([this.i18n.preferences().locale], { type: 'language' }).of(value) ||
        this.i18n.text('Other language')
      );
    } catch {
      return this.i18n.text('Other language');
    }
  }
  async avatarChanged(event: Event) {
    const input = event.target as HTMLInputElement,
      file = input.files?.[0];
    if (file) this.photo.stageAvatar(file);
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
    this.tokenContext = {
      subject: this.f.context()?.subject ?? '',
      tenant: this.f.tenantId(),
      workspace: this.f.workspaceId(),
      asset: this.selectedAsset()?.id ?? '',
    };
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
    this.issuedSecret.set('');
    this.copied.set(false);
    this.scopeNotice.set('');
  }
  availableScopes() {
    return availableTokenScopes(
      this.account.tokenScopes()?.items ?? [],
      this.f.tenantPermissions(),
      this.f.permissions(),
    );
  }
  groupScopes(group: TokenScopeGroup) {
    return this.availableScopes().filter((scope) => tokenScopeGroup(scope.id) === group);
  }
  scopeDisabled(id: string) {
    return (
      this.requiredScope(id) ||
      ((this.workspaceBound || this.assetBound) && tokenScopeGroup(id) === 'organization')
    );
  }
  limitChanged(kind: 'workspace' | 'asset', selected: boolean) {
    if (kind === 'workspace') this.workspaceBound = selected;
    else this.assetBound = selected;
    if (selected) {
      const retained = this.scopeIds.filter((id) => tokenScopeGroup(id) !== 'organization');
      if (retained.length !== this.scopeIds.length)
        this.scopeNotice.set(
          'Organization permissions were removed because this token is limited to knowledge resources.',
        );
      this.scopeIds = retained;
    }
  }
  preset(kind: 'read' | 'write' | 'organization') {
    const scopes = this.availableScopes();
    if (kind === 'organization') {
      if (!this.groupScopes('organization').length) return;
      this.workspaceBound = false;
      this.assetBound = false;
      this.scopeNotice.set(
        'All available knowledge and organization permissions are selected. This token has organization scope.',
      );
    } else this.scopeNotice.set('Review the selected permissions before creating this token.');
    this.scopeIds = tokenDependencies(
      scopes
        .filter((scope) => {
          const group = tokenScopeGroup(scope.id);
          return (
            group === 'read' ||
            (kind !== 'read' && group === 'write') ||
            (kind === 'organization' && group === 'organization')
          );
        })
        .map((scope) => scope.id),
      scopes,
    );
  }
  toggleScope(id: string, selected: boolean) {
    if (!selected) {
      this.scopeIds = this.scopeIds.filter((value) => value !== id);
      return;
    }
    if (this.scopeDisabled(id)) return;
    this.scopeIds = tokenDependencies([...this.scopeIds, id], this.availableScopes());
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
    if (
      this.tokenContext.subject !== (this.f.context()?.subject ?? '') ||
      this.tokenContext.tenant !== this.f.tenantId()
    ) {
      this.formError.set(
        'Your access context changed. Cancel and start a new token to review its access.',
      );
      return;
    }
    if (
      this.workspaceBound &&
      (!this.tokenContext.workspace || this.tokenContext.workspace !== this.f.workspaceId())
    ) {
      this.formError.set(
        'The selected workspace changed. Cancel and start a new token to review its limits.',
      );
      return;
    }
    if (
      this.assetBound &&
      (!this.tokenContext.asset || this.tokenContext.asset !== this.selectedAsset()?.id)
    ) {
      this.formError.set(
        'The selected file changed. Cancel and start a new token to review its limits.',
      );
      return;
    }
    const available = new Set(this.availableScopes().map((scope) => scope.id));
    if (this.scopeIds.some((id) => !available.has(id))) {
      this.scopeIds = tokenDependencies(
        this.scopeIds.filter((id) => available.has(id)),
        this.availableScopes(),
      );
      this.formError.set(
        'Your available permissions changed. Review the remaining permissions before creating this token.',
      );
      return;
    }
    if (!this.tokenName.trim() || !this.scopeIds.length || !this.expiryDate) {
      this.formError.set('Enter a name, expiry date and at least one permission.');
      return;
    }
    const expiresAt = this.expiryDate + 'T23:59:59Z',
      remaining = new Date(expiresAt).getTime() - Date.now(),
      maximum = this.account.tokenScopes()?.max_lifetime_days ?? 0;
    if (!Number.isFinite(remaining) || remaining < 60000 || remaining > maximum * 86400000) {
      this.formError.set('Choose an expiry date within the allowed lifetime.');
      return;
    }
    if (
      (this.workspaceBound || this.assetBound) &&
      this.scopeIds.some((id) => tokenScopeGroup(id) === 'organization')
    ) {
      this.formError.set(
        'Organization permissions require organization scope. Remove the workspace and file limits.',
      );
      return;
    }
    const requestIdentity = this.tokenIdentity();
    const created = await this.account.createToken({
      name: this.tokenName.trim(),
      tenant_id: this.f.tenantId(),
      scopes: this.scopeIds,
      expires_at: expiresAt,
      workspace_ids: this.workspaceBound ? [this.tokenContext.workspace] : null,
      asset_ids: this.assetBound ? [this.tokenContext.asset] : null,
    });
    if (this.tokenIdentity() !== requestIdentity) {
      this.issuedSecret.set('');
      this.creating.set(false);
      this.formError.set(
        'Your access context changed. Cancel and start a new token to review its access.',
      );
      return;
    }
    if (created) {
      this.secretIdentity = requestIdentity;
      this.issuedSecret.set(created.token);
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
    this.issuedSecret.set('');
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
