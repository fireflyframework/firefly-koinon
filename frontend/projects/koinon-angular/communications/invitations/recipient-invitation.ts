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
} from '@angular/core';
import {
  KoinonButton,
  KoinonDatePipe,
  KoinonSkeleton,
  KoinonTextPipe,
} from '@fireflyframework/koinon-angular';
import type { RecipientInvitationReviewView } from '@fireflyframework/koinon-angular/communications';
import { registerKoinonSpanish } from '@fireflyframework/koinon-angular/workbench';
import { INVITATION_SPANISH } from './spanish';
registerKoinonSpanish(INVITATION_SPANISH);

@Component({
  selector: 'ffk-recipient-invitation',
  imports: [KoinonButton, KoinonDatePipe, KoinonSkeleton, KoinonTextPipe],
  templateUrl: './recipient-invitation.html',
  styleUrl: './recipient-invitation.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonRecipientInvitation implements OnChanges {
  @Input() review: RecipientInvitationReviewView | null = null;
  @Input() problem: 'sign_in' | 'wrong_account' | 'unavailable' | null = null;
  @Input() busy = false;
  @Input() error = '';
  @Output() accepted = new EventEmitter<string>();
  @Output() declined = new EventEmitter<string>();
  @Output() signInRequested = new EventEmitter<void>();
  @Output() switchAccountRequested = new EventEmitter<void>();
  @Output() closed = new EventEmitter<void>();
  @Output() retryRequested = new EventEmitter<void>();
  readonly confirmDecline = signal(false);
  private submitted = false;
  ngOnChanges(changes: SimpleChanges) {
    if (changes['review'] || changes['problem']) {
      this.submitted = false;
      this.confirmDecline.set(false);
    }
    if (changes['busy'] && !this.busy) this.submitted = false;
  }
  canAct() {
    return (
      !!this.review &&
      this.review.status === 'pending' &&
      !this.problem &&
      !this.busy &&
      !this.submitted
    );
  }
  accept() {
    if (this.canAct() && this.review!.can_accept) {
      this.submitted = true;
      this.accepted.emit(this.review!.id);
    }
  }
  decline() {
    if (this.canAct() && this.review!.can_decline && this.confirmDecline()) {
      this.submitted = true;
      this.declined.emit(this.review!.id);
    }
  }
  statusTitle() {
    return {
      pending: 'Review invitation',
      accepted: 'Invitation accepted',
      declined: 'Invitation declined',
      revoked: 'Invitation revoked',
      expired: 'Invitation expired',
    }[this.review?.status ?? 'pending'];
  }
  statusHelp() {
    return {
      pending: '',
      accepted:
        'This invitation has already been accepted. Your organization manages your current access.',
      declined: 'You declined this invitation. No access was granted through it.',
      revoked:
        'An administrator revoked this invitation. Ask them for a new invitation if you still need access.',
      expired: 'This invitation has expired. Ask an administrator for a new invitation.',
    }[this.review?.status ?? 'pending'];
  }
}
