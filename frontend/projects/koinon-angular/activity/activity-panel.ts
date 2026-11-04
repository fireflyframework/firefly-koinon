// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { UploadObservationLoop } from '@fireflyframework/koinon-angular/workbench/availability';
import { statusTone } from '@fireflyframework/koinon-angular/workbench/core';
import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  computed,
  effect,
  inject,
  signal,
  input,
  booleanAttribute,
  untracked,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import {
  KoinonBadge,
  KoinonButton,
  KoinonIcon,
  KoinonClientContext,
  KoinonFacade,
  KoinonI18n,
  KoinonSkeleton,
  KoinonTextPipe,
} from '@fireflyframework/koinon-angular';
import {
  KoinonError,
  type ActivitySummary,
  type Job,
  type ActivityWindow,
} from '@fireflyframework/koinon-sdk';
import {
  KoinonActivityWindow,
  activityWindow,
  defaultActivityDates,
} from '@fireflyframework/koinon-angular/activity/window';
import { KoinonProcessingHistory } from './processing-history';
import { activityAdministrator } from './activity-access';
import { KoinonActivitySummary } from './activity-summary';
@Component({
  selector: 'ffk-activity-panel',
  imports: [
    FormsModule,
    KoinonBadge,
    KoinonButton,
    KoinonIcon,
    KoinonSkeleton,
    KoinonTextPipe,
    KoinonActivityWindow,
    KoinonActivitySummary,
    KoinonProcessingHistory,
  ],
  template: `<header class="page-heading">
      <div>
        <h1>{{ (personalOnly() ? 'My activity' : 'Activity') | ffkText }}</h1>
        <p>
          {{
            (personalOnly()
              ? 'Review the knowledge you create, update and consult.'
              : 'Review knowledge use and follow file processing.'
            ) | ffkText
          }}
        </p>
      </div>
    </header>
    <section aria-label="Activity summary">
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
          <ffk-button type="submit" variant="primary" [loading]="pending()" [disabled]="denied">{{
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
    </section>
    @if (canManageJobs()) {
      <ffk-processing-history />
      <h2>{{ 'Processing jobs' | ffkText }}</h2>
      @if (jobsError()) {
        <p role="status">{{ jobsError() | ffkText }}</p>
        @if (!jobsDenied) {
          <ffk-button
            variant="quiet"
            icon="refresh"
            [disabled]="jobsPending()"
            (click)="refreshJobs()"
            >{{ 'Try again' | ffkText }}</ffk-button
          >
        }
      }
      <div class="workbench-table-wrap">
        <table>
          <thead>
            <tr>
              <th>{{ 'Knowledge' | ffkText }}</th>
              <th>{{ 'Activity' | ffkText }}</th>
              <th>{{ 'Status' | ffkText }}</th>
              <th>{{ 'Progress' | ffkText }}</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            @for (job of jobs(); track job.id) {
              <tr>
                <td>{{ jobResourceName(job.resource_id) }}</td>
                <td>{{ job.kind.replaceAll('_', ' ') }}</td>
                <td>
                  <ffk-badge [tone]="jobsStale() ? 'attention' : tone(job.status)">{{
                    job.status
                  }}</ffk-badge>
                  @if (job.error) {
                    <p class="job-error">{{ job.error }}</p>
                  }
                </td>
                <td>
                  @if (job.progress !== null && job.progress !== undefined) {
                    {{ job.progress }}%
                  }
                </td>
                <td>
                  @if (
                    !['knowledge.bulk.intake', 'knowledge.bulk.query'].includes(job.kind) &&
                    ['pending', 'queued', 'running'].includes(job.status.toLowerCase())
                  ) {
                    <ffk-button
                      variant="quiet"
                      [disabled]="jobsPending() || jobsStale()"
                      (click)="cancelJob(job.id)"
                      >{{ 'Cancel' | ffkText }}</ffk-button
                    >
                  }
                </td>
              </tr>
            } @empty {
              <tr>
                <td colspan="5">
                  <div class="workbench-empty">
                    <ffk-icon name="history" />
                    <h2>You’re up to date</h2>
                    <p>Uploads and processing activity will appear here.</p>
                  </div>
                </td>
              </tr>
            }
          </tbody>
        </table>
      </div>
    }`,
  styles: [
    `
      :host {
        display: block;
        margin: 0 0 36px;
      }
      .workbench-table-wrap {
        overflow-x: auto;
      }
      table {
        width: 100%;
        border-collapse: collapse;
        font-size: 13px;
      }
      th,
      td {
        padding: 16px 12px;
        text-align: left;
        border-bottom: 1px solid var(--ui-line);
      }
      th {
        color: var(--ui-muted);
        font-weight: 500;
      }
      .job-error {
        margin-top: 8px;
        color: var(--ui-muted);
        max-width: 40ch;
        overflow-wrap: anywhere;
      }
      .workbench-empty {
        padding: 32px;
        text-align: center;
        color: var(--ui-muted);
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
  readonly tone = statusTone;
  readonly personalOnly = input(false, { transform: booleanAttribute });
  readonly facade = inject(KoinonFacade);
  readonly clients = inject(KoinonClientContext);
  readonly i18n = inject(KoinonI18n);
  readonly pending = signal(false);
  readonly error = signal('');
  readonly stale = signal(false);
  protected denied = false;
  private alive = true;
  private expiry?: ReturnType<typeof setTimeout>;
  readonly now = signal(Date.now());
  private lastSelection = '';
  private readonly jobResult = signal<{ key: string; rows: Job[] } | null>(null);
  readonly jobs = computed(() =>
    this.canManageJobs() && this.jobResult()?.key === this.key() ? this.jobResult()!.rows : [],
  );
  readonly jobsPending = signal(false);
  readonly jobsStale = signal(false);
  readonly jobsError = signal('');
  protected jobsDenied = false;
  private jobsRequest?: AbortController;
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
    return `${this.personalOnly()}:${this.epoch}:${this.clients.revision()}:${this.facade.tenantId()}:${this.facade.workspaceId()}:${this.hasAdmin()}`;
  });
  private readonly result = signal<{ key: string; value: ActivitySummary } | null>(null);
  readonly summary = computed(() =>
    this.result()?.key === this.key() ? this.result()!.value : null,
  );
  private hasAdmin() {
    return activityAdministrator(this.facade.context(), this.facade.tenantId(), this.now());
  }
  readonly canAdmin = computed(
    () =>
      !this.personalOnly() &&
      this.hasAdmin() &&
      this.facade.tenantPermissions().has('audit:read') &&
      this.facade.tenantPermissions().has('activity:read'),
  );
  readonly canManageJobs = computed(
    () =>
      !this.personalOnly() && this.hasAdmin() && this.facade.tenantPermissions().has('jobs:manage'),
  );
  private selection() {
    return JSON.stringify([
      this.personalOnly() ? 'personal' : this.audience,
      this.window === undefined
        ? activityWindow(this.dates.start, this.dates.end, this.i18n.preferences().time_zone)
        : this.window,
    ]);
  }
  private readonly visible = signal(
    typeof document === 'undefined' || document.visibilityState !== 'hidden',
  );
  private readonly polling = new UploadObservationLoop({
    active: () =>
      this.alive &&
      !!this.clients.getTransport() &&
      !!this.facade.context()?.subject &&
      !!this.facade.tenantId() &&
      !this.pending() &&
      !this.jobsPending() &&
      ((!this.denied && this.selection() === this.lastSelection) ||
        (this.canManageJobs() && !this.jobsDenied)),
    visible: () => this.visible(),
    interval: () =>
      this.jobs().some((job) => ['queued', 'pending', 'running'].includes(job.status.toLowerCase()))
        ? 5000
        : 30000,
    read: async () => {
      await Promise.all([
        this.denied || this.selection() !== this.lastSelection
          ? Promise.resolve()
          : this.load(true),
        this.refreshJobs(true),
      ]);
      return (this.denied || !this.error()) && (this.jobsDenied || !this.jobsError());
    },
  });
  private readonly reenter = () => {
    this.visible.set(document.visibilityState !== 'hidden');
    this.now.set(Date.now());
    this.polling.reset();
  };
  private request: AbortController | null = null;
  constructor() {
    if (typeof document !== 'undefined') {
      document.addEventListener('visibilitychange', this.reenter);
      window.addEventListener('focus', this.reenter);
    }
    effect(() => {
      this.key();
      this.pending();
      this.jobsPending();
      this.canManageJobs();
      this.visible();
      this.polling.update();
    });
    effect(() => {
      this.now();
      clearTimeout(this.expiry);
      const times = (this.facade.context()?.memberships ?? [])
        .map((grant) => (grant.expires_at ? Date.parse(grant.expires_at) : NaN))
        .filter((time) => time > Date.now());
      if (times.length)
        this.expiry = setTimeout(
          () => this.now.set(Date.now()),
          Math.min(Math.max(1, Math.min(...times) - Date.now() + 1), 2147483647),
        );
    });
    effect(() => {
      this.key();
      untracked(() => {
        this.request?.abort();
        this.result.set(null);
        this.jobResult.set(null);
        this.jobsRequest?.abort();
        this.jobsRequest = undefined;
        this.jobsPending.set(false);
        this.jobsStale.set(false);
        this.jobsError.set('');
        this.jobsDenied = false;
        this.stale.set(false);
        this.denied = false;
        this.error.set('');
        this.audience = 'personal';
        this.polling.reset();
        void this.load();
        void this.refreshJobs();
      });
    });
    inject(DestroyRef).onDestroy(() => {
      this.alive = false;
      this.polling.dispose();
      clearTimeout(this.expiry);
      this.request?.abort();
      this.jobsRequest?.abort();
      if (typeof document !== 'undefined') {
        document.removeEventListener('visibilitychange', this.reenter);
        window.removeEventListener('focus', this.reenter);
      }
    });
  }
  jobResourceName(id: string) {
    return (
      [...(this.facade.context()?.workspaces ?? []), ...this.facade.entries()].find(
        (entry) => entry.id === id,
      )?.name || 'Knowledge processing'
    );
  }
  async load(background = false) {
    if (!this.alive || this.denied || (background && this.pending())) return;
    const key = this.key();
    this.request?.abort();
    if (!background) this.result.set(null);
    if (!this.stale()) this.error.set('');
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
    const audience = this.personalOnly() ? 'personal' : this.audience;
    if (audience === 'administrative' && !this.canAdmin()) {
      this.error.set('Your current account cannot view this activity.');
      return;
    }
    this.lastSelection = this.selection();
    const selection = this.lastSelection;
    const controller = new AbortController();
    this.request = controller;
    this.pending.set(true);
    const current = () =>
      this.alive &&
      !controller.signal.aborted &&
      this.request === controller &&
      this.key() === key &&
      this.selection() === selection;
    try {
      const api = this.clients.get().activity;
      const result = await (audience === 'administrative'
        ? api.administrative(this.facade.tenantId(), window, { signal: controller.signal })
        : api.personal(this.facade.tenantId(), window, { signal: controller.signal }));
      if (
        result.tenant_id !== this.facade.tenantId() ||
        (this.personalOnly() && result.audience !== 'personal')
      )
        throw new Error('Activity scope mismatch');
      if (current()) {
        this.result.set({ key, value: result });
        this.stale.set(false);
        this.error.set('');
      }
    } catch (error) {
      if (current()) {
        this.stale.set(true);
        if (error instanceof KoinonError && [401, 403].includes(error.status)) {
          this.denied = true;
          this.result.set(null);
        }
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
        this.polling.update();
      }
    }
  }
  async refreshJobs(background = false) {
    if (
      !this.alive ||
      !this.canManageJobs() ||
      this.jobsDenied ||
      !this.clients.getTransport() ||
      (background && this.jobsPending())
    )
      return;
    this.jobsRequest?.abort();
    const controller = new AbortController(),
      key = this.key(),
      tenant = this.facade.tenantId();
    this.jobsRequest = controller;
    this.jobsPending.set(true);
    if (!this.jobsStale()) this.jobsError.set('');
    const current = () =>
      this.alive &&
      this.jobsRequest === controller &&
      !controller.signal.aborted &&
      key === this.key() &&
      this.canManageJobs();
    try {
      const result = await this.clients.get().jobs.list(tenant, { signal: controller.signal });
      if (!current()) return;
      if (!Array.isArray(result.items) || result.items.some((job) => job.tenant_id !== tenant))
        throw Error('Job scope mismatch');
      this.jobResult.set({ key, rows: result.items });
      this.jobsStale.set(false);
      this.jobsError.set('');
    } catch (error) {
      if (!current()) return;
      this.jobsStale.set(true);
      this.jobsError.set('Processing observations could not be verified.');
      if (error instanceof KoinonError && [401, 403].includes(error.status)) {
        this.jobsDenied = true;
        this.jobResult.set(null);
        if (error.status === 401) this.facade.authRequired.set(true);
      }
    } finally {
      if (this.jobsRequest === controller) {
        this.jobsRequest = undefined;
        this.jobsPending.set(false);
        this.polling.update();
      }
    }
  }
  async cancelJob(id: string) {
    if (!this.canManageJobs() || this.jobsPending() || this.jobsStale()) return;
    if (await this.facade.cancelJob(id)) await this.refreshJobs();
  }
}
