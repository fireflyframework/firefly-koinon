// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import {
  ChangeDetectionStrategy,
  Component,
  EventEmitter,
  Input,
  OnChanges,
  Output,
  effect,
  inject,
  untracked,
} from '@angular/core';
import { KoinonError } from '@fireflyframework/koinon-sdk';
import type { Membership, InvitationReview } from '@fireflyframework/koinon-sdk';
import type { RecipientInvitationReviewView } from '@fireflyframework/koinon-angular/communications';
import { KoinonCommunicationsSession } from '@fireflyframework/koinon-angular/communications/runtime';
import { KoinonRecipientInvitation } from './recipient-invitation';
import { invitationActionReason } from './action-reasons';
const roles = {
  viewer: 'Viewer',
  analyst: 'Analyst',
  editor: 'Editor',
  operator: 'Operator',
  admin: 'Administrator',
};
@Component({
  selector: 'ffk-email-invitation-acceptance',
  imports: [KoinonRecipientInvitation],
  providers: [KoinonCommunicationsSession],
  template: `<ffk-recipient-invitation
    [review]="review()"
    [problem]="problem()"
    [busy]="session.pending()"
    [error]="session.error()"
    (accepted)="accept()"
    (declined)="decline()"
    (closed)="closed.emit()"
    (retryRequested)="load()"
    (signInRequested)="signInRequested.emit()"
    (switchAccountRequested)="switchAccountRequested.emit()"
  />`,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonEmailInvitationAcceptance implements OnChanges {
  readonly session = inject(KoinonCommunicationsSession);
  @Input() invitationId = '';
  @Output() accepted = new EventEmitter<Membership>();
  @Output() closed = new EventEmitter<void>();
  @Output() signInRequested = new EventEmitter<void>();
  @Output() switchAccountRequested = new EventEmitter<void>();
  readonly review = this.session.state<RecipientInvitationReviewView | null>(null);
  readonly problem = this.session.state<'sign_in' | 'wrong_account' | 'unavailable' | null>(null);
  constructor() {
    effect(() => {
      this.session.key();
      untracked(() => {
        this.review.set(null);
        void this.load();
      });
    });
  }
  ngOnChanges() {
    this.review.set(null);
    void this.load();
  }
  private apply(value: InvitationReview) {
    this.problem.set(null);
    this.review.set({
      ...value,
      role_name: roles[value.role],
      accept_reason: invitationActionReason(value.action_reasons?.accept),
      role_description: 'Permissions apply to shared knowledge in this scope.',
    });
  }
  async load() {
    if (!this.invitationId) return;
    this.problem.set(null);
    await this.session.run(
      'review',
      (signal) => this.session.api!.emailInvitations.review(this.invitationId, { signal }),
      (value) => this.apply(value),
      (error) =>
        this.problem.set(
          error instanceof KoinonError && error.status === 401
            ? 'sign_in'
            : error instanceof KoinonError && error.status === 403
              ? 'wrong_account'
              : 'unavailable',
        ),
    );
  }
  async accept() {
    if (!this.review()?.can_accept || this.session.pending()) return;
    await this.session.run(
      'decision',
      (signal) => this.session.api!.emailInvitations.accept(this.invitationId, { signal }),
      (value) => {
        this.review.update((current) =>
          current
            ? { ...current, status: 'accepted', can_accept: false, can_decline: false }
            : null,
        );
        this.accepted.emit(value);
      },
    );
  }
  async decline() {
    if (!this.review()?.can_decline || this.session.pending()) return;
    await this.session.run(
      'decision',
      (signal) => this.session.api!.emailInvitations.decline(this.invitationId, { signal }),
      (value) => this.apply(value),
    );
  }
}
