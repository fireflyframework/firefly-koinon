// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { computed, signal } from '@angular/core';
import { KoinonError } from '@fireflyframework/koinon-sdk';
import type {
  CommunicationsApi,
  DeliveryRecoveryOptions,
  DeliveryOperationObservation,
  DeliveryObservationPage,
  WelcomeRecoveryAcknowledgement,
} from '@fireflyframework/koinon-sdk/communications';
import { DeliveryRecoveryJournal, type DeliveryWrite } from './delivery-recovery-journal';
export interface DeliveryScope {
  key: string;
  subject: string;
  tenantId: string;
  allowed: boolean;
}
interface Ports {
  scope(): DeliveryScope;
  api(): CommunicationsApi | null;
  journal: DeliveryRecoveryJournal;
  denied?(status: 401 | 403): void;
}
interface View {
  options: DeliveryRecoveryOptions | null;
  history: DeliveryOperationObservation[];
  hasMore: boolean;
  review: { request: DeliveryWrite; replay: boolean } | null;
  pending: DeliveryWrite[];
  acknowledgment: WelcomeRecoveryAcknowledgement | null;
  busy: boolean;
  error: string;
  notice: string;
  journalError: boolean;
  stale: boolean;
}
const empty = (): View => ({
  options: null,
  history: [],
  hasMore: false,
  review: null,
  pending: [],
  acknowledgment: null,
  busy: false,
  error: '',
  notice: '',
  journalError: false,
  stale: false,
});
const statuses = [
  'queued',
  'sending',
  'sent',
  'delivered',
  'deferred',
  'failed',
  'suppressed',
  'cancelled',
  'unknown',
];
const integer = (value: unknown, min = 0) => Number.isSafeInteger(value) && Number(value) >= min;
const identifier = (value: unknown): value is string =>
  typeof value === 'string' &&
  value.length > 0 &&
  value.length <= 64 &&
  Array.from(value).every((c) => c.charCodeAt(0) >= 32 && c.charCodeAt(0) !== 127);
interface Session {
  scope: DeliveryScope;
  id: string;
  api: CommunicationsApi;
  abort: AbortController;
}
export class DeliveryRecoveryState {
  private readonly state = signal<View>(empty());
  private key: string;
  private id = '';
  private session: Session | null = null;
  private alive = true;
  private denied = false;
  readonly view = computed(() => {
    const value = this.state();
    return this.alive && this.ports.scope().key === this.key && this.ports.scope().allowed
      ? value
      : empty();
  });
  constructor(private readonly ports: Ports) {
    this.key = ports.scope().key;
  }
  sync() {
    const scope = this.ports.scope();
    if (scope.key === this.key && scope.allowed) return;
    this.session?.abort.abort();
    this.session = null;
    if (scope.key !== this.key) this.denied = false;
    this.key = scope.key;
    this.state.set(empty());
  }
  private current(s: Session) {
    const scope = this.ports.scope();
    return (
      this.alive &&
      this.session === s &&
      !s.abort.signal.aborted &&
      s.id === this.id &&
      s.scope.key === scope.key &&
      scope.allowed
    );
  }
  private check(s: Session) {
    if (!this.current(s)) throw new DOMException('Access changed', 'AbortError');
  }
  private set(s: Session, value: Partial<View>) {
    if (this.current(s)) this.state.update((v) => ({ ...v, ...value }));
  }
  private async run(work: (s: Session) => Promise<void>, readOnly = false) {
    this.sync();
    const scope = this.ports.scope(),
      api = this.ports.api();
    if (
      !this.alive ||
      this.denied ||
      !scope.allowed ||
      !scope.subject ||
      !scope.tenantId ||
      this.session ||
      !api ||
      !this.id
    )
      return;
    const s: Session = { scope: { ...scope }, id: this.id, api, abort: new AbortController() };
    this.session = s;
    this.set(s, { busy: true, ...(readOnly ? {} : { error: '', notice: '' }) });
    try {
      await work(s);
    } catch (error) {
      if (!this.current(s)) return;
      if (error instanceof KoinonError && (error.status === 401 || error.status === 403)) {
        this.set(s, {
          ...empty(),
          error: 'Your current account cannot inspect or manage this delivery.',
        });
        this.denied = true;
        this.ports.denied?.(error.status);
      } else
        this.set(s, {
          stale: true,
          error: this.state().pending.length
            ? 'The request result is not confirmed. Inspect this delivery before reviewing the exact saved request.'
            : 'The delivery could not be inspected. Refresh its details before continuing.',
        });
    } finally {
      if (this.session === s) {
        this.set(s, { busy: false });
        this.session = null;
      }
    }
  }
  private options(s: Session, value: DeliveryRecoveryOptions) {
    this.check(s);
    if (
      !value ||
      value.delivery_id !== s.id ||
      !integer(value.generation) ||
      !integer(value.attempt_count) ||
      !statuses.includes(value.submission_status) ||
      typeof value.can_inspect !== 'boolean' ||
      typeof value.can_recover_welcome !== 'boolean' ||
      !['verified', 'operator_verification_required', 'unavailable'].includes(
        value.provider_binding_state,
      ) ||
      value.possible_original_late_arrival !== true ||
      (value.can_recover_welcome &&
        (!identifier(value.contact_id) || !integer(value.contact_revision, 1)))
    )
      throw Error('Invalid delivery options');
  }
  private observation(s: Session, value: DeliveryOperationObservation) {
    this.check(s);
    if (
      !value ||
      !identifier(value.id) ||
      value.delivery_id !== s.id ||
      value.source !== 'operation_lookup' ||
      value.recipient_state !== 'not_observed' ||
      !['checking', 'pending', 'accepted', 'rejected', 'unknown', 'unavailable'].includes(
        value.operation_state,
      ) ||
      (value.checked_at != null && !Number.isFinite(Date.parse(value.checked_at)))
    )
      throw Error('Invalid operation observation');
  }
  private async read(s: Session) {
    const request = { signal: s.abort.signal };
    const options = await s.api.administration.recovery(s.scope.tenantId, s.id, request);
    this.options(s, options);
    const history: DeliveryObservationPage = await s.api.administration.observations(
      s.scope.tenantId,
      s.id,
      request,
    );
    this.check(s);
    if (
      !Array.isArray(history.items) ||
      history.items.length > 25 ||
      typeof history.has_more !== 'boolean' ||
      new Set(history.items.map((v) => v.id)).size !== history.items.length
    )
      throw Error('Invalid observation history');
    for (const row of history.items) this.observation(s, row);
    return { options, history: history.items, hasMore: history.has_more };
  }
  private admit(s: Session, value: Awaited<ReturnType<DeliveryRecoveryState['read']>>) {
    let pending: DeliveryWrite[] = [];
    let journalError = false;
    try {
      pending = this.ports.journal.forDelivery(s.scope.subject, s.scope.tenantId, s.id);
    } catch {
      journalError = true;
    }
    this.set(s, {
      ...value,
      pending,
      journalError,
      review: null,
      stale: false,
      error: '',
      ...(journalError
        ? {
            error:
              'Saved delivery requests could not be verified. This browser tab must support session storage before making changes.',
          }
        : {}),
    });
  }
  async open(id: string) {
    if (!identifier(id)) return;
    if (this.id === id && this.view().review) return;
    if (this.id !== id) {
      this.session?.abort.abort();
      this.session = null;
      this.id = id;
      this.state.set(empty());
    }
    return this.run(async (s) => this.admit(s, await this.read(s)), true);
  }
  async review(operation: 'inspect' | 'welcome') {
    if (
      this.view().busy ||
      this.view().stale ||
      this.view().journalError ||
      this.view().pending.length
    )
      return;
    return this.run(async (s) => {
      const fresh = await this.read(s);
      this.admit(s, fresh);
      const value = fresh.options;
      if (
        this.state().journalError ||
        (operation === 'inspect' ? !value.can_inspect : !value.can_recover_welcome)
      )
        return;
      const common = {
        subject: s.scope.subject,
        tenantId: s.scope.tenantId,
        deliveryId: s.id,
        key: crypto.randomUUID(),
      };
      const request: DeliveryWrite =
        operation === 'inspect'
          ? { ...common, operation, input: { expected_generation: value.generation } }
          : {
              ...common,
              operation,
              input: {
                expected_generation: value.generation,
                contact_id: value.contact_id!,
                expected_contact_revision: value.contact_revision!,
                reason: 'recipient_reported_not_received',
                acknowledge_possible_duplicate: true,
              },
            };
      this.set(s, { review: { request, replay: false } });
    });
  }
  async reviewSaved(request: DeliveryWrite) {
    return this.run(async (s) => {
      this.admit(s, await this.read(s));
      const saved = this.state().pending.find((v) => v.key === request.key);
      if (saved && !this.state().journalError)
        this.set(s, { review: { request: saved, replay: true } });
    });
  }
  closeReview() {
    if (!this.view().busy) this.state.update((v) => ({ ...v, review: null }));
  }
  async confirm(acknowledged: boolean) {
    const review = this.view().review;
    if (!review || (review.request.operation === 'welcome' && !acknowledged)) return;
    return this.run(async (s) => {
      const fresh = await this.read(s);
      this.admit(s, fresh);
      if (this.state().journalError) return;
      const request = review.request,
        value = fresh.options;
      if (
        request.subject !== s.scope.subject ||
        request.tenantId !== s.scope.tenantId ||
        request.deliveryId !== s.id
      )
        return;
      if (
        !review.replay &&
        (request.input.expected_generation !== value.generation ||
          (request.operation === 'inspect'
            ? !value.can_inspect
            : !value.can_recover_welcome ||
              request.input.contact_id !== value.contact_id ||
              request.input.expected_contact_revision !== value.contact_revision))
      ) {
        this.set(s, {
          error:
            'This delivery changed. Inspect its current options before confirming another action.',
        });
        return;
      }
      if (review.replay && !this.state().pending.some((v) => v.key === request.key)) return;
      this.ports.journal.put(request);
      this.set(s, {
        pending: this.ports.journal.forDelivery(s.scope.subject, s.scope.tenantId, s.id),
        review: null,
      });
      try {
        if (request.operation === 'inspect') {
          const result = await s.api.administration.inspectDelivery(
            s.scope.tenantId,
            s.id,
            request.input,
            request.key,
            { signal: s.abort.signal },
          );
          this.observation(s, result);
          this.set(s, {
            history: [result, ...this.state().history.filter((v) => v.id !== result.id)].slice(
              0,
              25,
            ),
            notice:
              'Email service observation recorded. This does not confirm that the recipient received the message.',
          });
        } else {
          const result = await s.api.administration.recoverWelcome(
            s.scope.tenantId,
            s.id,
            request.input,
            request.key,
            { signal: s.abort.signal },
          );
          this.check(s);
          if (
            result.original_delivery_id !== s.id ||
            !identifier(result.delivery_id) ||
            result.delivery_id === s.id ||
            !statuses.includes(result.status) ||
            result.possible_original_late_arrival !== true
          )
            throw Error('Invalid welcome acknowledgment');
          this.set(s, {
            acknowledgment: result,
            notice:
              'A new welcome was queued. The earlier delivery is unchanged and may still arrive. Mailbox receipt is not confirmed.',
          });
        }
        this.ports.journal.clear(request);
        this.set(s, {
          pending: this.ports.journal.forDelivery(s.scope.subject, s.scope.tenantId, s.id),
          options: null,
        });
      } catch (error) {
        if (error instanceof KoinonError && [400, 401, 403, 409, 422, 429].includes(error.status)) {
          this.ports.journal.clear(request);
          this.set(s, {
            pending: [],
            error:
              'The request was not accepted. Inspect current delivery options before choosing another action.',
          });
          if (error.status === 401 || error.status === 403) throw error;
          return;
        }
        throw error;
      }
    });
  }
  dispose() {
    this.alive = false;
    this.session?.abort.abort();
    this.session = null;
    this.state.set(empty());
  }
}
