// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { A11yModule } from '@angular/cdk/a11y';
import { DOCUMENT } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  OnDestroy,
  PendingTasks,
  effect,
  inject,
  signal,
  untracked,
} from '@angular/core';
import {
  KoinonFacade,
  KoinonI18n,
  KoinonTextPipe,
  registerKoinonSpanish,
} from '@fireflyframework/koinon-angular/workbench/core';
import { KoinonSourceAccounts } from './source-accounts';
import { SOURCE_SPANISH } from './source-spanish';
import { connectionStatus, providerName } from './source-presentation';
import type { SourceAuthorization, SourceProvider } from './source-contracts';
registerKoinonSpanish(SOURCE_SPANISH);
@Component({
  selector: 'ffk-connected-sources',
  imports: [KoinonTextPipe, A11yModule],
  providers: [KoinonSourceAccounts],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: './source-controls.scss',
  template: `<section
    [attr.aria-label]="'Connected sources' | ffkText"
    [attr.aria-busy]="state.loading()"
  >
    <p>
      {{
        'Connect an account to import knowledge or verify your access to imported sources. Koinon does not change your original files.'
          | ffkText
      }}
    </p>
    @if (!f.authRequired()) {
      @if (state.capabilities(); as capability) {
        <div class="actions" [attr.aria-label]="'Connect account' | ffkText">
          @for (provider of capability.providers; track provider.provider) {
            @if (provider.consent_available) {
              <button
                type="button"
                [disabled]="state.pending() || !!authorization()"
                (click)="consentProvider.set(provider.provider)"
              >
                {{ 'Connect account' | ffkText }}: {{ provider.display_name }}
              </button>
            } @else {
              <p>
                <strong>{{ provider.display_name }}</strong
                ><br />{{ 'This provider is not available in this organization.' | ffkText }}
              </p>
            }
          }
        </div>
        @if (!hasProvider()) {
          <p>{{ 'Contact your administrator to enable a provider.' | ffkText }}</p>
        }
      }
      @if (consentProvider(); as provider) {
        <section class="confirmation" [attr.aria-label]="'Connect account' | ffkText">
          <p>{{ consentExplanation(provider) }}</p>
          <div class="actions">
            <button type="button" (click)="consentProvider.set(null)">
              {{ 'Cancel' | ffkText }}</button
            ><button type="button" class="primary" (click)="connect(provider)">
              {{ 'Continue' | ffkText }}
            </button>
          </div>
        </section>
      }
      @if (authorization() || consentPending()) {
        <p role="status">{{ 'Waiting for account connection…' | ffkText }}</p>
        <button type="button" (click)="cancelConsent()">{{ 'Cancel' | ffkText }}</button>
      }
      @if (consentError()) {
        <p role="alert">{{ consentError() | ffkText }}</p>
        @if (authorization()) {
          <button type="button" (click)="openConsent()">{{ 'Open sign-in' | ffkText }}</button>
        }
      }
      @if (consentNotice()) {
        <p role="status">{{ consentNotice() | ffkText }}</p>
      }
      <div class="source-rows">
        @for (account of state.page().items; track account.id; let index = $index) {
          <div class="source-row">
            <div>
              <strong
                >{{ account.display_name || providerName(account.provider) }}
                @if (!account.display_name) {
                  — {{ 'Connected account' | ffkText }} {{ index + 1 }}
                }</strong
              ><small
                >{{ providerName(account.provider) }} ·
                {{ connectionStatus(account.status) | ffkText }}</small
              >
              @if (account.display_address && account.display_address_verified) {
                <small>{{ account.display_address }}</small>
              } @else if (!account.display_name) {
                <small>{{ 'Account identity is unavailable.' | ffkText }}</small>
              }
            </div>
            @if (account.status !== 'connected' && providerAvailable(account.provider)) {
              <div>
                <p>
                  {{
                    'Continue with the same provider account to restore this connection.' | ffkText
                  }}
                </p>
                <button
                  type="button"
                  [disabled]="state.pending() || !!authorization()"
                  (click)="consentProvider.set(account.provider)"
                >
                  {{ 'Reconnect account' | ffkText }}
                </button>
              </div>
            }
            @if (account.status !== 'disconnected') {
              <button
                type="button"
                [disabled]="state.pending()"
                (click)="confirm(account.id, $event)"
              >
                {{ 'Disconnect account' | ffkText }}
              </button>
            }
          </div>
        } @empty {
          @if (!state.loading() && !state.error()) {
            <p>
              {{
                (state.page().next_cursor
                  ? 'No matching items on this page.'
                  : 'No matching items.'
                ) | ffkText
              }}
            </p>
          }
        }
      </div>
      @if (state.page().next_cursor) {
        <button type="button" [disabled]="state.loading()" (click)="more()">
          {{ (state.loading() ? 'Loading more…' : 'Continue browsing') | ffkText }}
        </button>
      }
      @if (confirming() && state.page().items.length) {
        <section
          class="confirmation"
          role="dialog"
          aria-modal="true"
          [attr.aria-label]="'Disconnect this account?' | ffkText"
          cdkTrapFocus
          [cdkTrapFocusAutoCapture]="true"
          (keydown.escape)="cancel($event)"
        >
          <h2>{{ 'Disconnect this account?' | ffkText }}</h2>
          <p>
            {{
              'Synchronization using this account will stop. Imported knowledge will still require current source access. Original files will not change.'
                | ffkText
            }}
          </p>
          <div class="actions">
            <button type="button" cdkFocusInitial (click)="cancel()">
              {{ 'Keep connected' | ffkText }}</button
            ><button type="button" [disabled]="state.pending()" (click)="disconnect()">
              {{ 'Disconnect account' | ffkText }}
            </button>
          </div>
        </section>
      }
    }
    @if (state.loading()) {
      <p role="status">{{ 'Loading accounts…' | ffkText }}</p>
    }
    @if (state.error()) {
      <p role="alert">{{ state.error() | ffkText }}</p>
      <button type="button" (click)="reload()">{{ 'Try again' | ffkText }}</button>
    }
    @if (state.notice()) {
      <p role="status">{{ state.notice() | ffkText }}</p>
    }
  </section>`,
})
export class KoinonConnectedSources implements OnDestroy {
  readonly state = inject(KoinonSourceAccounts);
  readonly f = inject(KoinonFacade);
  private readonly i18n = inject(KoinonI18n);
  readonly consentProvider = signal<SourceProvider | null>(null);
  private readonly tasks = inject(PendingTasks);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  readonly confirming = signal('');
  readonly providerName = providerName;
  readonly connectionStatus = connectionStatus;
  private trigger?: HTMLElement;
  private readonly window = inject(DOCUMENT).defaultView;
  private popup: Window | null = null;
  private consentGeneration = 0;
  private alive = true;
  readonly consentPending = signal(false);
  private interval?: ReturnType<typeof setInterval>;
  private consentIdentity = '';
  private consentContext: ReturnType<KoinonFacade['context']> = null;
  readonly authorization = signal<SourceAuthorization | null>(null);
  readonly consentError = signal('');
  readonly consentNotice = signal('');
  constructor() {
    effect(() => {
      this.state.identity();
      this.f.context();
      this.confirming.set('');
      this.consentProvider.set(null);
      this.trigger = undefined;
      this.closeConsent();
      this.consentError.set('');
      this.consentNotice.set('');
      if (!this.f.authRequired()) untracked(() => this.reload());
    });
  }
  reload() {
    this.tasks.run(() => Promise.all([this.state.load(), this.state.loadCapabilities()]));
  }
  more() {
    this.tasks.run(() => this.state.load(true));
  }
  confirm(id: string, event: Event) {
    this.trigger = event.currentTarget as HTMLElement;
    this.confirming.set(id);
  }
  cancel(event?: Event) {
    event?.preventDefault();
    event?.stopPropagation();
    this.confirming.set('');
    this.trigger?.focus();
  }
  disconnect() {
    this.tasks.run(async () => {
      if (await this.state.disconnect(this.confirming())) {
        this.confirming.set('');
        this.host.nativeElement.querySelector<HTMLElement>('button')?.focus();
      }
    });
  }
  hasProvider() {
    return this.state.capabilities()?.providers.some((row) => row.consent_available);
  }
  consentExplanation(provider: SourceProvider) {
    return this.i18n
      .text('Continue to {provider} to choose your account and allow read access.')
      .replace('{provider}', providerName(provider));
  }
  providerAvailable(provider: SourceProvider) {
    return (
      this.state
        .capabilities()
        ?.providers.some((row) => row.provider === provider && row.consent_available) ?? false
    );
  }
  connect(provider: SourceProvider) {
    if (this.authorization() || this.state.pending()) return;
    const generation = ++this.consentGeneration;
    this.consentPending.set(true);
    this.consentProvider.set(null);
    this.consentError.set('');
    this.consentNotice.set('');
    const popup = this.window?.open('about:blank', '_blank', 'popup,width=620,height=740') ?? null;
    if (popup) popup.opener = null;
    this.popup = popup;
    this.consentIdentity = this.state.identity();
    this.consentContext = this.f.context();
    this.tasks.run(async () => {
      const authorization = await this.state.begin(provider);
      if (!this.alive || generation !== this.consentGeneration || !authorization) {
        popup?.close();
        if (generation === this.consentGeneration) this.consentPending.set(false);
        return;
      }
      this.consentPending.set(false);
      this.authorization.set(authorization);
      this.navigateConsent();
    });
  }
  openConsent() {
    this.popup = this.window?.open('about:blank', '_blank', 'popup,width=620,height=740') ?? null;
    if (this.popup) this.popup.opener = null;
    this.navigateConsent();
  }
  private navigateConsent() {
    const authorization = this.authorization();
    if (!authorization) return;
    try {
      const callback = new URL(authorization.callback_uri),
        target = new URL(authorization.authorization_url);
      if (
        callback.origin !== this.window?.location.origin ||
        !['https:', 'http:'].includes(callback.protocol) ||
        !['https:', 'http:'].includes(target.protocol) ||
        !target.searchParams.get('state') ||
        !Number.isFinite(Date.parse(authorization.expires_at)) ||
        Date.parse(authorization.expires_at) <= Date.now()
      )
        throw Error('Invalid consent callback');
      if (!this.popup) {
        this.consentError.set('Your browser blocked the sign-in window. Open sign-in to continue.');
        return;
      }
      this.consentError.set('');
      this.popup.location.replace(target.href);
      if (this.interval) clearInterval(this.interval);
      this.interval = setInterval(() => this.observeConsent(), 400);
    } catch {
      this.closeConsent();
      this.consentError.set(
        'Account sign-in is not configured for this browser. Contact your administrator.',
      );
    }
  }
  private observeConsent() {
    const authorization = this.authorization();
    if (
      !authorization ||
      this.state.identity() !== this.consentIdentity ||
      this.f.context() !== this.consentContext
    ) {
      this.closeConsent();
      return;
    }
    if (Date.parse(authorization.expires_at) <= Date.now()) {
      this.closeConsent();
      this.consentError.set('Account connection expired. Try again.');
      return;
    }
    if (this.popup?.closed) {
      this.cancelConsent();
      return;
    }
    try {
      if (!this.popup) return;
      const callback = new URL(authorization.callback_uri),
        url = new URL(this.popup.location.href);
      if (url.origin !== callback.origin || url.pathname !== callback.pathname) return;
      const state = url.searchParams.get('state'),
        code = url.searchParams.get('code');
      const expected = new URL(authorization.authorization_url).searchParams.get('state');
      this.popup.history.replaceState(null, '', callback.pathname);
      this.closeConsent();
      if (url.searchParams.has('error')) {
        this.consentNotice.set('Account connection was cancelled. No synchronization was created.');
        return;
      }
      if (!state || !code || state !== expected) {
        this.consentError.set('Account connection could not be verified. Try again.');
        return;
      }
      this.tasks.run(() => this.state.complete(authorization, state, code));
    } catch {
      /* The provider owns the popup until it returns to the registered callback. */
    }
  }
  private closeConsent() {
    ++this.consentGeneration;
    this.consentPending.set(false);
    if (this.interval) clearInterval(this.interval);
    this.interval = undefined;
    this.popup?.close();
    this.popup = null;
    this.authorization.set(null);
  }
  cancelConsent() {
    this.closeConsent();
    this.consentError.set('');
    this.consentNotice.set('Account connection was cancelled. No synchronization was created.');
  }
  ngOnDestroy() {
    this.alive = false;
    this.closeConsent();
  }
}
