// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { KoinonTextPipe, KoinonI18n, KoinonValuePipe } from '@fireflyframework/koinon-angular';
import {
  Component,
  ChangeDetectionStrategy,
  Input,
  OnInit,
  PendingTasks,
  inject,
  signal,
  computed,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import {
  KoinonFacade,
  KoinonClientContext,
  KoinonButton,
  KoinonBadge,
  KoinonSkeleton,
  KoinonIcon,
  KoinonFormField,
  KoinonSearchField,
  KoinonPagination,
  KoinonFolderTree,
  friendlyStatus,
} from '@fireflyframework/koinon-angular';
import {KoinonCommunicationsSettings} from '@fireflyframework/koinon-angular/communications/admin';
import { KoinonModelOptionsForm } from './model-options-form';
import { describeModelOptions, parseModelOptions, type ModelOptionValues } from './model-options';
import { KoinonOrganizationPeople } from './organization-directory';
import { KoinonOrganizationStructure } from './organization-structure';
import { KoinonPeopleAccess } from './people-access';
import { KoinonAuditPanel } from './audit-panel';
import { KoinonKnowledgeModels } from './knowledge-models';
import { KoinonKnowledgeBehavior } from './knowledge-behavior';
import { KoinonDeploymentPanel } from './deployment-panel';
import type {
  CapabilityState,
  ModelConnection,
  ModelApi,
  AgentConfiguration,
  AgentInput,
  AgentTool,
  FieldSchema,
  ModelProvider,
  ProviderInput,
  KnowledgeScope,
  CatalogEntry,
  Page,
} from '@fireflyframework/koinon-sdk';
import { KoinonOrganizationChatSettings } from './organization-chat-settings';
import { KoinonIdentityAppearance } from './identity-appearance';
import { KoinonMcpApplications } from './mcp-applications';
import { KoinonConfiguration } from './configuration';
import { registerKoinonSpanish } from '@fireflyframework/koinon-angular/workbench';
import { ORGANIZATION_SPANISH } from './organization-spanish';
registerKoinonSpanish({ ...ORGANIZATION_SPANISH, Applications: 'Aplicaciones' });
@Component({
  selector: 'ffk-settings-page',
  imports: [
    KoinonCommunicationsSettings,
    KoinonIdentityAppearance,
    KoinonMcpApplications,
    KoinonTextPipe,
    KoinonValuePipe,
    FormsModule,
    KoinonButton,
    KoinonBadge,
    KoinonSkeleton,
    KoinonIcon,
    KoinonFormField,
    KoinonSearchField,
    KoinonPagination,
    KoinonFolderTree,
    KoinonDeploymentPanel,
    KoinonKnowledgeModels,
    KoinonKnowledgeBehavior,
    KoinonPeopleAccess,
    KoinonOrganizationPeople,
    KoinonOrganizationStructure,
    KoinonAuditPanel,
    KoinonModelOptionsForm,
    KoinonOrganizationChatSettings,
  ],
  providers: [KoinonConfiguration],
  templateUrl: './settings-page.html',
  styleUrl: './settings-page.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonSettingsPage implements OnInit {
  @Input() actions?: {
    chat: (id: string) => void;
    section?: () => string;
    addKnowledge?: () => void;
    resource?: (id: string) => void;
    invitationBaseUrl?: () => string;
    navigationCollapsed?: () => boolean;
    toggleNavigation?: () => void;
  };
  private readonly collapsed = signal(false);
  navigationCollapsed() { return this.actions?.navigationCollapsed?.() ?? this.collapsed(); }
  toggleNavigation() { if(this.actions?.toggleNavigation) this.actions.toggleNavigation(); else this.collapsed.update(value=>!value); }
  readonly c = inject(KoinonConfiguration);
  readonly f = inject(KoinonFacade);
  private readonly i18n = inject(KoinonI18n);
  private readonly clients = inject(KoinonClientContext);
  private readonly tasks = inject(PendingTasks);
  readonly section = signal('providers');
  readonly editor = signal<'provider' | 'agent' | null>(null);
  readonly step = signal(1);
  readonly providerRecord = signal<ModelProvider | null>(null);
  readonly agentRecord = signal<AgentConfiguration | null>(null);
  readonly formError = signal('');
  readonly providerFieldErrors = signal<Record<string, string>>({});
  readonly providerQuery = signal('');
  agentQuery = '';
  readonly providerKind = signal('');
  providerValues: Record<string, string> = {};
  providerEnabled = true;
  removeProviderSecret = false;
  modelOptionValues: ModelOptionValues = {};
  readonly modelOptionErrors = signal<Record<string, string>>({});
  agentName = '';
  agentDescription = '';
  agentInstructions = '';
  agentProvider = '';
  agentModel = '';
  agentEnabled = true;
  agentTools: AgentTool[] = [];
  agentScope: KnowledgeScope = {};
  readonly scopePicker = signal(false);
  readonly selectedType = computed(() =>
    this.c.configuration()?.provider_types.find((type) => type.id === this.providerKind()),
  );
  readonly providers = computed(
    () =>
      this.c
        .configuration()
        ?.providers.filter((provider) =>
          provider.name.toLowerCase().includes(this.providerQuery().toLowerCase()),
        ) ?? [],
  );
  readonly usableProviders = computed(
    () =>
      this.c
        .configuration()
        ?.providers.filter(
          (provider) => provider.enabled && (provider.discovered ?? provider.validated),
        ) ?? [],
  );
  readonly groups = [
    {
      id: 'organization',
      label: 'Organization',
      sections: ['people', 'structure', 'access', 'communications', 'identity', 'applications'],
    },
    {
      id: 'knowledge',
      label: 'Knowledge & AI',
      sections: ['sources', 'providers', 'models', 'agents', 'storage'],
    },
    { id: 'operations', label: 'Operations', sections: ['audit', 'operations'] },
  ];
  readonly tabs = [
    {
      id: 'identity',
      label: 'Identity & appearance',
      permission: 'settings:write',
      icon: 'palette',
    },
    { id: 'people', label: 'People', permission: 'members:write', icon: 'users' },
    {
      id: 'structure',
      label: 'Organization structure',
      permission: 'members:write',
      icon: 'lineage',
    },
    { id: 'communications', label: 'Communications', permission: 'members:write', icon: 'mail' },
    { id: 'access', label: 'Access', permission: 'members:write', icon: 'shield' },
    { id: 'applications', label: 'Applications', permission: 'identity:manage', icon: 'grid' },
    {
      id: 'sources',
      label: 'Sources & connections',
      permission: 'sources:configure',
      icon: 'link',
    },
    { id: 'providers', label: 'Providers', permission: 'providers:write', icon: 'spark' },
    { id: 'models', label: 'Knowledge models', permission: 'providers:write', icon: 'link' },
    { id: 'agents', label: 'Agents', permission: 'agents:write', icon: 'chat' },
    { id: 'storage', label: 'Storage & indexing', permission: 'indexes:manage', icon: 'table' },
    { id: 'audit', label: 'Audit', permission: 'audit:read', icon: 'shield' },
    { id: 'operations', label: 'Operations', permission: 'jobs:manage', icon: 'jobs' },
  ];
  ngOnInit() {
    this.tasks.run(async () => {
      const metadata = this.allowed('providers:write') ? this.c.load() : undefined;
      const requested = this.actions?.section?.() || 'providers';
      const initial =
        this.tabs.find((tab) => tab.id === requested && this.tabAllowed(tab)) ??
        this.tabs.find((tab) => this.tabAllowed(tab));
      if (initial) await this.openSection(initial.id);
      await metadata;
    });
  }
  allowed(permission: string) {
    return (permission === 'members:write' ? this.f.permissions() : this.f.tenantPermissions()).has(
      permission,
    );
  }
  tabAllowed(tab: { id: string; permission: string }) {
    if (['people', 'structure'].includes(tab.id))
      return this.f.tenantPermissions().has('members:write');
    return this.allowed(tab.permission) || (tab.id === 'models' && this.allowed('settings:write'));
  }
  tabsFor(group: { sections: string[] }) {
    return this.tabs.filter((tab) => group.sections.includes(tab.id) && this.tabAllowed(tab));
  }
  async openSection(section: string) {
    if (!this.tabs.some((tab) => tab.id === section && this.tabAllowed(tab))) return;
    this.providerValues['secret'] = '';
    this.section.set(section);
    this.editor.set(null);
    this.formError.set('');
    if (section === 'agents') await this.c.loadAgents();
    if (section === 'access') await this.f.loadMembers();
    if (section === 'operations') await this.f.loadJobs();
    if (section === 'storage') await this.c.load();
    if (section === 'sources') await this.loadSources();
  }
  beginProvider(provider?: ModelProvider) {
    this.providerRecord.set(provider ?? null);
    this.providerValues = {};
    this.removeProviderSecret = false;
    this.providerFieldErrors.set({});
    this.providerEnabled = provider?.enabled ?? true;
    this.providerKind.set(provider?.kind ?? '');
    if (provider) {
      this.providerValues = {
        name: provider.name,
        base_url: provider.base_url,
        model_ids: provider.model_ids.join('\n'),
        secret: '',
        api:
          provider.api ??
          this.c
            .configuration()
            ?.provider_types.find((type) => type.id === provider.kind)
            ?.fields.find((field) => field.name === 'api')?.default ??
          '',
      };
    }
    this.step.set(provider ? 2 : 1);
    this.editor.set('provider');
    this.formError.set('');
    this.c.error.set('');
    this.c.notice.set('');
    this.c.validation.set(null);
  }
  chooseProvider(kind: string) {
    const type = this.c.configuration()?.provider_types.find((value) => value.id === kind);
    if (!type) return;
    if (kind !== this.providerKind())
      this.providerValues = Object.fromEntries(
        type.fields.map((field) => [field.name, field.default ?? '']),
      );
    this.providerKind.set(kind);
    this.step.set(2);
  }
  backProvider() {
    if (!this.providerRecord()) {
      this.providerValues['secret'] = '';
      this.step.set(1);
      this.providerFieldErrors.set({});
      this.formError.set('');
    }
  }
  fieldHint(field: FieldSchema) {
    return field.type === 'string_list'
      ? 'Enter one model name per line. Use models available to this provider.'
      : field.type === 'secret' && this.removeProviderSecret
        ? 'The current key will be removed.'
        : field.type === 'secret' && this.providerRecord()?.secret_configured
          ? 'Leave blank to keep the current key.'
          : '';
  }
  requiredField(field: FieldSchema) {
    return (
      field.required &&
      !(
        field.type === 'secret' &&
        (this.providerRecord()?.secret_configured || this.removeProviderSecret)
      )
    );
  }
  async saveProvider() {
    const type = this.selectedType();
    if (!type) return;
    const errors: Record<string, string> = {};
    for (const field of type.fields) {
      const value = this.providerValues[field.name]?.trim() ?? '';
      if (this.requiredField(field) && !value) errors[field.name] = 'This field is required.';
      if (
        field.type === 'select' &&
        value &&
        !field.options?.some((option) => option.value === value)
      )
        errors[field.name] = 'Choose one of the available values.';
      if (field.type === 'url' && value) {
        try {
          const url = new URL(value);
          if (!['http:', 'https:'].includes(url.protocol))
            errors[field.name] = 'Enter an HTTP or HTTPS address.';
        } catch {
          errors[field.name] = 'Enter an HTTP or HTTPS address.';
        }
      }
    }
    this.providerFieldErrors.set(errors);
    if (Object.keys(errors).length) {
      this.formError.set('Complete the required provider fields.');
      return;
    }
    this.formError.set('');
    const value: ProviderInput = {
      kind: this.providerKind() as ModelProvider['kind'],
      name: this.providerValues['name']?.trim(),
      base_url: this.providerValues['base_url']?.trim(),
      model_ids: (this.providerValues['model_ids'] ?? '')
        .split('\n')
        .map((model) => model.trim())
        .filter(Boolean),
      enabled: this.providerEnabled,
    };
    if (this.providerValues['api']) value.api = this.providerValues['api'] as ModelApi;
    if (this.removeProviderSecret) value.secret = null;
    else if (this.providerValues['secret']?.trim())
      value.secret = this.providerValues['secret'].trim();
    const saved = await this.c.saveProvider(this.providerRecord()?.id ?? null, value);
    if (saved) {
      this.providerValues['secret'] = '';
      this.providerRecord.set(saved);
      this.step.set(3);
    }
  }
  async checkProvider() {
    const provider = this.providerRecord();
    if (!provider) return;
    const result = await this.c.validateProvider(provider.id);
    if (result) this.providerRecord.set(this.c.provider(provider.id) ?? provider);
  }
  finish() {
    this.providerValues['secret'] = '';
    this.editor.set(null);
    this.formError.set('');
  }
  beginAgent(agent?: AgentConfiguration) {
    this.agentRecord.set(agent ?? null);
    this.agentName = agent?.name ?? '';
    this.agentDescription = agent?.description ?? '';
    this.agentInstructions = agent?.instructions ?? '';
    this.agentProvider = agent?.provider_id ?? '';
    this.agentModel = agent?.model_id ?? '';
    this.agentEnabled = agent?.enabled ?? true;
    this.agentTools = [...(agent?.tools ?? [])];
    this.modelOptionValues = Object.fromEntries(
      Object.entries(agent?.model_options ?? {}).map(([key, value]) => [
        key,
        Array.isArray(value) ? [...value] : String(value),
      ]),
    );
    this.modelOptionErrors.set({});
    const folder = this.f.entries().find((entry) => entry.id === this.f.parentId());
    this.agentScope = agent?.scope ?? {
      ...(this.f.workspaceId() ? { workspace_id: this.f.workspaceId() } : {}),
      ...(this.f.projectId() ? { project_id: this.f.projectId() } : {}),
      ...(folder && (folder.kind === 'collection' || folder.kind === 'corpus')
        ? { collection_id: folder.id }
        : {}),
    };
    this.step.set(2);
    this.editor.set('agent');
    this.formError.set('');
    this.c.error.set('');
    this.c.notice.set('');
  }
  modelOptionFields() {
    const supported =
      this.c
        .provider(this.agentProvider)
        ?.model_capabilities?.find((model) => model.model_id === this.agentModel)?.option_fields ??
      this.agentRecord()?.model_options_supported ??
      [];
    return describeModelOptions(this.c.configuration()?.model_options_schema, supported);
  }
  resetModelOptions() {
    this.modelOptionValues = {};
    this.modelOptionErrors.set({});
  }
  canRun(agent: AgentConfiguration | null | undefined) {
    return !!agent && (agent.can_run ?? agent.status === 'ready');
  }
  capabilityLabel(state: CapabilityState | undefined) {
    return state?.verified && state.supported === true
      ? 'Verified'
      : state?.supported === false
        ? 'Not supported'
        : 'Not checked';
  }
  generationVerified(provider: ModelProvider) {
    return (
      provider.enabled &&
      !!provider.model_capabilities?.length &&
      provider.model_capabilities.every(
        (model) =>
          model.chat.verified &&
          model.chat.supported === true &&
          model.streaming.verified &&
          model.streaming.supported === true,
      )
    );
  }
  providerLabel(provider: ModelProvider) {
    return !provider.enabled
      ? 'Disabled'
      : this.generationVerified(provider)
        ? 'Generation checked'
        : (provider.discovered ?? provider.validated)
          ? 'Models found'
          : provider.connected
            ? 'Connected'
            : 'Not checked';
  }
  apiLabel(value: string) {
    return (
      (
        { chat: 'Chat completions', responses: 'Responses', messages: 'Messages' } as Record<
          string,
          string
        >
      )[value] ?? value
    );
  }
  connectionLabel(connection: ModelConnection) {
    return (
      (
        {
          'documents.embedding': 'Document embeddings',
          'documents.answer': 'Document answers',
          'documents.rlm_root': 'Document reasoning',
          'documents.rlm_sub': 'Document analysis',
          'documents.datasource': 'Document database',
          'structured.datasource': 'Dataset database',
          'structured.grounding': 'Dataset grounding',
          'structured.generation': 'Dataset query generation',
          'structured.critic': 'Dataset query review',
          'structured.explainer': 'Dataset explanations',
        } as Record<string, string>
      )[connection.id] ?? 'Model connection'
    );
  }
  models() {
    return this.c.provider(this.agentProvider)?.model_ids ?? [];
  }
  toggleTool(tool: AgentTool, enabled: boolean) {
    this.agentTools = enabled
      ? [...new Set([...this.agentTools, tool])]
      : this.agentTools.filter((value) => value !== tool);
  }
  readonly tools: { id: AgentTool; name: string; description: string }[] = [
    {
      id: 'search_knowledge',
      name: 'Search knowledge',
      description: 'Find passages in documents the caller can access.',
    },
    {
      id: 'inspect_schema',
      name: 'Inspect datasets',
      description: 'Read dataset tables and column definitions.',
    },
    {
      id: 'query_dataset',
      name: 'Query datasets',
      description: 'Answer questions using authorized dataset queries.',
    },
  ];
  async saveAgent() {
    if (!this.agentName.trim() || !this.agentProvider || !this.agentModel) {
      this.formError.set('Enter an agent name and choose an available model.');
      return;
    }
    const options = parseModelOptions(this.modelOptionFields(), this.modelOptionValues);
    this.modelOptionErrors.set(options.errors);
    if (Object.keys(options.errors).length) {
      this.formError.set('Review the model options.');
      return;
    }
    const value: AgentInput = {
      model_options: options.value,
      name: this.agentName.trim(),
      description: this.agentDescription.trim(),
      provider_id: this.agentProvider,
      model_id: this.agentModel,
      tools: this.agentTools,
      scope: this.agentScope,
      instructions: this.agentInstructions.trim(),
      enabled: this.agentEnabled,
    };
    const saved = await this.c.saveAgent(this.agentRecord()?.id ?? null, value);
    if (saved) {
      this.agentRecord.set(saved);
      this.step.set(3);
    }
  }
  async checkAgent() {
    const agent = this.agentRecord();
    if (!agent) return;
    const checked = await this.c.validateAgent(agent.id);
    if (checked) this.agentRecord.set(checked);
  }
  useScope(id: string) {
    const entry =
      this.f.entries().find((row) => row.id === id) ||
      this.f.context()?.workspaces.find((row) => row.id === id);
    if (!entry) return;
    this.agentScope =
      entry.kind === 'workspace'
        ? { workspace_id: entry.id }
        : entry.kind === 'project'
          ? { workspace_id: entry.workspace_id ?? undefined, project_id: entry.id }
          : {
              workspace_id: entry.workspace_id ?? undefined,
              project_id: entry.project_id ?? undefined,
              collection_id: entry.id,
            };
    this.scopePicker.set(false);
  }
  scopeName() {
    const id =
      this.agentScope.collection_id || this.agentScope.project_id || this.agentScope.workspace_id;
    return id
      ? this.f.entries().find((row) => row.id === id)?.name ||
          this.f.context()?.workspaces.find((row) => row.id === id)?.name ||
          this.i18n.text('Selected knowledge')
      : this.i18n.text('Knowledge the caller can access');
  }
  readonly loadTreeChildren = (id: string, page = 1) => this.f.loadChildren(id, page);
  readonly status = friendlyStatus;
  workspaceName(id: string | null) {
    return id
      ? this.f.context()?.workspaces.find((workspace) => workspace.id === id)?.name ||
          'Selected space'
      : 'Organization';
  }
  actorName(subject: string) {
    return this.i18n.text(subject === this.f.context()?.subject ? 'You' : 'Name unavailable');
  }
  connectionName(value: unknown) {
    return value && typeof value === 'object' && 'name' in value && typeof value.name === 'string'
      ? value.name
      : 'Connection';
  }
  workspaceNames() {
    return Object.fromEntries(
      (this.f.context()?.workspaces ?? []).map((row) => [row.id, row.name]),
    );
  }
  readonly sources = signal<Page<CatalogEntry>>({ items: [] });
  sourceQuery = '';
  async loadSources(page = 1) {
    try {
      this.sources.set(
        await this.clients.get().catalog.list(this.f.tenantId(), {
          kind: 'source',
          q: this.sourceQuery,
          page,
          page_size: 25,
          workspace_id: this.f.workspaceId() || undefined,
        }),
      );
    } catch (error) {
      this.c.error.set(error instanceof Error ? error.message : 'Sources could not be loaded.');
    }
  }
}
