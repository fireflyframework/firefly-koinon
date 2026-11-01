// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  computed,
  effect,
  inject,
  signal,
  untracked,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import {
  KoinonButton,
  KoinonClientContext,
  KoinonFacade,
  KoinonI18n,
  KoinonSkeleton,
  KoinonTextPipe,
} from '@fireflyframework/koinon-angular';
import {
  KoinonError,
  type ActivitySummary,
  type ActivityWindow,
} from '@fireflyframework/koinon-sdk';
import {
  KoinonActivityWindow,
  activityWindow,
  defaultActivityDates,
} from '@fireflyframework/koinon-angular/activity/window';
import { KoinonActivitySummary } from './activity-summary';
@Component({
  selector: 'ffk-activity-panel',
  imports: [
    FormsModule,
    KoinonButton,
    KoinonSkeleton,
    KoinonTextPipe,
    KoinonActivityWindow,
    KoinonActivitySummary,
  ],
  template: `<section aria-label="Activity summary">
    <form (ngSubmit)="load()">
      <ffk-activity-window
        [timeZone]="i18n.preferences().time_zone"
        [disabled]="pending()"
        (windowChanged)="window = $event"
      />
      <div class="actions">
        @if (canAdmin()) {
          <label
            >{{ 'Summary audience' | ffkText
            }}<select name="activity-audience" [(ngModel)]="audience" [disabled]="pending()">
              <option value="personal">{{ 'Personal activity' | ffkText }}</option>
              <option value="administrative">{{ 'Administrator activity' | ffkText }}</option>
            </select></label
          >
        }
        <ffk-button type="submit" variant="primary" [loading]="pending()">{{
          'View summary' | ffkText
        }}</ffk-button>
      </div>
    </form>
    @if (error()) {
      <p role="alert">{{ error() | ffkText }}</p>
    }
    @if (summary(); as current) {
      <ffk-activity-summary [value]="current" />
    } @else if (pending()) {
      <ffk-skeleton width="70%" height="3px" [label]="'Loading activity' | ffkText" />
    }
  </section>`,
  styles: [
    `
      :host {
        display: block;
        margin: 24px 0 36px;
      }
      .actions {
        display: flex;
        align-items: end;
        gap: 24px;
        flex-wrap: wrap;
        margin-top: 20px;
      }
      label {
        display: grid;
        gap: 8px;
        font-size: 13px;
      }
      select {
        min-height: 44px;
        border: 1px solid var(--ui-line);
        border-radius: 8px;
        padding: 10px;
        background: var(--ui-surface);
        color: var(--ui-text);
        font: inherit;
      }
      p[role='alert'] {
        font-size: 13px;
        color: var(--ui-danger, var(--ui-text));
        margin: 20px 0;
      }
    `,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonActivityPanel {
  readonly facade = inject(KoinonFacade);
  readonly clients = inject(KoinonClientContext);
  readonly i18n = inject(KoinonI18n);
  readonly pending = signal(false);
  readonly error = signal('');
  audience: 'personal' | 'administrative' = 'personal';
  private readonly dates = defaultActivityDates();
  window: ActivityWindow | null | undefined = undefined;
  private identity: object | null = null;
  private epoch = 0;
  readonly key = computed(() => {
    const context = this.facade.context();
    if (context !== this.identity) {
      this.identity = context;
      ++this.epoch;
    }
    return `${this.epoch}:${this.clients.revision()}:${this.facade.tenantId()}:${this.facade.workspaceId()}`;
  });
  private readonly result = signal<{ key: string; value: ActivitySummary } | null>(null);
  readonly summary = computed(() =>
    this.result()?.key === this.key() ? this.result()!.value : null,
  );
  readonly canAdmin = computed(
    () =>
      !!this.facade
        .context()
        ?.memberships.some(
          (grant) =>
            grant.active &&
            grant.tenant_id === this.facade.tenantId() &&
            !grant.workspace_id &&
            grant.role === 'admin',
        ) &&
      this.facade.tenantPermissions().has('audit:read') &&
      this.facade.tenantPermissions().has('activity:read'),
  );
  private request: AbortController | null = null;
  constructor() {
    effect(() => {
      this.key();
      untracked(() => {
        this.request?.abort();
        this.result.set(null);
        this.error.set('');
        this.audience = 'personal';
        void this.load();
      });
    });
    inject(DestroyRef).onDestroy(() => this.request?.abort());
  }
  async load() {
    const key = this.key();
    this.request?.abort();
    this.result.set(null);
    this.error.set('');
    if (!this.clients.getTransport()) {
      this.pending.set(false);
      this.error.set('Activity is not connected in this application.');
      return;
    }
    if (!this.facade.context()?.subject || !this.facade.tenantId()) {
      this.pending.set(false);
      return;
    }
    const window =
      this.window === undefined
        ? activityWindow(this.dates.start, this.dates.end, this.i18n.preferences().time_zone)
        : this.window;
    if (!window) {
      this.error.set('Choose a valid past reporting window of at most 366 days.');
      return;
    }
    if (this.audience === 'administrative' && !this.canAdmin()) {
      this.error.set('Your current account cannot view this activity.');
      return;
    }
    const controller = new AbortController();
    this.request = controller;
    this.pending.set(true);
    const current = () =>
      !controller.signal.aborted && this.request === controller && this.key() === key;
    try {
      const api = this.clients.get().activity;
      const result = await (this.audience === 'administrative'
        ? api.administrative(this.facade.tenantId(), window, { signal: controller.signal })
        : api.personal(this.facade.tenantId(), window, { signal: controller.signal }));
      if (current()) this.result.set({ key, value: result });
    } catch (error) {
      if (current()) {
        if (error instanceof KoinonError && error.status === 401)
          this.facade.authRequired.set(true);
        this.error.set(
          error instanceof KoinonError && error.status === 403
            ? 'Your current account cannot view this activity.'
            : 'Activity could not be loaded. Try again.',
        );
      }
    } finally {
      if (this.request === controller) {
        this.request = null;
        this.pending.set(false);
      }
    }
  }
}
