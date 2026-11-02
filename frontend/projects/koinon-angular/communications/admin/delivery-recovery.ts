// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  afterRenderEffect,
  output,
  viewChild,
  OnDestroy,
  effect,
  input,
  signal,
  untracked,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import {
  KoinonButton,
  KoinonDatePipe,
  KoinonSkeleton,
  KoinonTextPipe,
} from '@fireflyframework/koinon-angular';
import type { DeliveryRecordView } from '@fireflyframework/koinon-angular/communications';
import type { KoinonCommunicationsSession } from '@fireflyframework/koinon-angular/communications/runtime';
import { registerKoinonSpanish } from '@fireflyframework/koinon-angular/workbench';
import { DeliveryRecoveryState } from './delivery-recovery-state';
import { DeliveryRecoveryJournal } from './delivery-recovery-journal';
import { deliveryReason, operationLabel } from './delivery-recovery-labels';
import { DELIVERY_RECOVERY_SPANISH } from './delivery-recovery-spanish';
registerKoinonSpanish(DELIVERY_RECOVERY_SPANISH);
@Component({
  selector: 'ffk-delivery-recovery',
  imports: [FormsModule, KoinonButton, KoinonDatePipe, KoinonSkeleton, KoinonTextPipe],
  templateUrl: './delivery-recovery.html',
  styleUrl: './delivery-recovery.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonDeliveryRecovery implements OnDestroy {
  readonly session = input.required<KoinonCommunicationsSession>();
  readonly delivery = input.required<DeliveryRecordView>();
  readonly deliveryRequested = output<string>();
  readonly accessDenied = output<void>();
  private readonly reviewTitle = viewChild<ElementRef<HTMLElement>>('reviewTitle');
  private readonly sectionTitle = viewChild<ElementRef<HTMLElement>>('sectionTitle');
  private readonly returnFocus = signal(false);
  readonly state = signal<DeliveryRecoveryState | null>(null);
  readonly duplicate = signal(false);
  private bound: KoinonCommunicationsSession | null = null;
  readonly reason = deliveryReason;
  readonly operationLabel = operationLabel;
  constructor() {
    afterRenderEffect(() => {
      const title = this.reviewTitle();
      if (title) title.nativeElement.focus();
      else if (this.returnFocus()) {
        this.sectionTitle()?.nativeElement.focus();
        this.returnFocus.set(false);
      }
    });
    effect(() => {
      const session = this.session(),
        delivery = this.delivery();
      session.key();
      untracked(() => {
        this.duplicate.set(false);
        if (this.bound !== session) {
          this.state()?.dispose();
          this.bound = session;
          this.state.set(
            new DeliveryRecoveryState({
              scope: () => ({
                key: session.key(),
                subject: session.facade.context()?.subject ?? '',
                tenantId: session.facade.tenantId(),
                allowed: this.allowed(),
              }),
              api: () => session.api,
              journal: new DeliveryRecoveryJournal({
                getItem: (key) => sessionStorage.getItem(key),
                setItem: (key, value) => sessionStorage.setItem(key, value),
                removeItem: (key) => sessionStorage.removeItem(key),
              }),
              denied: (status) => {
                if (status === 401) session.facade.authRequired.set(true);
                session.error.set('Your current account cannot inspect or manage this delivery.');
                this.accessDenied.emit();
              },
            }),
          );
        }
        this.state()!.sync();
        void this.state()!.open(delivery.id);
      });
    });
  }
  allowed() {
    const f = this.session().facade,
      context = f.context(),
      tenantId = f.tenantId();
    return (
      !!context?.subject &&
      context.tenants.some((t) => t.id === tenantId && t.permissions.includes('members:write')) &&
      context.memberships.some(
        (m) =>
          m.subject === context.subject &&
          m.tenant_id === tenantId &&
          m.workspace_id === null &&
          m.role === 'admin' &&
          m.active === true &&
          (m.expires_at == null || Date.parse(m.expires_at) > Date.now()),
      )
    );
  }
  async review(operation: 'inspect' | 'welcome') {
    this.duplicate.set(false);
    await this.state()?.review(operation);
  }
  async reviewSaved(request: Parameters<DeliveryRecoveryState['reviewSaved']>[0]) {
    this.duplicate.set(false);
    await this.state()?.reviewSaved(request);
  }
  cancel() {
    this.state()?.closeReview();
    this.returnFocus.set(true);
  }
  async confirm() {
    await this.state()?.confirm(this.duplicate());
    this.returnFocus.set(true);
  }
  ngOnDestroy() {
    this.state()?.dispose();
  }
}
