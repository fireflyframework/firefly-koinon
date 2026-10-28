// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import {
  ChangeDetectionStrategy,
  Component,
  EventEmitter,
  Input,
  OnChanges,
  OnDestroy,
  Output,
  PendingTasks,
  inject,
  signal,
} from '@angular/core';
import {
  KoinonButton,
  KoinonTextPipe,
  KoinonDatePipe,
  KoinonFacade,
  KoinonClientContext,
  KoinonSkeleton,
} from '@fireflyframework/koinon-angular';
import type { InvitationPreview, Membership } from '@fireflyframework/koinon-sdk';
import { ACCESS_ROLES } from './people-access';
@Component({
  selector: 'ffk-invitation-acceptance',
  imports: [KoinonButton, KoinonTextPipe, KoinonDatePipe, KoinonSkeleton],
  template: `<section aria-labelledby="invitation-heading">
    <h1 id="invitation-heading">{{ 'Join an organization' | ffkText }}</h1>
    @if (pending()) {
      <ffk-skeleton width="70%" height="3px" [label]="'Working' | ffkText" />
    }
    @if (error()) {
      <p role="alert">{{ error() | ffkText }}</p>
      <div class="actions">
        <ffk-button (click)="load()">{{ 'Try again' | ffkText }}</ffk-button>
        <ffk-button variant="quiet" (click)="dismiss()">{{
          'Close invitation' | ffkText
        }}</ffk-button>
      </div>
    }
    @if (preview(); as invitation) {
      <p>
        {{ 'You have been invited to join' | ffkText }} <strong>{{ invitation.tenant_name }}</strong
        >.
      </p>
      <dl>
        <dt>{{ 'Access' | ffkText }}</dt>
        <dd>{{ invitation.workspace_name || ('Entire organization' | ffkText) }}</dd>
        <dt>{{ 'Role' | ffkText }}</dt>
        <dd>{{ roleLabel(invitation.role) | ffkText }}</dd>
        <dt>{{ 'Expires' | ffkText }}</dt>
        <dd>{{ invitation.expires_at | ffkDate: undefined : 'datetime' }}</dd>
      </dl>
      <p>{{ roleDescription(invitation.role) | ffkText }}</p>
      <p>
        {{
          'Accept only if you recognize this organization and expected this invitation.' | ffkText
        }}
      </p>
      <div class="actions">
        <ffk-button variant="primary" [loading]="pending()" (click)="accept()">{{
          'Accept invitation' | ffkText
        }}</ffk-button
        ><ffk-button [disabled]="pending()" (click)="dismiss()">{{
          'Not now' | ffkText
        }}</ffk-button>
      </div>
    } @else if (!pending() && !error()) {
      <p>{{ 'Open the private invitation link shared by your administrator.' | ffkText }}</p>
    }
  </section>`,
  styles: `
    :host {
      display: block;
      width: 100%;
      min-width: 0;
      font-family: var(--ffk-font, 'Manrope', sans-serif);
    }
    section {
      max-width: 580px;
      margin: auto;
      padding: 32px;
      border: 1px solid var(--ui-line);
      border-radius: 14px;
      background: var(--ui-surface);
      color: var(--ui-text);
    }
    h1 {
      font-size: 24px;
      line-height: 1.5;
      font-weight: 500;
      margin: 0 0 20px;
    }
    p {
      font-size: 13px;
      line-height: 1.9;
    }
    dl {
      display: grid;
      grid-template-columns: 90px minmax(0, 1fr);
      gap: 16px;
      font-size: 13px;
      line-height: 1.7;
      margin: 28px 0;
    }
    dt {
      color: var(--ui-muted);
    }
    dd {
      margin: 0;
      overflow-wrap: anywhere;
    }
    .actions {
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
      margin-top: 28px;
    }
    @media (max-width: 480px) {
      section {
        padding: 22px;
      }
      .actions ffk-button {
        flex: 1;
      }
    }
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonInvitationAcceptance implements OnChanges, OnDestroy {
  @Input() token = '';
  @Input() actions?: { accepted: (membership: Membership) => void; dismissed: () => void };
  @Output() accepted = new EventEmitter<Membership>();
  @Output() dismissed = new EventEmitter<void>();
  private readonly clients = inject(KoinonClientContext);
  private readonly facade = inject(KoinonFacade);
  private readonly tasks = inject(PendingTasks);
  private epoch = 0;
  readonly preview = signal<InvitationPreview | null>(null);
  readonly pending = signal(false);
  readonly error = signal('');
  ngOnChanges() {
    this.tasks.run(() => this.load());
  }
  roleLabel(role: string) {
    return ACCESS_ROLES.find((value) => value.id === role)?.label ?? role;
  }
  roleDescription(role: string) {
    return ACCESS_ROLES.find((value) => value.id === role)?.description ?? '';
  }
  private fail(error: unknown) {
    this.preview.set(null);
    if (error instanceof Error && 'status' in error && error.status === 401) {
      this.facade.authRequired.set(true);
      this.error.set('Sign in to review this invitation.');
    } else this.error.set('This invitation is unavailable. Ask an administrator for a new link.');
  }
  async load() {
    const epoch = ++this.epoch;
    this.preview.set(null);
    this.error.set('');
    if (!this.token) {
      this.pending.set(false);
      return;
    }
    this.pending.set(true);
    try {
      const value = await this.clients.get().invitations.inspect(this.token);
      if (epoch === this.epoch) this.preview.set(value);
    } catch (error) {
      if (epoch === this.epoch) this.fail(error);
    } finally {
      if (epoch === this.epoch) this.pending.set(false);
    }
  }
  async accept() {
    if (this.pending() || !this.preview()) return;
    const epoch = this.epoch;
    this.pending.set(true);
    this.error.set('');
    try {
      const value = await this.clients.get().invitations.redeem(this.token);
      if (epoch === this.epoch) {
        this.preview.set(null);
        this.accepted.emit(value);
        this.actions?.accepted(value);
      }
    } catch (error) {
      if (epoch === this.epoch) this.fail(error);
    } finally {
      if (epoch === this.epoch) this.pending.set(false);
    }
  }
  dismiss() {
    this.dismissed.emit();
    this.actions?.dismissed();
  }
  ngOnDestroy() {
    ++this.epoch;
    this.preview.set(null);
  }
}
