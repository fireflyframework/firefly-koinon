// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  Injector,
  afterNextRender,
  PendingTasks,
  computed,
  effect,
  inject,
  input,
  signal,
  untracked,
  type OnDestroy,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import {
  KoinonBadge,
  KoinonButton,
  KoinonClientContext,
  KoinonDatePipe,
  KoinonFacade,
  KoinonPagination,
  KoinonSkeleton,
  KoinonTextPipe,
  KoinonValuePipe,
} from '@fireflyframework/koinon-angular';
import { registerKoinonSpanish } from '@fireflyframework/koinon-angular/workbench';
import type { Configuration, KnowledgeIndexView, Page } from '@fireflyframework/koinon-sdk';
import {
  availableIndexActions,
  indexPermissions,
  type IndexActionName,
  type IndexDomain,
  type IndexManagementScope,
} from './index-management-contract';
import { IndexActionJournal } from './index-management-journal';
import { IndexManagementState } from './index-management-state';
import { INDEX_MANAGEMENT_SPANISH } from './index-management-spanish';
registerKoinonSpanish(INDEX_MANAGEMENT_SPANISH);
@Component({
  selector: 'ffk-index-management-panel',
  imports: [
    FormsModule,
    KoinonBadge,
    KoinonButton,
    KoinonDatePipe,
    KoinonPagination,
    KoinonSkeleton,
    KoinonTextPipe,
    KoinonValuePipe,
  ],
  templateUrl: './index-management-panel.html',
  styleUrl: './index-management-panel.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonIndexManagementPanel implements OnDestroy {
  readonly configuration = input<Configuration | null>(null);
  private readonly f = inject(KoinonFacade);
  private readonly clients = inject(KoinonClientContext);
  private readonly tasks = inject(PendingTasks);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  private readonly injector = inject(Injector);
  readonly workspace = signal(this.f.workspaceId());
  readonly domain = signal<IndexDomain>('documents');
  readonly filter = signal('');
  readonly editing = signal(false);
  readonly replayReview = signal(false);
  readonly providerId = signal('');
  readonly modelId = signal('');
  readonly now = signal(Date.now());
  private expiry?: ReturnType<typeof setTimeout>;
  readonly workspaces = computed(
    () =>
      this.f
        .context()
        ?.workspaces.filter(
          (row) =>
            row.tenant_id === this.f.tenantId() &&
            row.kind === 'workspace' &&
            row.status !== 'archived',
        ) ?? [],
  );
  readonly providers = computed(
    () =>
      this.configuration()?.providers.filter(
        (row) => row.enabled && ['openai', 'ollama'].includes(row.kind),
      ) ?? [],
  );
  readonly models = computed(
    () => this.providers().find((row) => row.id === this.providerId())?.model_ids ?? [],
  );
  private scope = (): IndexManagementScope => {
    const context = this.f.context();
    return {
      owner: context,
      subject: context?.subject ?? '',
      tenantId: this.f.tenantId(),
      workspaceId: this.workspace(),
      domain: this.domain(),
      clientRevision: this.clients.revision(),
      ...indexPermissions(
        context,
        this.f.tenantId(),
        this.workspace(),
        Math.max(this.now(), Date.now()),
      ),
    };
  };
  private journal() {
    try {
      return new IndexActionJournal(sessionStorage);
    } catch {
      return new IndexActionJournal({
        getItem: () => {
          throw Error('Session storage unavailable');
        },
        setItem: () => {
          throw Error('Session storage unavailable');
        },
        removeItem: () => {
          throw Error('Session storage unavailable');
        },
      });
    }
  }
  readonly state = new IndexManagementState({
    scope: this.scope,
    client: () => this.clients.get(),
    journal: this.journal(),
    denied: (status) => {
      if (status === 401) this.f.authRequired.set(true);
    },
  });
  readonly canRead = computed(() => this.scope().read && !this.state.view().accessDenied);
  readonly canManage = computed(
    () => this.scope().manage && !this.state.view().accessDenied && !this.state.view().journalError,
  );
  readonly page = computed<Page<KnowledgeIndexView>>(() => {
    const view = this.state.view();
    return {
      items: view.rows,
      total: view.total,
      page: view.page,
      page_size: 25,
      pages: Math.max(1, Math.ceil(view.total / 25)),
    };
  });
  readonly statuses = [
    'queued',
    'building',
    'awaiting_index',
    'ready',
    'activating',
    'active',
    'retired',
    'failed',
    'cancelled',
  ];
  readonly actionLabels: Record<IndexActionName, string> = {
    activate: 'Activate index',
    cancel: 'Cancel build',
    resume: 'Resume build',
    finish: 'Finish activation',
    restore_previous: 'Restore previous index',
  };
  readonly actionHelp: Record<IndexActionName, string> = {
    activate:
      'This switches the active target and its compatible embedding assignment for this workspace. The previous version remains in retained history.',
    cancel:
      'This requests cancellation of the current build. It does not delete source knowledge or prove that provider work has physically stopped.',
    resume:
      'This queues more work for the same nonactive target and its recorded embedding identity. Provider usage may apply.',
    finish:
      'This explicitly finishes an interrupted activation using the current target, native pointer and assignment revisions.',
    restore_previous:
      'This explicitly restores the previous native target and reviewed assignment after an interrupted activation.',
  };
  constructor() {
    effect(() => {
      this.scope();
      untracked(() => {
        this.state.syncScope();
        this.editing.set(false);
        this.replayReview.set(false);
        this.providerId.set('');
        this.modelId.set('');
        if (this.scope().read) void this.track(() => this.state.load(1, this.filter()));
      });
    });
    effect(() => {
      this.now();
      clearTimeout(this.expiry);
      const times = (this.f.context()?.memberships ?? [])
        .map((row) => (row.expires_at ? Date.parse(row.expires_at) : NaN))
        .filter((time) => time > Date.now());
      if (times.length)
        this.expiry = setTimeout(
          () => this.now.set(Date.now()),
          Math.min(Math.max(1, Math.min(...times) - Date.now() + 1), 2147483647),
        );
    });
  }
  status(value: string) {
    return (
      (
        {
          queued: 'Queued',
          building: 'Building',
          awaiting_index: 'Awaiting physical index',
          ready: 'Ready for review',
          activating: 'Activation unfinished',
          active: 'Active',
          retired: 'Retired',
          failed: 'Failed',
          cancelled: 'Cancelled',
        } as Record<string, string>
      )[value] ?? 'Unknown'
    );
  }
  providerName(id: string) {
    return this.configuration()?.providers.find((row) => row.id === id)?.name ?? id;
  }
  qualification(value: string) {
    return (
      (
        {
          coverage_and_ann_passed: 'Coverage and physical index verified',
          probe_passed: 'Embedding check passed',
          stale: 'Verification incomplete',
          native_target_unavailable: 'Native target unavailable',
          legacy_provider_history_required: 'Historical provider evidence required',
        } as Record<string, string>
      )[value] ?? 'Verification not established'
    );
  }
  rowStatus(row: KnowledgeIndexView) {
    return this.state.view().activeKnown && this.state.view().active?.id === row.id
      ? 'Active'
      : row.status === 'active'
        ? 'Recorded active, not confirmed'
        : this.status(row.status);
  }
  tone(row: KnowledgeIndexView): 'ready' | 'attention' | 'neutral' {
    return this.state.view().activeKnown && this.state.view().active?.id === row.id
      ? 'ready'
      : ['failed', 'activating', 'active'].includes(row.status)
        ? 'attention'
        : 'neutral';
  }
  actions(row: KnowledgeIndexView) {
    const view = this.state.view();
    if (view.activeKnown && view.active?.id === row.id) return [];
    const unknown = view.unknown;
    return this.canManage()
      ? availableIndexActions(row).filter(
          (action) =>
            !unknown ||
            (unknown.write.operation === 'activate' &&
              unknown.write.targetId === row.id &&
              ['finish', 'restore_previous'].includes(action)),
        )
      : [];
  }
  private async track(work: () => Promise<void>) {
    const done = this.tasks.add();
    try {
      await work();
    } finally {
      done();
    }
  }
  private focusHeading(id: string) {
    afterNextRender(() => this.host.nativeElement.querySelector<HTMLElement>(`#${id}`)?.focus(), {
      injector: this.injector,
    });
  }
  startPlan() {
    this.state.closeReview();
    this.editing.set(true);
    this.focusHeading('index-plan-title');
  }
  providerChanged(value: string) {
    this.providerId.set(value);
    this.modelId.set('');
    this.state.closeReview();
  }
  async prepare() {
    if (!this.providerId() || !this.modelId()) return;
    await this.track(() =>
      this.state.plan({
        workspace_id: this.workspace(),
        domain: this.domain(),
        provider_id: this.providerId(),
        model_id: this.modelId(),
      }),
    );
    if (this.state.view().plan) this.focusHeading('index-plan-title');
  }
  changeModel() {
    this.state.closeReview();
    this.focusHeading('index-plan-title');
  }
  async build() {
    await this.track(() => this.state.build());
    if (!this.state.view().plan) this.editing.set(false);
  }
  async refresh() {
    await this.track(() => this.state.load(this.state.view().page, this.filter()));
  }
  async changeFilter(value: string) {
    this.filter.set(value);
    await this.track(() => this.state.load(1, value));
  }
  async select(id: string) {
    this.editing.set(false);
    await this.track(() => this.state.select(id));
  }
  async review(action: IndexActionName) {
    this.editing.set(false);
    await this.track(() => this.state.reviewAction(action));
    if (this.state.view().review) this.focusHeading('index-action-title');
  }
  async confirm() {
    await this.track(() => this.state.confirmAction());
  }
  async inspect() {
    await this.track(() => this.state.inspectSaved());
  }
  async repeat() {
    this.replayReview.set(false);
    await this.track(() => this.state.repeatSaved());
  }
  async changePage(page: number) {
    await this.track(() => this.state.load(page, this.filter()));
  }
  ngOnDestroy() {
    clearTimeout(this.expiry);
    this.state.dispose();
  }
}
