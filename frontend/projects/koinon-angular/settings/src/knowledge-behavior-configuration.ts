// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { Injectable, OnDestroy, computed, effect, inject, signal } from '@angular/core';
import { KoinonClientContext, KoinonFacade } from '@fireflyframework/koinon-angular';
import type {
  DocumentKnowledgeSettings,
  StructuredKnowledgeSettings,
  OrganizationKnowledgeSettings,
  KnowledgeRole,
} from '@fireflyframework/koinon-sdk';
export interface KnowledgeBehaviorField {
  domain: 'documents' | 'structured';
  name: string;
  label: string;
  boolean?: boolean;
  decimal?: boolean;
}
export const DOCUMENT_FIELDS: readonly KnowledgeBehaviorField[] = [
  { domain: 'documents', name: 'retrieval_top_k', label: 'Retrieved passages' },
  { domain: 'documents', name: 'retrieval_per_query_k', label: 'Candidates per search' },
  { domain: 'documents', name: 'retrieval_rrf_k', label: 'Search fusion constant' },
  {
    domain: 'documents',
    name: 'query_expansion_enabled',
    label: 'Expand search queries',
    boolean: true,
  },
  { domain: 'documents', name: 'query_expansion_n', label: 'Expanded queries' },
  { domain: 'documents', name: 'answer_top_k', label: 'Passages used to answer' },
  { domain: 'documents', name: 'rlm_max_iters', label: 'Analysis steps' },
  { domain: 'documents', name: 'rlm_sub_budget', label: 'Analysis calls' },
  { domain: 'documents', name: 'rlm_max_depth', label: 'Analysis depth' },
  { domain: 'documents', name: 'rlm_self_consistency', label: 'Independent analysis attempts' },
  {
    domain: 'documents',
    name: 'rlm_extended_reasoning',
    label: 'Extended reasoning',
    boolean: true,
  },
];
export const STRUCTURED_FIELDS: readonly KnowledgeBehaviorField[] = [
  { domain: 'structured', name: 'top_k_schema', label: 'Schema matches' },
  { domain: 'structured', name: 'top_k_examples', label: 'Query examples' },
  { domain: 'structured', name: 'top_k_metrics', label: 'Metric matches' },
  { domain: 'structured', name: 'rrf_k', label: 'Schema fusion constant' },
  { domain: 'structured', name: 'generation_candidates', label: 'Query candidates' },
  { domain: 'structured', name: 'max_refine_retries', label: 'Query repair attempts' },
  {
    domain: 'structured',
    name: 'grounding_min_confidence',
    label: 'Minimum grounding confidence',
    decimal: true,
  },
];
@Injectable()
export class KoinonKnowledgeBehaviorConfiguration implements OnDestroy {
  readonly f = inject(KoinonFacade);
  private readonly clients = inject(KoinonClientContext);
  private epoch = 0;
  private key = this.contextKey();
  readonly settings = signal<OrganizationKnowledgeSettings | null>(null);
  readonly roles = signal<KnowledgeRole[] | null>(null);
  readonly values = signal<Record<string, string | boolean>>({});
  readonly errors = signal<Record<string, string>>({});
  readonly pending = signal(false);
  readonly saving = signal(false);
  readonly stale = signal(false);
  readonly denied = signal(false);
  readonly error = signal('');
  readonly notice = signal('');
  readonly canEdit = computed(
    () =>
      this.f.tenantPermissions().has('settings:write') &&
      this.key === this.contextKey() &&
      !!this.settings() &&
      !this.pending() &&
      !this.saving() &&
      !this.stale() &&
      !this.denied(),
  );
  readonly dirty = computed(
    () =>
      !!this.settings() &&
      JSON.stringify(this.values()) !== JSON.stringify(this.fromSettings(this.settings()!)),
  );
  readonly canSave = computed(() => this.canEdit() && this.dirty());
  constructor() {
    effect(() => {
      const key = this.contextKey();
      if (key !== this.key) {
        this.key = key;
        ++this.epoch;
        this.settings.set(null);
        this.roles.set(null);
        this.values.set({});
        this.errors.set({});
        this.pending.set(false);
        this.saving.set(false);
        this.stale.set(false);
        this.denied.set(false);
        this.error.set('');
        this.notice.set('');
      }
    });
  }
  contextKey() {
    return (
      this.f.tenantId() +
      ':' +
      this.f.context()?.subject +
      ':' +
      this.clients.revision() +
      ':' +
      [...this.f.tenantPermissions()].sort().join(',')
    );
  }
  private current(epoch: number) {
    return epoch === this.epoch && this.key === this.contextKey();
  }
  private fromSettings(value: OrganizationKnowledgeSettings) {
    return Object.fromEntries(
      Object.entries({ documents: value.documents, structured: value.structured }).flatMap(
        ([domain, fields]) =>
          Object.entries(fields).map(([name, field]) => [
            `${domain}.${name}`,
            typeof field === 'boolean' ? field : String(field),
          ]),
      ),
    );
  }
  private fail(error: unknown, saving = false) {
    const status = error instanceof Error && 'status' in error ? error.status : undefined;
    if (status === 401) this.f.authRequired.set(true);
    if (saving && status === 403) this.denied.set(true);
    if (saving && status === 409) {
      this.stale.set(true);
      this.error.set('Knowledge behavior changed. Reload the settings before saving again.');
    } else
      this.error.set(
        error instanceof Error
          ? error.message
          : 'Knowledge behavior could not be loaded. Try again.',
      );
  }
  async load() {
    const epoch = ++this.epoch,
      tenant = this.f.tenantId();
    this.pending.set(true);
    this.error.set('');
    this.notice.set('');
    this.denied.set(false);
    this.stale.set(false);
    this.settings.set(null);
    this.roles.set(null);
    this.values.set({});
    this.errors.set({});
    try {
      const value = await this.clients.get().organizationKnowledge.get(tenant);
      if (!this.current(epoch)) return;
      if (
        value.tenant_id !== tenant ||
        !value.documents ||
        !value.structured ||
        !value.capabilities
      )
        throw new Error('Knowledge behavior could not be loaded. Try again.');
      this.settings.set(value);
      this.values.set(this.fromSettings(value));
      try {
        const roles = await this.clients.get().knowledgeConnections.roles(tenant);
        if (this.current(epoch)) this.roles.set(roles.roles);
      } catch {
        /* Assignment visibility is independently authorized by the server. */
      }
    } catch (error) {
      if (this.current(epoch)) this.fail(error);
    } finally {
      if (this.current(epoch)) this.pending.set(false);
    }
  }
  set(name: string, value: string | boolean) {
    if (this.canEdit()) {
      this.values.update((current) => ({ ...current, [name]: value }));
      this.errors.update((current) => ({ ...current, [name]: '' }));
      this.notice.set('');
    }
  }
  cancel() {
    if (!this.settings() || this.saving()) return;
    this.values.set(this.fromSettings(this.settings()!));
    this.errors.set({});
    this.notice.set('');
  }
  bound(field: KnowledgeBehaviorField) {
    return (
      this.settings()?.capabilities[field.domain].bounds as unknown as
        Record<string, { minimum: number; maximum: number }> | undefined
    )?.[field.name];
  }
  async save() {
    if (!this.canSave()) return;
    const snapshot = this.settings()!,
      documents: Record<string, unknown> = {},
      structured: Record<string, unknown> = {},
      errors: Record<string, string> = {};
    const mode = this.values()['documents.answer_mode'];
    if (
      typeof mode !== 'string' ||
      !snapshot.capabilities.documents.answer_modes.some((value) => value === mode)
    )
      errors['documents.answer_mode'] = 'Choose an available document answer method.';
    documents['answer_mode'] = mode;
    for (const field of [...DOCUMENT_FIELDS, ...STRUCTURED_FIELDS]) {
      const id = field.domain + '.' + field.name,
        raw = this.values()[id],
        target = field.domain === 'documents' ? documents : structured;
      if (field.boolean) {
        if (typeof raw !== 'boolean') errors[id] = 'Choose one of the available values.';
        else target[field.name] = raw;
      } else {
        const bound = this.bound(field),
          value = typeof raw === 'string' && raw.trim() ? Number(raw) : NaN;
        if (
          !bound ||
          !Number.isFinite(value) ||
          (!field.decimal && !Number.isInteger(value)) ||
          value < bound.minimum ||
          value > bound.maximum
        )
          errors[id] = field.decimal
            ? 'Enter a number within the displayed limits.'
            : 'Enter a whole number within the displayed limits.';
        else target[field.name] = value;
      }
    }
    this.errors.set(errors);
    if (Object.keys(errors).length) return;
    const epoch = this.epoch,
      tenant = this.f.tenantId();
    this.saving.set(true);
    this.error.set('');
    this.notice.set('');
    try {
      const value = await this.clients.get().organizationKnowledge.update(tenant, {
        expected_revision: snapshot.revision,
        documents: documents as unknown as DocumentKnowledgeSettings,
        structured: structured as unknown as StructuredKnowledgeSettings,
      });
      if (!this.current(epoch)) return;
      this.settings.set(value);
      this.values.set(this.fromSettings(value));
      this.notice.set('Knowledge behavior saved.');
    } catch (error) {
      if (this.current(epoch)) this.fail(error, true);
    } finally {
      if (this.current(epoch)) this.saving.set(false);
    }
  }
  ngOnDestroy() {
    ++this.epoch;
  }
}
