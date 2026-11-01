// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import {
  ChangeDetectionStrategy,
  Component,
  EventEmitter,
  Input,
  Output,
  computed,
  effect,
  inject,
  untracked,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import {
  KoinonButton,
  KoinonDatePipe,
  KoinonPagination,
  KoinonTextPipe,
} from '@fireflyframework/koinon-angular';
import { KoinonCommunicationsSession } from '@fireflyframework/koinon-angular/communications/runtime';
import type {
  EmailInvitation,
  EmailInvitationPage,
  EmailInvitationStatus,
  RecipientProviderPage,
} from '@fireflyframework/koinon-sdk';
import type {
  CommunicationReadiness,
  CommunicationRole,
  EmailInvitationDraft,
  InvitationEmailPreview,
  InvitationQueuedView,
  RecipientPage,
} from '@fireflyframework/koinon-angular/communications';
import { invitationActionReason } from './action-reasons';
import { KoinonInvitationComposer } from './invitation-composer';
@Component({
  selector: 'ffk-email-invitations',
  imports: [
    FormsModule,
    KoinonButton,
    KoinonDatePipe,
    KoinonPagination,
    KoinonTextPipe,
    KoinonInvitationComposer,
  ],
  providers: [KoinonCommunicationsSession],
  templateUrl: './email-invitations.html',
  styleUrl: './email-invitations.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonEmailInvitations {
  readonly actionReason = invitationActionReason;
  readonly session = inject(KoinonCommunicationsSession);
  @Input() initialMode: 'list' | 'compose' = 'list';
  @Input() roles: readonly CommunicationRole[] = [];
  @Input() brandBase = '/assets/brand';
  @Output() closed = new EventEmitter<void>();
  readonly readiness = this.session.state<CommunicationReadiness | null>(null);
  async loadReadiness() {
    await this.session.run(
      'readiness',
      (signal) =>
        this.session.api!.administration.capabilities(this.session.facade.tenantId(), { signal }),
      (value) => this.readiness.set(value),
    );
  }
  readonly mode = this.session.state<'list' | 'compose'>('list');
  readonly recipients = this.session.state<RecipientPage | null>(null);
  readonly preview = this.session.state<InvitationEmailPreview | null>(null);
  readonly queued = this.session.state<InvitationQueuedView | null>(null);
  readonly providers = this.session.state<RecipientProviderPage | null>(null);
  readonly invitations = this.session.state<EmailInvitationPage | null>(null);
  readonly confirming = this.session.state<{ id: string; action: 'revoke' | 'resend' } | null>(
    null,
  );
  readonly providerId = this.session.state('');
  status: EmailInvitationStatus = 'pending';
  private operationKey = '';
  private draftKey = '';
  private activePage = 1;
  readonly organizationAdmin = computed(
    () =>
      this.session.facade
        .context()
        ?.memberships.some(
          (row) =>
            row.tenant_id === this.session.facade.tenantId() &&
            row.active &&
            row.role === 'admin' &&
            !row.workspace_id,
        ) ?? false,
  );
  readonly scopes = computed(() => {
    const f = this.session.facade;
    return (f.context()?.workspaces ?? [])
      .filter(
        (row) =>
          row.tenant_id === f.tenantId() &&
          row.kind === 'workspace' &&
          row.status !== 'archived' &&
          (this.organizationAdmin() ||
            f
              .context()
              ?.memberships.some(
                (grant) =>
                  grant.active &&
                  grant.tenant_id === f.tenantId() &&
                  grant.role === 'admin' &&
                  grant.workspace_id === row.id,
              )),
      )
      .map((row) => ({ id: row.id, name: row.name }));
  });
  readonly organizationName = computed(
    () =>
      this.session.facade
        .context()
        ?.tenants.find((row) => row.id === this.session.facade.tenantId())?.name ?? '',
  );
  readonly contextKey = computed(() => this.session.key() + ':' + this.providerId());
  constructor() {
    effect(() => {
      this.session.key();
      untracked(() => {
        this.mode.set(this.initialMode);
        this.recipients.set(null);
        this.preview.set(null);
        this.queued.set(null);
        this.invitations.set(null);
        this.providers.set(null);
        this.providerId.set('');
        this.confirming.set(null);
        this.operationKey = '';
        this.draftKey = '';
        this.readiness.set(null);
        void this.loadReadiness();
        void this.loadProviders();
        void this.load();
      });
    });
  }
  compose() {
    this.queued.set(null);
    this.preview.set(null);
    this.recipients.set(null);
    this.mode.set('compose');
  }
  async loadProviders(page = 1) {
    await this.session.run(
      'providers',
      (signal) =>
        this.session.api!.recipients.providers(
          this.session.facade.tenantId(),
          {
            page,
            page_size: 20,
            ...(!this.organizationAdmin() && this.session.facade.workspaceId()
              ? { workspace_id: this.session.facade.workspaceId() }
              : {}),
          },
          { signal },
        ),
      (value) => {
        this.providers.set(value);
        if (value.total === 1 && value.items[0]) this.providerId.set(value.items[0].id);
      },
    );
  }
  providerChanged(value: string) {
    this.providerId.set(value);
    this.recipients.set(null);
    this.preview.set(null);
  }
  async search(query: { q: string; after?: string }) {
    this.preview.set(null);
    const provider = this.providerId();
    if (!provider) return;
    await this.session.run(
      'recipients',
      (signal) =>
        this.session.api!.recipients.list(
          this.session.facade.tenantId(),
          {
            q: query.q,
            provider_id: this.providerId(),
            limit: 20,
            ...(query.after ? { after: query.after } : {}),
            ...(!this.organizationAdmin() && this.session.facade.workspaceId()
              ? { workspace_id: this.session.facade.workspaceId() }
              : {}),
          },
          { signal },
        ),
      (value) => {
        if (provider === this.providerId())
          this.recipients.set({ items: value.items, next_cursor: value.next_cursor });
      },
    );
  }
  async makePreview(draft: EmailInvitationDraft) {
    this.preview.set(null);
    if (this.draftKey !== JSON.stringify(draft)) this.operationKey = '';
    this.draftKey = JSON.stringify(draft);
    const context = this.contextKey();
    await this.session.run(
      'preview',
      (signal) =>
        this.session.api!.emailInvitations.preview(this.session.facade.tenantId(), draft, {
          signal,
        }),
      (value) => {
        if (context === this.contextKey() && this.draftKey === JSON.stringify(draft))
          this.preview.set({ ...value, draft: { ...draft } });
      },
    );
  }
  async send(draft: EmailInvitationDraft) {
    if (
      this.readiness()?.state !== 'ready' ||
      this.session.pending() ||
      !this.preview() ||
      this.draftKey !== JSON.stringify(draft)
    )
      return;
    if (!this.operationKey) this.operationKey = crypto.randomUUID();
    await this.session.run(
      'send',
      (signal) =>
        this.session.api!.emailInvitations.create(this.session.facade.tenantId(), draft, {
          signal,
          headers: { 'Idempotency-Key': this.operationKey },
        }),
      (value) => {
        this.queued.set({
          invitation_id: value.id,
          recipient_display_name: value.recipient_display_name,
          recipient_email: value.recipient_email,
          delivery_status: value.delivery.status,
        });
        this.operationKey = '';
      },
    );
  }
  async load(page = 1) {
    this.activePage = page;
    await this.session.run(
      'invitations',
      (signal) =>
        this.session.api!.emailInvitations.list(
          this.session.facade.tenantId(),
          {
            status: this.status,
            page,
            page_size: 25,
            ...(!this.organizationAdmin() && this.session.facade.workspaceId()
              ? { workspace_id: this.session.facade.workspaceId() }
              : {}),
          },
          { signal },
        ),
      (value) => this.invitations.set(value),
    );
  }
  async list() {
    this.mode.set('list');
    await this.load();
  }
  async act(invitation: EmailInvitation, action: 'revoke' | 'resend') {
    if (
      this.session.pending() ||
      !invitation.allowed_actions.includes(action) ||
      this.confirming()?.id !== invitation.id ||
      this.confirming()?.action !== action
    )
      return;
    const result = await this.session.run(
      'mutation',
      async (signal) => {
        if (action === 'revoke')
          await this.session.api!.emailInvitations.revoke(
            this.session.facade.tenantId(),
            invitation.id,
            { signal },
          );
        else
          await this.session.api!.emailInvitations.resend(
            this.session.facade.tenantId(),
            invitation.id,
            { signal },
          );
        return true;
      },
      () => this.confirming.set(null),
    );
    if (result) await this.load(this.activePage);
  }
}
