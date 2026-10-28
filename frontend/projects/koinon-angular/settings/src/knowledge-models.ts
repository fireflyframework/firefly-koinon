// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  Injector,
  Input,
  OnInit,
  PendingTasks,
  afterNextRender,
  computed,
  effect,
  inject,
  signal,
  untracked,
  viewChild,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import {
  KoinonBadge,
  KoinonButton,
  KoinonClientContext,
  KoinonFacade,
  KoinonFormField,
  KoinonIcon,
  KoinonSkeleton,
  KoinonTextPipe,
} from '@fireflyframework/koinon-angular';
import type {
  Configuration,
  KnowledgeConnection,
  KnowledgeRole,
} from '@fireflyframework/koinon-sdk';
import { KoinonKnowledgeConfiguration } from './knowledge-configuration';
import { connectionInput, type KnowledgeFormValues } from './knowledge-form';
import { KoinonModelOptionsForm } from './model-options-form';
import { describeModelOptions, parseModelOptions, type ModelOptionValues } from './model-options';
@Component({
  selector: 'ffk-knowledge-models',
  imports: [
    FormsModule,
    KoinonTextPipe,
    KoinonBadge,
    KoinonButton,
    KoinonFormField,
    KoinonIcon,
    KoinonSkeleton,
    KoinonModelOptionsForm,
  ],
  providers: [KoinonKnowledgeConfiguration],
  templateUrl: './knowledge-models.html',
  styleUrl: './knowledge-models.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { '[attr.aria-busy]': 'service.pending()' },
})
export class KoinonKnowledgeModels implements OnInit {
  @Input() configuration: Configuration | null = null;
  readonly service = inject(KoinonKnowledgeConfiguration);
  readonly facade = inject(KoinonFacade);
  private readonly clients = inject(KoinonClientContext);
  private readonly tasks = inject(PendingTasks);
  private readonly injector = inject(Injector);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  private readonly heading = viewChild<ElementRef<HTMLHeadingElement>>('editorHeading');
  readonly editing = signal<KnowledgeRole | null>(null);
  readonly existing = signal<KnowledgeConnection | null>(null);
  readonly errors = signal<Record<string, string>>({});
  readonly removeConfirmation = signal(false);
  readonly formMode = signal<'provider' | 'current_agent'>('provider');
  readonly providerId = signal('');
  readonly modelId = signal('');
  enabled = true;
  dimensions = '';
  storageDimensions = '';
  spaceId = '';
  modelOptions: ModelOptionValues = {};
  readonly optionErrors = signal<Record<string, string>>({});
  readonly providers = computed(() =>
    (this.service.roles()?.providers ?? []).filter(
      (provider) =>
        this.editing()?.kind !== 'embedding' || ['ollama', 'openai'].includes(provider.kind),
    ),
  );
  readonly models = computed(
    () => this.providers().find((provider) => provider.id === this.providerId())?.model_ids ?? [],
  );
  readonly workspaces = computed(() =>
    (this.facade.context()?.workspaces ?? []).filter(
      (workspace) =>
        workspace.tenant_id === this.facade.tenantId() &&
        workspace.kind === 'workspace' &&
        workspace.status !== 'archived',
    ),
  );
  readonly domains = [
    { id: 'documents', label: 'Documents' },
    { id: 'structured', label: 'Datasets' },
  ];
  private context = this.facade.tenantId() + ':' + this.clients.revision();
  constructor() {
    effect(() => {
      const context = this.facade.tenantId() + ':' + this.clients.revision();
      if (context !== this.context) {
        this.context = context;
        this.editing.set(null);
        untracked(() => this.tasks.run(() => this.service.load('')));
      }
    });
  }
  hasModelOptions() {
    return Object.keys(this.modelOptions).length > 0;
  }
  ngOnInit() {
    this.tasks.run(() => this.service.load());
  }
  async scopeChanged(scope: string) {
    this.editing.set(null);
    this.removeConfirmation.set(false);
    await this.service.load(scope);
  }
  scopeName() {
    return this.workspaces().find((workspace) => workspace.id === this.service.scope())?.name ?? '';
  }
  roles(domain: string) {
    return this.service.roles()?.roles.filter((role) => role.domain === domain) ?? [];
  }
  assignment(role: KnowledgeRole) {
    return (
      this.service
        .connections()
        .find((row) => row.role === role.id && row.domain === role.domain) ?? null
    );
  }
  modelName(role: KnowledgeRole) {
    const row = this.assignment(role);
    if (!row)
      return role.assignment === 'tenant' ? 'Uses organization default' : 'No model assigned';
    return row.mode === 'current_agent'
      ? 'Current chat agent'
      : (row.model_id ?? 'Model unavailable');
  }
  providerName(role: KnowledgeRole) {
    const row = this.assignment(role);
    return row?.provider_id
      ? (this.service.roles()?.providers?.find((provider) => provider.id === row.provider_id)
          ?.name ?? 'Provider unavailable')
      : '';
  }
  assignmentLabel(role: KnowledgeRole) {
    return role.status === 'disabled'
      ? 'Disabled'
      : role.status === 'assigned'
        ? 'Assigned'
        : 'Not assigned';
  }
  originLabel(role: KnowledgeRole) {
    return role.assignment === 'workspace'
      ? 'Workspace override'
      : role.assignment === 'tenant'
        ? 'Organization default'
        : 'No assignment';
  }
  begin(role: KnowledgeRole) {
    const row = this.assignment(role);
    this.existing.set(row);
    this.editing.set(role);
    this.formMode.set(row?.mode ?? 'provider');
    this.providerId.set(row?.provider_id ?? '');
    this.modelId.set(row?.model_id ?? '');
    this.enabled = row?.enabled ?? true;
    this.dimensions = row?.dimensions?.toString() ?? '';
    this.storageDimensions = row?.storage_dimensions?.toString() ?? '';
    this.spaceId = row?.space_id ?? '';
    this.modelOptions = Object.fromEntries(
      Object.entries(row?.model_options ?? {}).map(([key, value]) => [
        key,
        Array.isArray(value) ? value.map(String) : String(value),
      ]),
    );
    this.errors.set({});
    this.optionErrors.set({});
    this.removeConfirmation.set(false);
    this.service.error.set(null);
    this.service.notice.set('');
    afterNextRender(() => this.heading()?.nativeElement.focus(), { injector: this.injector });
  }
  back() {
    const role = this.editing();
    this.editing.set(null);
    this.removeConfirmation.set(false);
    afterNextRender(
      () => {
        if (role)
          this.host.nativeElement
            .querySelector<HTMLButtonElement>(`ffk-button[data-role="${role.id}"] button`)
            ?.focus();
      },
      { injector: this.injector },
    );
  }
  providerChanged(id: string) {
    this.providerId.set(id);
    this.modelId.set('');
    this.modelOptions = {};
    this.optionErrors.set({});
  }
  optionFields() {
    const supported =
      this.configuration?.providers
        .find((provider) => provider.id === this.providerId())
        ?.model_capabilities?.find((model) => model.model_id === this.modelId())?.option_fields ??
      [];
    return describeModelOptions(this.service.roles()?.model_options_schema, supported);
  }
  async save() {
    const role = this.editing();
    if (!role) return;
    const parsed = parseModelOptions(
      this.optionFields(),
      this.formMode() === 'current_agent' || role.kind === 'embedding' ? {} : this.modelOptions,
    );
    this.optionErrors.set(parsed.errors);
    const values: KnowledgeFormValues = {
      mode: this.formMode(),
      provider_id: this.providerId(),
      model_id: this.modelId(),
      enabled: this.enabled,
      dimensions: this.dimensions,
      storage_dimensions: this.storageDimensions,
      space_id: this.spaceId,
    };
    const result = connectionInput(role, this.service.scope(), values, parsed.value);
    if (
      values.mode === 'provider' &&
      (!this.providers().some((provider) => provider.id === values.provider_id) ||
        !this.models().includes(values.model_id))
    )
      result.errors['provider_id'] = 'Choose a provider and model available in this organization.';
    this.errors.set(result.errors);
    if (!result.input || Object.keys(result.errors).length || Object.keys(parsed.errors).length)
      return;
    if (await this.service.save(result.input, this.existing())) this.back();
  }
  async remove() {
    const row = this.existing();
    if (row && (await this.service.remove(row))) this.back();
  }
  errorHelp() {
    const error = this.service.error();
    const code = error && 'code' in error ? String(error.code) : '';
    return (
      (
        {
          ACCESS_DENIED:
            'You do not have permission in this scope. Choose an authorized workspace or contact an administrator.',
          KNOWLEDGE_CONNECTION_CONFLICT:
            'Another operator changed this assignment. Reload it before saving again.',
          KNOWLEDGE_CONNECTION_EXISTS:
            'This role already has an assignment. Reload to edit its current version.',
          KNOWLEDGE_EMBEDDING_REINDEX_REQUIRED:
            'This index is tied to a different embedding configuration. Ask your deployment administrator to complete a reviewed reindex before changing it.',
          KNOWLEDGE_CURRENT_AGENT_REQUIRED:
            'This role needs a running chat agent. Choose a separate provider for operations outside Chat.',
          INVALID_KNOWLEDGE_EMBEDDING:
            'Check the approved index reference and its model and storage dimensions.',
          KNOWLEDGE_CONNECTION_SCOPE_IMMUTABLE:
            'The organization, workspace and role cannot be changed on an existing assignment.',
        } as Record<string, string>
      )[code] ?? ''
    );
  }
  async reload() {
    this.editing.set(null);
    await this.service.load();
  }
}
