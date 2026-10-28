// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { KoinonTextPipe } from '@fireflyframework/koinon-angular';
import {
  ChangeDetectionStrategy,
  Component,
  Input,
  Output,
  EventEmitter,
  OnChanges,
  OnDestroy,
  PendingTasks,
  computed,
  inject,
  signal,
} from '@angular/core';
import {
  Renderer,
  RenderNode,
  createLibrary,
  defineComponent,
  injectOpenUiContext,
} from '@openuidev/angular-lang';
import type {
  Column,
  Citation,
  EvidenceResult,
  OpenUIArtifact,
  QueryResponse,
  Presentation,
} from '@fireflyframework/koinon-sdk';
import {
  answerProps,
  evidenceProps,
  validateEvidenceLanguage,
  type EvidenceView,
} from './evidence-language';
import { KoinonEvidenceGroups } from '@fireflyframework/koinon-angular';
import { KoinonEvidenceContext, type EvidenceResolver } from './evidence-context';
import { KoinonEvidenceTable } from '../organisms/evidence-table';
import { KoinonResultChart } from '../organisms/result-chart';
import { KoinonCatalogProposal } from '../organisms/catalog-proposal';
import { KoinonButton } from '@fireflyframework/koinon-angular';
import { KoinonBadge } from '@fireflyframework/koinon-angular';
import { KoinonSkeleton } from '@fireflyframework/koinon-angular';
import { KoinonIcon } from '@fireflyframework/koinon-angular';
import { KoinonCodeBlock } from '@fireflyframework/koinon-angular';
@Component({
  selector: 'ffk-openui-answer',
  imports: [KoinonTextPipe, RenderNode],
  template: `@if (props?.children?.length) {
    <section class="answer-evidence" [attr.aria-label]="'Supporting evidence' | ffkText">
      <openui-render-node
        [value]="openUi.renderNode(props.children || [])"
        [library]="openUi.library"
        [context]="openUi"
      />
    </section>
  }`,
  styles: `
    :host {
      display: block;
      min-width: 0;
    }
    .answer-evidence {
      display: flex;
      flex-direction: column;
      gap: 12px;
      min-width: 0;
    }
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonKnowledgeAnswer {
  @Input() props: { children?: unknown[] } | null = null;
  @Input() renderNode: ((value: unknown) => unknown) | null = null;
  @Input() statementId?: string;
  readonly openUi = injectOpenUiContext();
}
@Component({
  selector: 'ffk-openui-evidence',
  imports: [
    KoinonTextPipe,
    KoinonEvidenceTable,
    KoinonResultChart,
    KoinonCatalogProposal,
    KoinonButton,
    KoinonBadge,
    KoinonSkeleton,
    KoinonIcon,
    KoinonCodeBlock,
  ],
  templateUrl: './evidence-renderer.html',
  styleUrl: './evidence-renderer.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonEvidence implements OnChanges, OnDestroy {
  @Input() props: { resultId?: string; view?: EvidenceView } | null = null;
  @Input() renderNode: ((value: unknown) => unknown) | null = null;
  @Input() statementId?: string;
  readonly context = inject(KoinonEvidenceContext);
  private readonly groups = inject(KoinonEvidenceGroups, { optional: true });
  private readonly owner = {};
  private readonly groupKey = signal('');
  readonly visible = computed(() => {
    if (this.context.mode() === 'audit') return true;
    const result = this.result();
    if (
      result?.kind !== 'proposal' &&
      (result?.kind !== 'query' ||
        !['OK', 'REFINED_OK'].includes(result.data.execution_status ?? '') ||
        !result.data.preview?.length)
    )
      return false;
    return !this.groupKey() || !this.groups || this.groups.visible(this.groupKey(), this.owner);
  });
  private releaseGroup() {
    const key = this.groupKey();
    if (key) this.groups?.release(key, this.owner);
    this.groupKey.set('');
  }
  ngOnDestroy() {
    ++this.request;
    this.releaseGroup();
  }
  private readonly tasks = inject(PendingTasks);
  private request = 0;
  readonly result = signal<EvidenceResult | null>(null);
  readonly error = signal('');
  readonly pending = signal(true);
  readonly selectedQueryView = signal<'table' | 'chart'>('table');
  view: EvidenceView = 'auto';
  readonly query = computed(() => {
    const r = this.result();
    return r?.kind === 'query' ? r.data : null;
  });
  readonly canChart = computed(() => {
    const rows = this.query()?.preview ?? [];
    return (
      rows.length > 0 &&
      rows.length <= 100 &&
      Object.keys(rows[0]).some((key) =>
        rows.every((row) => typeof row[key] === 'number' && Number.isFinite(row[key])),
      )
    );
  });
  readonly schema = computed(() => {
    const r = this.result();
    return r?.kind === 'schema' ? r.data : null;
  });
  readonly search = computed(() => {
    const r = this.result();
    return r?.kind === 'search' ? r.data : null;
  });
  readonly lineage = computed(() => {
    const r = this.result();
    return r?.kind === 'lineage' ? r.data : null;
  });
  readonly attachmentEvidence = computed(() => {
    const result = this.result();
    return result?.kind === 'attachment' ? result.data : null;
  });
  readonly citations = computed(() => {
    const r = this.result();
    return r?.kind === 'search' || r?.kind === 'query' ? (r.data.citations ?? []) : [];
  });
  ngOnChanges() {
    this.tasks.run(() => this.load());
  }
  private async load() {
    const request = ++this.request;
    this.releaseGroup();
    this.result.set(null);
    this.error.set('');
    this.pending.set(true);
    this.selectedQueryView.set('table');
    const props = evidenceProps.safeParse(this.props);
    if (!props.success) {
      this.pending.set(false);
      return;
    }
    this.view = props.data.view ?? 'auto';
    try {
      const result = await this.context.read(props.data.resultId);
      if (request !== this.request) return;
      const supported: Record<string, EvidenceView[]> = {
        query: ['auto', 'table', 'chart', 'citations'],
        search: ['auto', 'table', 'document', 'citations'],
        schema: ['auto', 'table', 'schema'],
        lineage: ['auto', 'table', 'lineage'],
        attachment: ['auto', 'document'],
        proposal: ['auto', 'proposal'],
      };
      if (!supported[result.kind]?.includes(this.view))
        throw new Error('This view is not available for the returned evidence.');
      if (this.groups && this.context.mode() === 'answer') {
        const key =
          result.run_id +
          ':' +
          result.kind +
          ':' +
          (result.kind === 'attachment' ? JSON.stringify(result.data) : result.id);
        this.groups.claim(key, this.owner);
        this.groupKey.set(key);
      }
      this.result.set(result);
    } catch (error) {
      if (request === this.request && !(error instanceof Error && error.name === 'AbortError'))
        this.error.set(
          error instanceof Error ? error.message : 'This evidence could not be opened.',
        );
    } finally {
      if (request === this.request) this.pending.set(false);
    }
  }
  queryRows(query: QueryResponse) {
    return query.preview ?? [];
  }
  chartKind(query: QueryResponse): 'line' | 'bar' | 'pie' {
    return query.chart_hint === 'line' || query.chart_hint === 'pie' ? query.chart_hint : 'bar';
  }
  sqlLabel(query: QueryResponse) {
    return ['OK', 'REFINED_OK'].includes(query.execution_status ?? '')
      ? 'Executed SQL'
      : query.execution_status === 'REJECTED_BY_FIREWALL'
        ? 'Blocked SQL'
        : 'Recorded SQL';
  }
  queryOutcome(query: QueryResponse) {
    return ['OK', 'REFINED_OK'].includes(query.execution_status ?? '')
      ? 'Completed'
      : query.execution_status === 'FAILED'
        ? 'Failed'
        : query.execution_status === 'REJECTED_BY_FIREWALL'
          ? 'Blocked by query policy'
          : 'Status unavailable';
  }
  schemaRows(columns: Column[]) {
    return columns.map((column) => ({
      Column: column.name,
      Type: column.data_type,
      Description: column.description ?? '',
      Classification: column.pii_tag ?? '',
    }));
  }
  searchRows() {
    return (
      this.search()?.hits.map((hit) => ({
        Document: hit.title,
        Excerpt: hit.text,
        ...(hit.score !== undefined ? { Score: hit.score } : {}),
      })) ?? []
    );
  }
  nodeLabel(id: string) {
    return (
      this.lineage()?.nodes.find((node) => node.id === id)?.label || 'Missing source reference'
    );
  }
  lineageRows() {
    return (
      this.lineage()?.edges.map((edge) => ({
        From: this.nodeLabel(edge.source),
        To: this.nodeLabel(edge.target),
        Relationship: edge.label ?? '',
      })) ?? []
    );
  }
}
const KnowledgeAnswer = /* @__PURE__ */ defineComponent({
  name: 'KnowledgeAnswer',
  description: 'Groups canonical server evidence. No model-authored business values.',
  props: answerProps,
  component: KoinonKnowledgeAnswer,
});
const Evidence = /* @__PURE__ */ defineComponent({
  name: 'Evidence',
  description: 'Displays an authorized result from this answer using its canonical result ID.',
  props: evidenceProps,
  component: KoinonEvidence,
});
export const KOINON_EVIDENCE_LIBRARY = /* @__PURE__ */ createLibrary({
  components: [KnowledgeAnswer, Evidence],
  root: 'KnowledgeAnswer',
});
@Component({
  selector: 'ffk-openui-artifact',
  imports: [KoinonTextPipe, Renderer, KoinonSkeleton, KoinonIcon],
  providers: [KoinonEvidenceContext],
  template: `@if (validation().status === 'error' || renderError()) {
      <div class="artifact-error" role="status">
        <ffk-icon name="alert" /><span>{{ renderError() || validation().message }}</span>
      </div>
    } @else if (validation().status === 'pending' && mode === 'audit') {
      <ffk-skeleton width="70%" height="12px" [label]="'Preparing evidence' | ffkText" />
    } @else if (validation().status === 'ready') {
      <openui-renderer
        [response]="validation().source"
        [library]="library"
        [isStreaming]="false"
        [toolProvider]="null"
        (error)="renderError.set($event.length ? 'This evidence view could not be displayed.' : '')"
        (action)="renderError.set('This evidence view requested an unsupported action.')"
      />
    }`,
  styles: `
    :host {
      display: block;
      min-width: 0;
    }
    .artifact-error {
      display: flex;
      align-items: flex-start;
      gap: 10px;
      font: 400 12px/1.8 var(--ffk-font, 'Manrope Variable', sans-serif);
      color: var(--ui-muted, #62645b);
      padding: 14px 0;
    }
    .artifact-error ffk-icon {
      font-size: 16px;
      flex-shrink: 0;
      margin-top: 3px;
    }
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonOpenUiArtifact implements OnChanges, OnDestroy {
  @Input() mode: 'answer' | 'audit' = 'answer';
  @Input() resultIds?: readonly string[];
  @Input() presentation?: Presentation;
  @Input() artifact: OpenUIArtifact | null = null;
  @Input({ required: true }) runId = '';
  @Input({ required: true }) contextKey = '';
  @Input({ required: true }) resolver: EvidenceResolver = async () => {
    throw new Error('The host has not connected this evidence.');
  };
  @Output() citationSelected = new EventEmitter<Citation>();
  @Output() resourceSelected = new EventEmitter<string>();
  private readonly context = inject(KoinonEvidenceContext);
  readonly library = KOINON_EVIDENCE_LIBRARY;
  readonly validation = signal<ReturnType<typeof validateEvidenceLanguage>>({
    status: 'pending',
    source: '',
  });
  readonly renderError = signal('');
  private readonly citationSubscription = this.context.citationRequested.subscribe((value) =>
    this.citationSelected.emit(value),
  );
  private readonly resourceSubscription = this.context.resourceRequested.subscribe((value) =>
    this.resourceSelected.emit(value),
  );
  ngOnChanges() {
    this.context.bind(this.runId, this.resolver, this.contextKey, this.presentation, this.mode);
    this.renderError.set('');
    if (!this.artifact) {
      this.validation.set({ status: 'pending', source: '' });
      return;
    }
    if (this.artifact.run_id !== this.runId) {
      this.validation.set({
        status: 'error',
        source: '',
        message: 'This evidence belongs to a different answer.',
      });
      return;
    }
    this.validation.set(
      validateEvidenceLanguage(
        this.artifact.language,
        !this.artifact.complete,
        this.library.toJSONSchema(),
        this.mode === 'answer' ? this.resultIds : undefined,
      ),
    );
  }
  ngOnDestroy() {
    this.citationSubscription.unsubscribe();
    this.resourceSubscription.unsubscribe();
  }
}
