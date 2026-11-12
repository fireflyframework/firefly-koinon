// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { DOCUMENT } from '@angular/common';
import { A11yModule } from '@angular/cdk/a11y';
import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  EventEmitter,
  Injector,
  Output,
  PendingTasks,
  afterNextRender,
  computed,
  effect,
  inject,
  signal,
  untracked,
} from '@angular/core';
import {
  KoinonClientContext,
  KoinonDatePipe,
  KoinonFacade,
  KoinonI18n,
  formatFileSize,
  KoinonTextPipe,
  registerKoinonSpanish,
  type FolderPageState,
} from '@fireflyframework/koinon-angular/workbench/core';
import { KoinonFolderTree } from '@fireflyframework/koinon-angular/workbench/panels';
import type { CatalogEntry } from '@fireflyframework/koinon-sdk';
import { KoinonSourceAccounts } from './source-accounts';
import { KoinonSourceMappings } from './source-mappings';
import { KoinonSourceBrowser, type SourceSelection } from './source-browser';
import { SOURCE_SPANISH } from './source-spanish';
import type { Destination, MappingPolicy, SourceSchedule } from './mapping-contracts';
registerKoinonSpanish(SOURCE_SPANISH);
type Screen = 'list' | 'detail' | 'content' | 'structure' | 'updates' | 'review';
@Component({
  selector: 'ffk-synchronization-page',
  imports: [A11yModule, KoinonTextPipe, KoinonDatePipe, KoinonFolderTree, KoinonSourceBrowser],
  providers: [KoinonSourceAccounts, KoinonSourceMappings],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './synchronization-page.html',
  styleUrls: ['./source-controls.scss', './synchronization-page.scss'],
})
export class KoinonSynchronizationPage {
  readonly f = inject(KoinonFacade);
  private readonly i18n = inject(KoinonI18n);
  readonly accounts = inject(KoinonSourceAccounts);
  readonly state = inject(KoinonSourceMappings);
  private readonly clients = inject(KoinonClientContext);
  private readonly tasks = inject(PendingTasks);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  private readonly injector = inject(Injector);
  @Output() libraryRequested = new EventEmitter<void>();
  @Output() accountsRequested = new EventEmitter<void>();
  readonly summaryOpen =
    inject(DOCUMENT).defaultView?.matchMedia?.('(min-width: 761px)').matches ?? true;
  readonly screen = signal<Screen>('list');
  readonly source = signal<SourceSelection | null>(null);
  readonly connectionId = signal('');
  readonly mode = signal<'document' | 'dataset'>('document');
  readonly hierarchy = signal<'preserve' | 'flatten'>('preserve');
  readonly recursive = signal(true);
  readonly formats = signal<string[]>([]);
  readonly destination = signal<Destination | null>(null);
  readonly destinationName = signal('');
  readonly destinations = signal<CatalogEntry[]>([]);
  readonly removal = signal<'retire' | 'pause_for_review'>('pause_for_review');
  readonly scheduleKind = signal<'manual' | 'interval' | 'daily' | 'weekly'>('manual');
  readonly intervalMinutes = signal(15);
  readonly timezone = signal(Intl.DateTimeFormat().resolvedOptions().timeZone);
  readonly localTime = signal('09:00');
  readonly weekdays = signal<number[]>([1]);
  readonly validation = signal('');
  readonly creating = signal(false);
  readonly createdFolder = signal<CatalogEntry | null>(null);
  folderName = '';
  private confirmationTrigger?: HTMLElement;
  readonly confirmation = signal<'pause' | 'retire' | 'abandon' | 'cancel' | null>(null);
  readonly account = computed(
    () => this.accounts.page().items.find((row) => row.id === this.connectionId()) ?? null,
  );
  readonly availableFormats = computed(
    () =>
      this.accounts.capabilities()?.formats.filter((format) => format.mode === this.mode()) ?? [],
  );
  readonly steps = [
    { screen: 'content', label: 'Content' },
    { screen: 'structure', label: 'Structure' },
    { screen: 'updates', label: 'Updates' },
    { screen: 'review', label: 'Review' },
  ] as const;
  readonly days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
  readonly stepNumber = computed(
    () => this.steps.findIndex((step) => step.screen === this.screen()) + 1,
  );
  private readonly draftIdentity = signal('');
  private readonly draftContext = signal<ReturnType<KoinonFacade['context']>>(null);
  readonly authorized = computed(
    () =>
      this.draftIdentity() === this.state.identity() &&
      this.draftContext() === this.f.context() &&
      !this.f.authRequired(),
  );
  private loadedIdentity = '';
  private loadedContext: ReturnType<KoinonFacade['context']> = null;
  constructor() {
    effect(() => {
      this.state.identity();
      this.f.context();
      this.state.accessChanged();
      this.resetDraft();
      this.screen.set('list');
      const identity = this.state.identity(),
        context = this.f.context();
      if (
        !this.f.authRequired() &&
        (identity !== this.loadedIdentity || context !== this.loadedContext)
      ) {
        this.loadedIdentity = identity;
        this.loadedContext = context;
        untracked(() => this.reload());
      }
    });
  }
  reload() {
    this.tasks.run(async () => {
      await Promise.all([this.accounts.load(), this.accounts.loadCapabilities()]);
      if (this.accounts.capabilities()?.synchronization_available) {
        await this.state.load();
        await this.state.restoreRecovery();
        const policy = this.state.preparedPolicy();
        if (policy) {
          this.connectionId.set(policy.connection_id);
          this.mode.set(policy.mode);
          this.hierarchy.set(policy.hierarchy);
          this.recursive.set(policy.recursive);
          this.formats.set([...policy.formats]);
          this.removal.set(policy.removal_policy);
          this.destination.set(policy.destination);
          this.scheduleKind.set(
            policy.schedule.kind === 'calendar'
              ? policy.schedule.weekdays.length === 7
                ? 'daily'
                : 'weekly'
              : policy.schedule.kind,
          );
          if (policy.schedule.kind === 'interval')
            this.intervalMinutes.set(policy.schedule.seconds / 60);
          if (policy.schedule.kind === 'calendar') {
            this.timezone.set(policy.schedule.timezone);
            this.localTime.set(policy.schedule.time);
            this.weekdays.set([...policy.schedule.weekdays]);
          }
        }
        if (this.state.preparation() || this.state.preparationUncertain() || this.state.review())
          this.show('review');
        else if (this.state.detail()) this.show('detail');
      }
    });
  }
  private resetDraft() {
    this.draftIdentity.set(this.state.identity());
    this.draftContext.set(this.f.context());
    this.source.set(null);
    this.connectionId.set('');
    this.destination.set(null);
    this.destinationName.set('');
    this.destinations.set([]);
    this.formats.set([]);
    this.recursive.set(true);
    this.mode.set('document');
    this.hierarchy.set('preserve');
    this.removal.set('pause_for_review');
    this.scheduleKind.set('manual');
    this.validation.set('');
    this.confirmation.set(null);
    this.folderName = '';
    this.createdFolder.set(null);
    this.creating.set(false);
  }
  begin() {
    if (
      !this.accounts.capabilities()?.synchronization_available ||
      this.state.loading() ||
      this.state.uncertain()
    )
      return;
    this.state.close();
    this.resetDraft();
    this.mode.set(this.accounts.capabilities()?.modes[0] ?? 'document');
    this.formats.set(this.availableFormats().map((item) => item.extension));
    this.show('content');
  }
  show(screen: Screen) {
    this.screen.set(screen);
    this.validation.set('');
    afterNextRender(() => this.host.nativeElement.querySelector<HTMLElement>('h1')?.focus(), {
      injector: this.injector,
    });
  }
  chooseAccount(id: string) {
    this.connectionId.set(id);
    this.source.set(null);
    this.changed();
  }
  chooseSource(value: SourceSelection | null) {
    this.source.set(value);
    if (value?.root.kind === 'file') this.recursive.set(false);
    this.changed();
  }
  changed() {
    this.state.selectionChanged();
    this.validation.set('');
  }
  setMode(mode: 'document' | 'dataset') {
    this.mode.set(mode);
    this.formats.set(this.availableFormats().map((item) => item.extension));
    this.changed();
  }
  toggleFormat(value: string, checked: boolean) {
    this.formats.update((rows) =>
      checked ? [...new Set([...rows, value])] : rows.filter((row) => row !== value),
    );
    this.changed();
  }
  toggleDay(day: number, checked: boolean) {
    this.weekdays.update((days) =>
      checked ? [...new Set([...days, day])].sort() : days.filter((value) => value !== day),
    );
    this.changed();
  }
  next() {
    if (this.screen() === 'content') {
      if (
        !this.source() ||
        !this.account() ||
        this.account()?.status !== 'connected' ||
        !this.formats().length
      ) {
        this.invalid('Choose a source and at least one supported file format.');
        return;
      }
      this.show('structure');
    } else if (this.screen() === 'structure') {
      if (!this.destination()) {
        this.invalid('Choose a writable destination folder.');
        return;
      }
      this.show('updates');
    }
  }
  back() {
    const index = this.stepNumber();
    if (index > 1) this.show(this.steps[index - 2].screen);
    else this.show('list');
  }
  private invalid(message: string) {
    this.validation.set(message);
    afterNextRender(
      () => this.host.nativeElement.querySelector<HTMLElement>('[role=alert]')?.focus(),
      { injector: this.injector },
    );
  }
  private schedule(): SourceSchedule | null {
    if (this.scheduleKind() === 'manual') return { kind: 'manual' };
    if (this.scheduleKind() === 'interval') {
      const seconds = this.intervalMinutes() * 60,
        bounds = this.accounts.capabilities()?.schedule;
      if (
        !bounds ||
        !Number.isInteger(seconds) ||
        seconds < bounds.min_interval_seconds ||
        seconds > bounds.max_interval_seconds
      ) {
        this.invalid('Choose an interval within the supported limits.');
        return null;
      }
      return { kind: 'interval', seconds };
    }
    if (!/^([01]\d|2[0-3]):[0-5]\d$/.test(this.localTime())) {
      this.invalid('Choose a valid local time.');
      return null;
    }
    try {
      new Intl.DateTimeFormat('en', { timeZone: this.timezone() }).format();
    } catch {
      this.invalid('Choose a valid IANA timezone.');
      return null;
    }
    const weekdays = this.scheduleKind() === 'daily' ? [1, 2, 3, 4, 5, 6, 7] : this.weekdays();
    if (!weekdays.length) {
      this.invalid('Choose at least one weekday.');
      return null;
    }
    return {
      kind: 'calendar',
      timezone: this.timezone(),
      time: this.localTime(),
      weekdays: [...weekdays],
    };
  }
  private policy(): MappingPolicy | null {
    const source = this.source(),
      destination = this.destination(),
      schedule = this.schedule();
    if (!source || !destination || !schedule || !this.authorized()) return null;
    return {
      connection_id: this.connectionId(),
      drive_id: source.driveId,
      root_id: source.root.item_id,
      destination,
      recursive: source.root.kind === 'file' ? false : this.recursive(),
      schema_version: 1,
      mode: this.mode(),
      hierarchy: this.hierarchy(),
      excluded_ids: source.root.kind === 'file' ? [] : source.excluded.map((item) => item.item_id),
      formats: this.formats(),
      schedule,
      removal_policy: this.removal(),
    };
  }
  prepareReview() {
    const policy = this.policy();
    if (!policy) return;
    this.tasks.run(async () => {
      this.show('review');
      if (await this.state.beginPreparation(policy)) await this.continuePreparation();
    });
  }
  resumePreparation() {
    this.tasks.run(() => this.continuePreparation());
  }
  private async continuePreparation() {
    const generation = this.state.generationVersion();
    while (
      this.screen() === 'review' &&
      this.state.canResumePreparation() &&
      generation === this.state.generationVersion()
    ) {
      if (!(await this.state.resumePreparation())) break;
    }
  }
  reviewPreparation() {
    this.tasks.run(() => this.state.reviewPreparation());
  }
  checkPreparation() {
    this.tasks.run(() => this.state.checkPreparation());
  }
  confirmChange() {
    const action = this.confirmation();
    this.confirmation.set(null);
    if (action === 'abandon') this.tasks.run(() => this.state.abandonPreparation());
    else if (action === 'cancel') this.tasks.run(() => this.state.runCommand('cancel'));
    else if (action) this.command(action);
  }
  phaseLabel(state: string) {
    const labels: Record<string, string> = {
      scanning: 'Finding selected content…',
      verifying: 'Verifying selected content…',
      checking_changes: 'Checking for changes…',
      complete: 'Preparation complete',
      blocked: 'Preparation needs attention',
      stale: 'The selection changed. Prepare it again.',
      cleaning: 'Cleaning preparation…',
      abandoned: 'Preparation abandoned',
      expired: 'Preparation expired',
      queued: 'Queued',
      running: 'Running',
      reconciling: 'Checking the result',
      reconnect_required: 'Reconnect required',
      succeeded: 'Completed',
      partial: 'Completed with issues',
      failed: 'Failed',
      cancelled: 'Cancelled',
      observed: 'Discovered',
      downloading: 'Downloading',
      processing: 'Processing',
      synchronized: 'Synchronized',
      searchable: 'Searchable',
      skipped: 'Skipped',
      conflict: 'Needs attention',
      retired: 'Retired',
      indeterminate: 'Checking the result',
    };
    return labels[state] ?? 'Needs attention';
  }
  preparationReason(reason: string | null | undefined) {
    const reasons: Record<string, string> = {
      SOURCE_NAME_COLLISION: 'Source files resolve to the same destination path.',
      SOURCE_DESTINATION_COLLISION: 'An item already exists at this destination path.',
      SOURCE_LOCAL_EDIT: 'Local changes were found. Koinon will keep them.',
      SOURCE_CHANGED: 'The selection changed. Prepare it again.',
      SOURCE_AUTHORITY_CHANGED: 'Access changed. Check your account and try again.',
      SOURCE_SCAN_LIMIT_EXCEEDED:
        'The selection exceeds the preparation limit. Choose fewer files.',
      SOURCE_VALIDATION_CAPACITY:
        'Preparation capacity is full. Check your existing preparation before trying again.',
      SOURCE_UNAVAILABLE: 'Source access could not be checked. Try again.',
      SOURCE_VALIDATION_REFRESH_REQUIRED: 'The selection changed. Prepare it again.',
      SOURCE_INVALID_SELECTION: 'Choose a supported file or folder.',
    };
    return reasons[reason ?? ''] ?? '';
  }
  approve() {
    const generation = this.state.generationVersion(),
      mappingId = this.state.reviewReceipt()?.mapping_id;
    if (!mappingId) return;
    const identity = this.state.identity(),
      context = this.f.context();
    this.tasks.run(async () => {
      const accepted = await this.state.approve();
      if (
        !accepted ||
        generation !== this.state.generationVersion() ||
        this.state.detail()?.id !== mappingId ||
        identity !== this.state.identity() ||
        context !== this.f.context()
      )
        return;
      this.show('detail');
      await this.state.loadRuns();
    });
  }
  checkRequest() {
    this.tasks.run(async () => {
      if (!(await this.state.checkOperation())) return;
      if (this.state.review() || this.state.preparation()) this.show('review');
      else if (this.state.detail()) this.show('detail');
    });
  }
  open(id: string) {
    this.tasks.run(async () => {
      if (await this.state.open(id)) {
        this.show('detail');
        await this.state.loadRuns();
      }
    });
  }
  edit() {
    const current = this.state.detail();
    if (!current) return;
    this.resetDraft();
    this.connectionId.set(current.policy.connection_id);
    this.mode.set(current.policy.mode);
    this.hierarchy.set(current.policy.hierarchy);
    this.recursive.set(current.policy.recursive);
    this.formats.set([...current.policy.formats]);
    this.removal.set(current.policy.removal_policy);
    const schedule = current.policy.schedule;
    this.scheduleKind.set(
      schedule.kind === 'calendar'
        ? schedule.weekdays.length === 7
          ? 'daily'
          : 'weekly'
        : schedule.kind,
    );
    if (schedule.kind === 'interval') this.intervalMinutes.set(schedule.seconds / 60);
    if (schedule.kind === 'calendar') {
      this.timezone.set(schedule.timezone);
      this.localTime.set(schedule.time);
      this.weekdays.set([...schedule.weekdays]);
    }
    this.show('content');
  }
  confirm(action: 'pause' | 'retire' | 'abandon' | 'cancel', event: Event) {
    this.confirmationTrigger = event.currentTarget as HTMLElement;
    this.confirmation.set(action);
  }
  cancelConfirmation(event?: Event) {
    event?.preventDefault();
    event?.stopPropagation();
    this.confirmation.set(null);
    this.confirmationTrigger?.focus();
  }
  command(action: 'sync' | 'pause' | 'resume' | 'retire') {
    this.confirmation.set(null);
    this.tasks.run(() => this.state.command(action));
  }
  readonly canSelect = (entry: CatalogEntry) => {
    const permissions = new Set([
      ...this.f.tenantPermissions(),
      ...(this.f.context()?.workspace_permissions?.[entry.workspace_id ?? ''] ?? []),
    ]);
    return (
      ['collection', 'corpus'].includes(entry.kind) &&
      entry.status !== 'archived' &&
      !!entry.workspace_id &&
      !!entry.project_id &&
      permissions.has('catalog:write') &&
      permissions.has('ingest:write')
    );
  };
  readonly loadChildren = async (parentId: string, page = 1): Promise<FolderPageState | null> => {
    const identity = this.state.identity(),
      context = this.f.context(),
      parent = this.destinations().find((entry) => entry.id === parentId);
    let result;
    try {
      result = await this.clients.get().catalog.list(this.f.tenantId(), {
        parent_id: parentId || undefined,
        kind: parentId ? undefined : 'workspace',
        view: 'library',
        page,
        page_size: 50,
        ...(parent?.workspace_id ? { workspace_id: parent.workspace_id } : {}),
      });
    } catch (error) {
      if (identity === this.state.identity() && context === this.f.context()) {
        this.destinations.set([]);
        this.destination.set(null);
        this.destinationName.set('');
        this.state.invalidateReview();
      }
      throw error;
    }
    if (identity !== this.state.identity() || context !== this.f.context()) return null;
    this.destinations.update((rows) => [
      ...new Map([...rows, ...result.items].map((entry) => [entry.id, entry])).values(),
    ]);
    return {
      ids: result.items.map((item) => item.id),
      page: result.page,
      pages: result.pages,
      total: result.total,
    };
  };
  chooseDestination(id: string) {
    const entry = this.destinations().find((row) => row.id === id);
    if (!entry || !this.canSelect(entry)) {
      this.invalid('You cannot add knowledge here. Choose another destination.');
      return;
    }
    this.destination.set({
      workspace_id: entry.workspace_id!,
      project_id: entry.project_id!,
      parent_id: id,
    });
    this.destinationName.set(entry.name);
    this.createdFolder.set(null);
    this.changed();
  }
  createFolder() {
    const destination = this.destination(),
      name = this.folderName.trim(),
      identity = this.state.identity(),
      context = this.f.context();
    if (!destination || !name || this.creating()) return;
    this.creating.set(true);
    this.tasks.run(async () => {
      try {
        const entry = await this.clients.get().catalog.create(this.f.tenantId(), {
          kind: 'collection',
          name,
          parent_id: destination.parent_id,
        });
        if (identity !== this.state.identity() || context !== this.f.context()) return;
        this.destinations.update((rows) => [...rows, entry]);
        this.createdFolder.set(entry);
        this.folderName = '';
        this.validation.set('Folder created. Select it to confirm your destination.');
      } catch {
        if (identity === this.state.identity() && context === this.f.context())
          this.invalid('The folder could not be created. Try again.');
      } finally {
        if (identity === this.state.identity() && context === this.f.context())
          this.creating.set(false);
      }
    });
  }
  fileSize(bytes: number) {
    return formatFileSize(bytes, this.i18n.preferences().locale);
  }
  previewAction(action: string) {
    const labels: Record<string, string> = {
      create: 'Create',
      replace: 'Replace',
      move: 'Move',
      skip: 'Skip',
      conflict: 'Conflict',
      retire: 'Retire',
    };
    return labels[action] ?? 'Needs attention';
  }
  scheduleLabel(schedule: SourceSchedule) {
    return schedule.kind === 'manual'
      ? 'Only when I start a sync'
      : schedule.kind === 'interval'
        ? 'Every…'
        : schedule.weekdays.length === 7
          ? 'Daily'
          : 'Weekly';
  }
}
