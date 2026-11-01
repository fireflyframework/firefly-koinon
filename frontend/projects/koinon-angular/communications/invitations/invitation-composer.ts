// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import {
  ChangeDetectionStrategy,
  Component,
  EventEmitter,
  Input,
  OnChanges,
  Output,
  SimpleChanges,
  signal,
  afterNextRender,
  inject,
  Injector,
  ElementRef,
  viewChild,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import {
  KoinonButton,
  KoinonIcon,
  KoinonSearchField,
  KoinonSkeleton,
  KoinonTextPipe,
} from '@fireflyframework/koinon-angular';
import type {
  CommunicationRole,
  CommunicationScope,
  DirectoryRecipientView,
  EmailInvitationDraft,
  InvitationEmailPreview,
  InvitationQueuedView,
  RecipientPage,
} from '@fireflyframework/koinon-angular/communications';

import { registerKoinonSpanish } from '@fireflyframework/koinon-angular/workbench';
import { INVITATION_SPANISH } from './spanish';
import { KoinonEmailPreview } from '@fireflyframework/koinon-angular/communications/email-preview';
registerKoinonSpanish(INVITATION_SPANISH);

@Component({
  selector: 'ffk-invitation-composer',
  imports: [
    KoinonEmailPreview,
    FormsModule,
    KoinonButton,
    KoinonIcon,
    KoinonSearchField,
    KoinonSkeleton,
    KoinonTextPipe,
  ],
  templateUrl: './invitation-composer.html',
  styleUrl: './invitation-composer.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonInvitationComposer implements OnChanges {
  @Input() contextKey = '';
  @Input() brandBase = '/assets/brand';
  @Input() recipients: RecipientPage | null = null;
  @Input() roles: readonly CommunicationRole[] = [];
  @Input() scopes: readonly CommunicationScope[] = [];
  @Input() allowOrganization = false;
  @Input() organizationName = '';
  @Input() preview: InvitationEmailPreview | null = null;
  @Input() result: InvitationQueuedView | null = null;
  @Input() busy = false;
  @Input() deliveryAvailable = true;
  @Input() searching = false;
  @Input() error = '';
  @Output() searchRequested = new EventEmitter<{ q: string; after?: string }>();
  @Output() previewRequested = new EventEmitter<EmailInvitationDraft>();
  @Output() submitted = new EventEmitter<EmailInvitationDraft>();
  @Output() closed = new EventEmitter<void>();
  readonly step = signal<'person' | 'access' | 'review'>('person');
  readonly selected = signal<DirectoryRecipientView | null>(null);
  readonly validation = signal('');
  query = '';
  scopeId = '';
  role: CommunicationRole['id'] = 'viewer';
  hours = 24;
  private submitting = false;
  private readonly injector = inject(Injector);
  private readonly heading = viewChild<ElementRef<HTMLHeadingElement>>('stepHeading');
  private focusHeading() {
    afterNextRender(() => this.heading()?.nativeElement.focus(), { injector: this.injector });
  }
  ngOnChanges(changes: SimpleChanges) {
    if (changes['contextKey']) {
      this.selected.set(null);
      this.step.set('person');
      this.validation.set('');
      this.query = '';
      this.scopeId = '';
      this.role = 'viewer';
      this.hours = 24;
      this.submitting = false;
    }
    if (changes['busy'] && !this.busy) this.submitting = false;
  }
  eligible(person: DirectoryRecipientView) {
    return (
      !!person.recipient_ref &&
      ['eligible', 'already_has_access'].includes(person.eligibility) &&
      person.delivery_address_status === 'verified_directory'
    );
  }
  eligibilityHelp(person: DirectoryRecipientView) {
    if (person.eligibility_reason) return person.eligibility_reason;
    if (person.eligibility === 'already_has_access')
      return 'Existing access will be checked for the scope you choose.';
    if (person.delivery_address_status === 'missing')
      return 'Add a delivery address in the identity provider before inviting this person.';
    if (person.delivery_address_status === 'unverified')
      return 'Verify this address in the identity provider before sending an invitation.';
    return this.eligible(person)
      ? ''
      : 'This account is unavailable. Check the identity directory configuration.';
  }
  selectRecipient(person: DirectoryRecipientView) {
    if (this.busy || !this.eligible(person)) return;
    this.selected.set(person);
    this.validation.set('');
  }
  initials(name: string) {
    return (
      name
        .trim()
        .split(/\s+/)
        .slice(0, 2)
        .map((part) => Array.from(part)[0])
        .join('')
        .toUpperCase() || '?'
    );
  }
  search(after?: string) {
    if (this.searching) return;
    if (!after) this.selected.set(null);
    this.searchRequested.emit({ q: this.query.trim(), ...(after ? { after } : {}) });
  }
  draft(): EmailInvitationDraft {
    return {
      recipient_ref: this.selected()?.recipient_ref ?? '',
      role: this.role,
      workspace_id: this.scopeId || null,
      expires_in_hours: this.hours,
    };
  }
  recipientName() {
    return this.matchingPreview()
      ? this.preview?.recipient_display_name || this.selected()?.display_name
      : this.selected()?.display_name;
  }
  recipientEmail() {
    return this.matchingPreview()
      ? this.preview?.recipient_email || this.selected()?.email
      : this.selected()?.email;
  }
  roleLabel() {
    return this.roles.find((item) => item.id === this.role)?.label ?? this.role;
  }
  roleDescription() {
    return this.roles.find((item) => item.id === this.role)?.description ?? '';
  }
  scopeName() {
    return this.scopeId
      ? (this.scopes.find((scope) => scope.id === this.scopeId)?.name ?? '')
      : this.organizationName;
  }
  matchingPreview() {
    const current = this.draft(),
      preview = this.preview?.draft;
    return (
      !!preview &&
      Object.keys(current).every(
        (key) =>
          current[key as keyof EmailInvitationDraft] === preview[key as keyof EmailInvitationDraft],
      )
    );
  }
  advance() {
    if (this.busy) return;
    this.validation.set('');
    if (this.step() === 'person') {
      if (!this.selected() || !this.eligible(this.selected()!)) return;
      this.step.set('access');
      this.focusHeading();
      return;
    }
    if (this.step() !== 'access') return;
    if (
      (!this.scopeId && !this.allowOrganization) ||
      (this.scopeId && !this.scopes.some((scope) => scope.id === this.scopeId))
    ) {
      this.validation.set('Choose an access scope you administer.');
      return;
    }
    if (!this.roles.some((role) => role.id === this.role)) {
      this.validation.set('Choose an available role.');
      return;
    }
    this.step.set('review');
    this.focusHeading();
    this.previewRequested.emit(this.draft());
  }
  back() {
    if (this.busy) return;
    this.validation.set('');
    this.submitting = false;
    this.step.set(this.step() === 'review' ? 'access' : 'person');
    this.focusHeading();
  }
  submit() {
    if (
      !this.deliveryAvailable ||
      this.busy ||
      this.submitting ||
      this.step() !== 'review' ||
      !this.matchingPreview() ||
      !this.selected() ||
      !this.eligible(this.selected()!)
    )
      return;
    this.submitting = true;
    this.submitted.emit(this.draft());
  }
}
