// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
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
  type ActivityWindow,
} from '@fireflyframework/koinon-sdk';
import {
  KoinonActivityWindow,
  activityWindow,
  defaultActivityDates,
} from '@fireflyframework/koinon-angular/activity/window';
import { KoinonProcessingHistory } from './processing-history';
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
  template: `<header class="page-heading"><div><h1>{{ (personalOnly() ? 'My activity' : 'Activity') | ffkText }}</h1><p>{{(personalOnly() ? 'Review the knowledge you create, update and consult.' : 'Review knowledge use and follow file processing.') | ffkText}}</p></div>@if(!personalOnly()){<ffk-button variant="quiet" icon="refresh" (click)="facade.loadJobs()">{{'Refresh'|ffkText}}</ffk-button>}</header><section aria-label="Activity summary">
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
    </section>
    @if (!personalOnly() && facade.tenantPermissions().has('jobs:manage')) {
      <ffk-processing-history />
      <h2>{{ 'Processing jobs' | ffkText }}</h2>
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
            @for (job of facade.jobs(); track job.id) {
              <tr>
                <td>{{ jobResourceName(job.resource_id) }}</td>
                <td>{{ job.kind.replaceAll('_', ' ') }}</td>
                <td>
                  <ffk-badge [tone]="job.status === 'failed' ? 'attention' : 'neutral'">{{
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
                    <ffk-button variant="quiet" (click)="facade.cancelJob(job.id)">{{
                      'Cancel' | ffkText
                    }}</ffk-button>
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
  readonly personalOnly = input(false, {transform:booleanAttribute});
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
    return `${this.personalOnly()}:${this.epoch}:${this.clients.revision()}:${this.facade.tenantId()}:${this.facade.workspaceId()}`;
  });
  private readonly result = signal<{ key: string; value: ActivitySummary } | null>(null);
  readonly summary = computed(() =>
    this.result()?.key === this.key() ? this.result()!.value : null,
  );
  readonly canAdmin = computed(
    () =>
      !this.personalOnly() && !!this.facade
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
  jobResourceName(id: string) {
    return (
      [...(this.facade.context()?.workspaces ?? []), ...this.facade.entries()].find(
        (entry) => entry.id === id,
      )?.name || 'Knowledge processing'
    );
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
    const audience = this.personalOnly() ? 'personal' : this.audience;
    if (audience === 'administrative' && !this.canAdmin()) {
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
      const result = await (audience === 'administrative'
        ? api.administrative(this.facade.tenantId(), window, { signal: controller.signal })
        : api.personal(this.facade.tenantId(), window, { signal: controller.signal }));
      if (result.tenant_id !== this.facade.tenantId() || (this.personalOnly() && result.audience !== 'personal')) throw new Error('Activity scope mismatch');
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
