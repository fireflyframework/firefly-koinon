// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import {
  ChangeDetectionStrategy,
  Component,
  EventEmitter,
  ElementRef,
  Input,
  OnChanges,
  OnDestroy,
  Output,
  PendingTasks,
  effect,
  inject,
  signal,
  computed,
} from '@angular/core';
import {
  KoinonButton,
  KoinonCodeBlock,
  KoinonDatePipe,
  KoinonIcon,
  KoinonSidePanel,
  KoinonSkeleton,
  KoinonTextPipe,
  KoinonValuePipe,
} from '@fireflyframework/koinon-angular';
import type {
  ChatMessage,
  Citation,
  GenerationReceipt,
  PrivateFileReceipt,
  SqlAttemptReceipt,
  NativeReadReceipt,
  NativeReadOrigin,
  SourceReference,
  ToolActivity,
} from '@fireflyframework/koinon-sdk';
import { KoinonOpenUiArtifact } from '@fireflyframework/koinon-angular/chat/evidence';
import { KoinonAnswerAuditState } from './answer-audit-state';
import { KoinonRecordedOrigin } from './recorded-origin';
@Component({
  selector: 'ffk-answer-audit',
  imports: [
    KoinonButton,
    KoinonCodeBlock,
    KoinonDatePipe,
    KoinonIcon,
    KoinonSidePanel,
    KoinonSkeleton,
    KoinonTextPipe,
    KoinonValuePipe,
    KoinonOpenUiArtifact,
    KoinonRecordedOrigin,
  ],
  providers: [KoinonAnswerAuditState],
  templateUrl: './answer-audit.html',
  styleUrl: './answer-audit.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonAnswerAudit implements OnChanges, OnDestroy {
  @Input() open = false;
  @Input() message: ChatMessage | null = null;
  @Input() threadId = '';
  @Output() closed = new EventEmitter<void>();
  @Output() resourceRequested = new EventEmitter<string>();
  @Output() citationSelected = new EventEmitter<Citation>();
  readonly state = inject(KoinonAnswerAuditState);
  private readonly tasks = inject(PendingTasks);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  readonly tabs = ['overview', 'sources', 'execution'] as const;
  readonly tab = signal<'overview' | 'sources' | 'execution'>('overview');
  readonly sourceId = signal('');
  readonly privateId = signal('');
  readonly attemptIndex = signal<number | null>(null);
  readonly readIndex = signal<number | null>(null);
  readonly selectedPrivate = computed(
    () => this.state.audit()?.private_files?.find((file) => file.id === this.privateId()) ?? null,
  );
  readonly citationIndex = signal<number | null>(null);
  readonly selectedSource = computed(
    () => this.state.sources().find((source) => source.id === this.sourceId()) ?? null,
  );
  private scope = '';
  private binding = '';
  private context = this.state.contextSnapshot();
  private static nextId = 0;
  private readonly viewId = 'answer-audit-' + ++KoinonAnswerAudit.nextId;
  receiptId(kind: string, index: number) {
    return this.viewId + '-' + kind + '-' + index;
  }
  pins(values: Record<string, string> | undefined, tables: SqlAttemptReceipt['tables'] = []) {
    const named = new Set(
      (tables ?? []).map((table) => JSON.stringify([table.table_id, table.snapshot_id])),
    );
    return Object.entries(values ?? {}).filter((pin) => !named.has(JSON.stringify(pin)));
  }
  resultId(index: number) {
    return this.viewId + '-result-' + index;
  }
  tabTitle(tab: 'overview' | 'sources' | 'execution') {
    return { overview: 'Overview', sources: 'Sources', execution: 'Execution' }[tab];
  }
  tabId(tab: string) {
    return this.viewId + '-tab-' + tab;
  }
  panelId(tab: string) {
    return this.viewId + '-panel-' + tab;
  }
  tabKeys(event: KeyboardEvent, index: number) {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
    event.preventDefault();
    const next =
      event.key === 'Home'
        ? 0
        : event.key === 'End'
          ? 2
          : (index + (event.key === 'ArrowRight' ? 1 : -1) + 3) % 3;
    this.tab.set(this.tabs[next]);
    const buttons =
      this.host.nativeElement.querySelectorAll<HTMLButtonElement>('.audit-tabs [role=tab]');
    buttons[next]?.focus();
  }
  selectSource(id: string) {
    this.sourceId.set(id);
    this.privateId.set('');
    this.citationIndex.set(null);
  }
  selectCitation(index: number) {
    this.citationIndex.set(index);
    this.privateId.set('');
    this.attemptIndex.set(null);
    this.readIndex.set(null);
    this.sourceId.set('');
  }
  selectedCitation() {
    const index = this.citationIndex();
    return index === null ? null : (this.fallbackCitations()[index] ?? null);
  }
  constructor() {
    effect(() => {
      const scope = this.state.scopeKey(),
        context = this.state.contextSnapshot();
      if (this.open && this.scope && (this.scope !== scope || this.context !== context))
        this.close();
    });
    effect(() => {
      if (
        this.tab() !== 'sources' ||
        !this.open ||
        this.state.auditPending() ||
        this.state.manifestPending() ||
        this.state.auditError() ||
        this.state.manifestError() ||
        this.sourceId() ||
        this.privateId() ||
        this.citationIndex() !== null ||
        this.attemptIndex() !== null ||
        this.readIndex() !== null ||
        this.state.selected()
      )
        return;
      const sources = this.state.sources(),
        files = this.state.audit()?.private_files ?? [];
      if (sources.length + files.length + this.fallbackCitations().length !== 1) return;
      if (sources.length) this.selectSource(sources[0].id);
      else if (files.length) this.selectPrivate(files[0].id);
    });
  }
  private clearSelection() {
    this.privateId.set('');
    this.sourceId.set('');
    this.citationIndex.set(null);
    this.attemptIndex.set(null);
    this.readIndex.set(null);
  }
  ngOnChanges() {
    const message = this.message;
    const binding =
      this.open && message
        ? JSON.stringify([this.threadId, message.id, message.run_id ?? '', message.status])
        : '';
    if (binding === this.binding) return;
    this.binding = binding;
    this.tab.set('overview');
    this.clearSelection();
    this.state.clear();
    this.scope = this.state.scopeKey();
    this.context = this.state.contextSnapshot();
    if (this.open && message && this.threadId)
      this.tasks.run(() => this.state.open(this.threadId, message));
  }
  ngOnDestroy() {
    this.state.clear();
  }
  close() {
    this.clearSelection();
    this.state.clear();
    this.closed.emit();
  }
  loadPage(page: number) {
    this.tasks.run(() => this.state.loadActivity(page));
  }
  retryActivity() {
    this.loadPage(this.state.activity()?.page ?? 1);
  }
  retryAudit() {
    this.tasks.run(() => this.state.loadAudit());
  }
  selectPrivate(id: string) {
    this.privateId.set(id);
    this.sourceId.set('');
    this.citationIndex.set(null);
  }
  sourceComplete() {
    const audit = this.state.audit();
    return audit
      ? (audit.source_provenance_complete ?? null)
      : (this.state.manifest()?.complete ?? null);
  }
  provider(kind: GenerationReceipt['provider_kind']) {
    return { ollama: 'Ollama', openai: 'OpenAI', anthropic: 'Anthropic' }[kind];
  }
  generationStatus(value: GenerationReceipt['status']) {
    return value === 'completed'
      ? 'Completed'
      : value === 'failed'
        ? 'Failed'
        : value === 'started'
          ? 'Started'
          : 'Not recorded';
  }
  privateAvailability(value: PrivateFileReceipt['availability']) {
    return {
      available: 'Available',
      expired: 'Expired',
      deleted: 'Deleted',
      changed: 'File has changed',
      unavailable: 'Unavailable',
    }[value];
  }
  retrySources() {
    this.tasks.run(() => this.state.loadManifest());
  }
  selectAttempt(index: number) {
    this.state.closeResult();
    this.readIndex.set(null);
    this.attemptIndex.update((current) => (current === index ? null : index));
  }
  selectRead(index: number) {
    this.state.closeResult();
    this.attemptIndex.set(null);
    this.readIndex.update((current) => (current === index ? null : index));
  }
  select(row: ToolActivity) {
    this.attemptIndex.set(null);
    this.readIndex.set(null);
    if (this.state.selected()?.call_id === row.call_id) this.state.closeResult();
    else this.state.selectResult(row);
  }
  query() {
    const result = this.state.result();
    return result?.kind === 'query' ? result.data : null;
  }
  datasetTitle(attempt: SqlAttemptReceipt) {
    return (
      this.state
        .sources()
        .find((source) => source.kind === 'dataset' && source.asset_id === attempt.dataset_id)
        ?.title ?? null
    );
  }
  readTitle(read: NativeReadReceipt) {
    const source = this.state.sources().find((row) => this.matchesRead(row, read));
    if (source) return source.title;
    if (read.domain === 'knowledge') return null;
    return read.origin?.original_filename ?? read.origin?.connection_name ?? null;
  }
  executionKind(value: SqlAttemptReceipt['execution_kind']) {
    return value === 'imported_snapshot'
      ? 'Imported snapshot execution'
      : value === 'computed'
        ? 'Computed execution'
        : 'Not recorded';
  }
  readKind(value: NativeReadReceipt['read_kind']) {
    const labels: Record<string, string> = {
      indexed_document: 'Indexed document content',
      document_extraction: 'Recorded document extraction',
      knowledge_version: 'Published knowledge content',
      metadata: 'Metadata',
    };
    return labels[value ?? ''] ?? 'Not recorded';
  }
  readDomain(value: NativeReadReceipt['domain']) {
    return value === 'documents'
      ? 'Document read'
      : value === 'knowledge'
        ? 'Published knowledge read'
        : 'Structured data read';
  }
  sourceKind(value: NativeReadReceipt['domain']) {
    return value === 'documents'
      ? 'document'
      : value === 'knowledge'
        ? 'knowledge_version'
        : 'dataset';
  }
  sqlOrigins(attempt: SqlAttemptReceipt) {
    const seen = new Set<string>(),
      origins: NativeReadOrigin[] = [];
    const fields: (keyof NativeReadOrigin)[] = [
      'original_filename',
      'sheet_or_json_path',
      'connection_id',
      'connection_name',
      'database',
      'schema',
      'table',
    ];
    for (const read of this.state.audit()?.native_reads ?? []) {
      if (read.result_id !== attempt.result_id || read.domain !== 'structured') continue;
      const generation = read.generation_id ?? null,
        expected = attempt.generation_id ?? null,
        dataset = attempt.dataset_id ?? null;
      if (generation !== null && expected !== null && generation !== expected) continue;
      if (dataset !== null && read.entity_id !== dataset) continue;
      const origin = read.origin;
      if (!origin) continue;
      const values = fields.map((field) => origin[field] ?? null);
      if (!values.some(Boolean)) continue;
      const key = JSON.stringify(values);
      if (!seen.has(key)) {
        seen.add(key);
        origins.push(origin);
      }
    }
    return origins;
  }
  sourceReads(source: SourceReference) {
    return (this.state.audit()?.native_reads ?? []).filter((read) =>
      this.matchesRead(source, read),
    );
  }
  private matchesRead(source: SourceReference, read: NativeReadReceipt) {
    if (this.sourceKind(read.domain) !== source.kind || read.entity_id !== source.asset_id)
      return false;
    if (source.kind === 'dataset')
      return !!source.snapshot_id && (read.snapshot_ids ?? []).includes(source.snapshot_id);
    if (source.kind === 'knowledge_version')
      return (
        !!source.knowledge_version_id &&
        read.knowledge_version_id === source.knowledge_version_id &&
        read.knowledge_version === source.knowledge_version
      );
    return (
      !!source.source_version_id &&
      !!source.extraction_id &&
      read.source_version_id === source.source_version_id &&
      read.extraction_id === source.extraction_id
    );
  }
  sourceOrigins(source: SourceReference) {
    const seen = new Set<string>();
    const origins: (NativeReadOrigin | null)[] = [];
    for (const read of this.sourceReads(source)) {
      const origin = read.origin ?? null;
      const key = JSON.stringify(origin);
      if (!seen.has(key)) {
        seen.add(key);
        origins.push(origin);
      }
    }
    return origins;
  }
  revisionLabel(source: SourceReference) {
    if (source.used_revision?.startsWith('knowledge-content-sha256:'))
      return 'Knowledge content fingerprint';
    if (source.used_revision?.startsWith('source-part-sha256:'))
      return 'Recorded passage fingerprint';
    return source.used_revision?.startsWith('chunk-sha256:')
      ? 'Passage fingerprint'
      : 'Used revision';
  }
  currentRevisionLabel(source: SourceReference) {
    return source.current_revision?.startsWith('chunk-sha256:')
      ? 'Current passage fingerprint'
      : 'Current revision';
  }
  sourceState(source: SourceReference) {
    return source.availability === 'available'
      ? 'Available'
      : source.availability === 'changed'
        ? 'Source has changed'
        : 'Revision not verified';
  }
  status(value: ChatMessage['status']) {
    return {
      queued: 'Queued',
      running: 'Running',
      completed: 'Completed',
      failed: 'Failed',
      cancelled: 'Stopped',
    }[value];
  }
  tool(value: ToolActivity['tool_name']) {
    return (
      {
        search_knowledge: 'Search knowledge',
        inspect_schema: 'Inspect data structure',
        query_dataset: 'Query data',
        search_private_attachments: 'Read attached files',
        propose_catalog_update: 'Propose a catalog edit',
      }[value] ?? 'Recorded tool'
    );
  }
  outcome() {
    const value: string = this.message?.answer_policy?.outcome ?? '';
    const labels: Record<string, string> = {
      grounded: 'Grounded in recorded evidence',
      refused: 'Answer withheld',
      review_required: 'Review required',
    };
    return labels[value] ?? 'Not recorded';
  }
  fallbackCitations() {
    return this.message?.run_id || this.state.sources().length
      ? []
      : (this.message?.citations ?? []);
  }
}
