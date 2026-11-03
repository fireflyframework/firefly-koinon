// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
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
  type OnDestroy,
} from '@angular/core';
import { UploadObservationLoop } from '../services/upload-observation-loop';
import { formatFileSize } from '@fireflyframework/koinon-angular/workbench/core';
import { DecimalPipe } from '@angular/common';
import type { FileBatchView, Page } from '@fireflyframework/koinon-sdk';
import { KoinonFacade } from '@fireflyframework/koinon-angular/workbench/core';
import { KoinonClientContext } from '@fireflyframework/koinon-angular/workbench/core';
import {
  retainedUploadAccess,
  type RetainedUploadOperation,
  type RetainedUploadRequest,
  type RetainedUploadScope,
} from '../services/library-retained-uploads-contract';
import { RetainedUploadJournal } from '../services/library-retained-uploads-journal';
import { RetainedUploadsState } from '../services/library-retained-uploads-state';
import { KoinonFileTypeIcon } from '@fireflyframework/koinon-angular/workbench/core';
import { KoinonBadge } from '@fireflyframework/koinon-angular/workbench/core';
import { statusTone } from '@fireflyframework/koinon-angular/workbench/core';
import { KoinonButton } from '@fireflyframework/koinon-angular/workbench/core';
import { KoinonSkeleton } from '@fireflyframework/koinon-angular/workbench/core';
import { KoinonPagination } from '../molecules/pagination';
import {
  KoinonI18n,
  KoinonDatePipe,
  KoinonTextPipe,
  registerKoinonSpanish,
} from '@fireflyframework/koinon-angular/workbench/core';
import {
  uploadProcessingHelp,
  uploadRecoveryReason,
} from '../services/library-upload-recovery-messages';
import { RETAINED_UPLOADS_SPANISH } from './library-retained-uploads-spanish';
registerKoinonSpanish(RETAINED_UPLOADS_SPANISH);
@Component({
  selector: 'ffk-library-retained-uploads-panel',
  imports: [
    KoinonFileTypeIcon,
    DecimalPipe,
    KoinonBadge,
    KoinonButton,
    KoinonSkeleton,
    KoinonPagination,
    KoinonDatePipe,
    KoinonTextPipe,
  ],
  templateUrl: './library-retained-uploads-panel.html',
  styleUrl: './library-retained-uploads-panel.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonLibraryRetainedUploadsPanel implements OnDestroy {
  @Output() readonly folderRequested = new EventEmitter<string>();
  @Output() readonly resourceRequested = new EventEmitter<string>();
  readonly f = inject(KoinonFacade);
  private readonly i18n = inject(KoinonI18n);
  private readonly clients = inject(KoinonClientContext);
  private readonly tasks = inject(PendingTasks);
  private readonly injector = inject(Injector);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  private expiry?: ReturnType<typeof setTimeout>;
  readonly now = signal(Date.now());
  private scope = (): RetainedUploadScope => ({
    owner: this.f.authRequired() ? null : this.f.context(),
    subject: this.f.context()?.subject ?? '',
    tenantId: this.f.tenantId(),
    clientRevision: this.clients.revision(),
    transport: this.clients.getTransport(),
    accessRevision: this.now(),
    allowed:
      !this.f.authRequired() &&
      retainedUploadAccess(
        this.f.context(),
        this.f.tenantId(),
        undefined,
        Math.max(this.now(), Date.now()),
      ).read,
  });
  private journal() {
    try {
      return new RetainedUploadJournal(sessionStorage);
    } catch {
      return new RetainedUploadJournal({
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
  readonly state = new RetainedUploadsState({
    scope: this.scope,
    client: () => this.clients.get(),
    journal: this.journal(),
    access: (batch) =>
      retainedUploadAccess(
        this.f.context(),
        this.f.tenantId(),
        batch.destination.workspace_id,
        Math.max(this.now(), Date.now()),
      ),
    denied: (status) => {
      if (status === 401) this.f.authRequired.set(true);
    },
  });
  readonly allowed = computed(() => this.scope().allowed);
  readonly page = computed<Page<FileBatchView>>(() => {
    const v = this.state.view();
    return {
      items: v.rows,
      total: v.total,
      page: v.page,
      page_size: 25,
      pages: Math.max(1, Math.ceil(v.total / 25)),
    };
  });
  readonly batchOperations = ['submit', 'cancel'] as const;
  readonly labels: Record<RetainedUploadOperation, string> = {
    recover_original: 'Check retained original',
    reconcile: 'Inspect processing outcome',
    submit: 'Submit for processing',
    cancel: 'Request cancellation',
    retry_processing: 'Retry processing',
    finalize_publication: 'Finish publication',
    acknowledge_commit: 'Record completed import',
  };
  readonly processingHelp = uploadProcessingHelp;
  readonly recoveryReason = uploadRecoveryReason;
  readonly technicalAccess = computed(
    () =>
      this.f
        .context()
        ?.memberships.some(
          (m) =>
            m.subject === this.f.context()?.subject &&
            m.tenant_id === this.f.tenantId() &&
            m.workspace_id === null &&
            m.active &&
            m.role === 'admin' &&
            (m.expires_at == null || Date.parse(m.expires_at) > Math.max(this.now(), Date.now())),
        ) ?? false,
  );
  readonly explanations: Record<RetainedUploadOperation, string> = {
    recover_original:
      'This reads the original retained by the server to verify its size and checksum. It can mark that original as received. It does not upload a file or start processing.',
    reconcile:
      'This inspects the native processing outcome and records a verified receipt when one exists. It does not repeat the import. An unresolved outcome remains unresolved.',
    submit:
      'This submits the currently staged originals for processing. Every original must be received first. Queued processing is separate from searchable knowledge.',
    retry_processing:
      'Process the saved file again. This may use your configured AI services. Earlier attempts remain in the activity history.',
    finalize_publication:
      'This finishes publication of an already prepared result. It does not authorize starting a new processing attempt if the result changes.',
    acknowledge_commit:
      'This records the verified import that already completed. It does not import the original again.',
    cancel:
      'This requests cancellation of pending work. Published knowledge and already committed effects can remain. It does not delete the retained history.',
  };
  private readonly visible = signal(
    typeof document === 'undefined' || document.visibilityState !== 'hidden',
  );
  private readonly visibilityChanged = () => {
    this.state.syncScope();
    this.visible.set(document.visibilityState !== 'hidden');
    this.polling.update();
    const v = this.state.view();
    if (this.visible() && this.allowed() && !v.busy && !v.review && !Object.keys(v.recovery).length)
      void this.refresh();
  };
  private readonly polling = new UploadObservationLoop({
    active: () => {
      const v = this.state.view();
      return (
        this.allowed() &&
        !v.denied &&
        !v.busy &&
        !v.review &&
        !Object.keys(v.recovery).length
      );
    },
    visible: () => this.visible(),
    interval: () => {
      const v = this.state.view();
      const rows = v.selected ? [v.selected] : v.rows;
      return rows.some(batch => ['staging', 'queued', 'running'].includes(batch.status)) ? 5000 : 30000;
    },
    read: () => this.refresh(),
  });
  constructor() {
    if (typeof document !== 'undefined') {
      document.addEventListener('visibilitychange', this.visibilityChanged);
      window.addEventListener('focus', this.visibilityChanged);
    }
    effect(() => {
      this.visible();
      this.allowed();
      this.state.view();
      this.polling.update();
    });
    effect(() => {
      this.scope();
      untracked(() => {
        this.state.syncScope();
        this.polling.reset();
        if (this.scope().allowed) void this.track(() => this.state.load(1));
      });
    });
    effect(() => {
      this.now();
      clearTimeout(this.expiry);
      const times = (this.f.context()?.memberships ?? [])
        .map((m) => (m.expires_at ? Date.parse(m.expires_at) : NaN))
        .filter((time) => time > Date.now());
      if (times.length)
        this.expiry = setTimeout(
          () => this.now.set(Date.now()),
          Math.min(Math.max(1, Math.min(...times) - Date.now() + 1), 2147483647),
        );
    });
  }
  private async track(work: () => Promise<void>) {
    const done = this.tasks.add();
    try {
      await work();
    } finally {
      done();
    }
  }
  private focus(id: string) {
    afterNextRender(() => this.host.nativeElement.querySelector<HTMLElement>('#' + id)?.focus(), {
      injector: this.injector,
    });
  }
  status(value: string) {
    return (
      (
        {
          awaiting_upload: 'Original not verified',
          staged: 'Original received',
          staging: 'Awaiting originals',
          queued: 'Queued',
          running: 'Processing',
          reconciling: 'Processing needs review',
          succeeded: 'Processing completed',
          partial: 'Partially completed',
          failed: 'Failed',
          cancelled: 'Cancelled',
          expired: 'Expired',
        } as Record<string, string>
      )[value] ?? 'Not verified'
    );
  }
  technicalCode(value: string | null | undefined) {
    return value && /^[A-Z][A-Z0-9_]{0,63}$/.test(value) ? value : '';
  }
  recoveryStatus(value: string) {
    return (
      (
        {
          absent: 'Not published',
          admitted: 'Publication not confirmed',
          failed: 'Processing failed before publication',
          prepared: 'Ready to publish',
          committed: 'Import completed',
          unknown: 'Not confirmed',
          not_checked: 'Not checked',
          verified: 'Upload confirmed',
          unavailable: 'Original unavailable',
        } as Record<string, string>
      )[value] ?? this.status(value)
    );
  }
  async inspectRecovery(id: string) {
    await this.track(() => this.state.inspectRecovery(id));
    if (this.state.view().recovery[id]) this.focus('upload-recovery-' + id);
  }
  batchStatus(batch: FileBatchView) {
    return batch.status === 'staging' &&
      batch.total_items > 0 &&
      batch.counts['staged'] === batch.total_items
      ? 'Originals received'
      : this.status(batch.status);
  }
  tone(value: string) { return this.state.view().stale || this.state.view().error ? 'attention' as const : statusTone(value); }
  async refresh() {
    const batch = this.state.view().selected;
    await this.track(() =>
      batch ? this.state.select(batch.id) : this.state.load(this.state.view().page),
    );
    return !this.state.view().error && !this.state.view().denied;
  }
  async select(id: string) {
    await this.track(() => this.state.select(id));
    if (this.state.view().selected) this.focus('retained-upload-details');
  }
  async back() {
    this.state.closeDetails();
    await this.track(() => this.state.load(this.state.view().page));
    this.focus('retained-upload-list');
  }
  async changePage(page: number) {
    await this.track(() => this.state.load(page));
  }
  async review(operation: RetainedUploadOperation, itemId?: string) {
    await this.track(() => this.state.review(operation, itemId));
    if (this.state.view().review) this.focus('retained-upload-review');
  }
  async reviewSaved(request: RetainedUploadRequest) {
    await this.track(() => this.state.reviewSaved(request));
    if (this.state.view().review) this.focus('retained-upload-review');
  }
  closeReview() {
    this.state.closeReview();
    this.focus('retained-upload-details');
  }
  async confirm() {
    await this.track(() => this.state.confirm());
    if (!this.state.view().review && this.state.view().selected)
      this.focus('retained-upload-details');
  }
  async receipt(id: string) {
    await this.track(() => this.state.verifyReceipt(id));
  }
  size(value: number) {
    return formatFileSize(value, this.i18n.preferences().locale);
  }
  filename(id: string | null) {
    return this.state.view().items.find((i) => i.id === id)?.filename ?? '';
  }
  ngOnDestroy() {
    clearTimeout(this.expiry);
    this.polling.dispose();
    if (typeof document !== 'undefined') {
      document.removeEventListener('visibilitychange', this.visibilityChanged);
      window.removeEventListener('focus', this.visibilityChanged);
    }
    this.state.dispose();
  }
}
