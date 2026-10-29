// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { computed, inject, Injectable, signal } from '@angular/core';
import {
  type KoinonClient,
  KoinonError,
  type AuditEvent,
  type Capabilities,
  type CatalogEntry,
  type CatalogFilter,
  type Page,
  type ContextResponse,
  type DatasetSchema,
  type EntryCreate,
  type EntryUpdate,
  type HttpMethod,
  type Job,
  type Lineage,
  type Membership,
  type MemberInput,
  type QueryResponse,
  type RequestOptions,
  type SearchResponse,
} from '@fireflyframework/koinon-sdk';
import { KOINON_TENANT_RESOLVER, KOINON_TRANSPORT } from './client-provider';
import type {FolderPageState} from './models';
import { KoinonClientContext } from './services/client-context';

@Injectable()
export class KoinonFacade {
  private readonly clientContext=inject(KoinonClientContext);
  private readonly transport = inject(KOINON_TRANSPORT, { optional: true });
  private readonly tenantResolver = inject(KOINON_TENANT_RESOLVER, { optional: true });
  private revision = 0;
  private initialization = 0;
  readonly context = signal<ContextResponse | null>(null);
  readonly tenantId = signal('');
  readonly workspaceId = signal('');
  readonly projectId = signal('');
  readonly parentId = signal('');
  readonly entries = signal<CatalogEntry[]>([]);
  readonly libraryPage=signal<Page<CatalogEntry>>({items:[]});
  readonly libraryFilter=signal<CatalogFilter>({view:"library",page:1,page_size:25,q:"",sort:"name",order:"asc"});
  readonly archivedPage=signal<Page<CatalogEntry>>({items:[]});
  readonly archivedFilter=signal<CatalogFilter>({page:1,page_size:25,q:"",sort:"name",order:"asc"});
  readonly selected = signal<CatalogEntry | null>(null);
  readonly error = signal('');
  readonly pending = signal(false);
  readonly initializing = signal(true);
  readonly authRequired = signal(false);
  readonly notice = signal('');
  readonly capabilities = signal<Capabilities | null>(null);
  readonly capabilitiesError = signal('');
  readonly searchResult = signal<SearchResponse | null>(null);
  readonly queryResult = signal<QueryResponse | null>(null);
  readonly schema = signal<DatasetSchema | null>(null);
  readonly jobs = signal<Job[]>([]);
  readonly lineage = signal<Lineage | null>(null);
  readonly members = signal<Membership[]>([]);
  readonly audit = signal<AuditEvent[]>([]);
  readonly advancedResult = signal<unknown>(undefined);
  readonly tenant = computed(() => this.context()?.tenants.find((t) => t.id === this.tenantId()));
  readonly tenantPermissions = computed(() => new Set(this.tenant()?.permissions ?? []));
  readonly permissions = computed(() => {
    const permissions = new Set(this.tenantPermissions());
    const context = this.context(), workspaceId = this.workspaceId();
    const workspace = context?.workspaces.find(row => row.id === workspaceId && row.tenant_id === this.tenantId() && row.kind === 'workspace' && row.status !== 'archived');
    const scopes = context && 'workspace_permissions' in context ? context.workspace_permissions : undefined;
    if (!workspace || !scopes || typeof scopes !== 'object' || !(workspaceId in scopes)) return permissions;
    const scoped: unknown = Reflect.get(scopes, workspaceId);
    if (Array.isArray(scoped) && scoped.every(value => typeof value === 'string')) for (const permission of scoped) permissions.add(permission);
    return permissions;
  });
  readonly canWrite = computed(() => this.permissions().has('catalog:write'));
  readonly canUpload = computed(() => this.permissions().has('ingest:write'));
  readonly canQuery = computed(() => this.permissions().has('query:execute'));
  readonly canManageMembers = computed(() => this.permissions().has('members:write'));
  readonly canAudit = computed(() => this.permissions().has('audit:read'));
  readonly advancedAvailable = !!this.transport;
  bindClient(client: KoinonClient): void {
    this.clientContext.bind(client);
    ++this.initialization;
    ++this.revision;
    this.context.set(null);
    this.libraryPage.set({items:[]});
    this.archivedPage.set({items:[]});
    this.entries.set([]);
    this.selected.set(null);
    this.clearResults();
  }
  private api():KoinonClient {return this.clientContext.get();}
  private message(error: unknown): string {
    if (error instanceof KoinonError || (error instanceof Error && 'status' in error)) {
      if (error.status === 401) this.authRequired.set(true);
      return error.message;
    }
    return error instanceof Error ? error.message : 'The request could not be completed.';
  }
  async bootstrap(tenantId = ''): Promise<void> {
    const initialization = ++this.initialization;
    const previousSubject = this.context()?.subject;
    this.initializing.set(true);
    this.error.set('');
    this.authRequired.set(false);
    try {
      const context = await this.api().context();
      if (initialization !== this.initialization) return;
      this.context.set(context);
      const requested = this.tenantResolver
        ? this.tenantResolver(context, tenantId)
        : tenantId || (previousSubject === context.subject ? this.tenantId() : '');
      const id = context.tenants.find(tenant => tenant.id === requested)?.id || context.tenants[0]?.id;
      await this.selectTenant(id || '');
    } catch (error) {
      if (initialization === this.initialization) this.error.set(this.message(error));
    } finally {
      if (initialization === this.initialization) this.initializing.set(false);
    }
  }
  async selectTenant(id: string): Promise<void> {
    const revision = ++this.revision;
    this.tenantId.set(id);
    this.workspaceId.set('');
    this.projectId.set('');
    this.parentId.set('');
    this.entries.set([]);
    this.libraryPage.set({items:[]});
    this.libraryFilter.set({view:"library",page:1,page_size:25,q:"",sort:"name",order:"asc"});
    this.selected.set(null);
    this.clearResults();
    this.error.set('');
    this.notice.set('');
    if (!id) {
      this.pending.set(false);
      return;
    }
    this.pending.set(true);
    try {
      const result = await this.api().catalog.list(id,this.libraryFilter());
      if (revision === this.revision) this.acceptLibraryPage(result);
    } catch (error) {
      if (revision === this.revision) this.error.set(this.message(error));
    } finally {
      if (revision === this.revision) this.pending.set(false);
    }
  }
  async setWorkspace(id: string): Promise<void> {
    this.workspaceId.set(id);
    this.projectId.set('');
    this.parentId.set(id);
    this.selected.set(null);
    this.clearResults();
    await this.loadLibrary({page:1,q:"",kind:undefined,status:undefined,tag:undefined,format:undefined});
  }
  async refresh(): Promise<void> {
    const revision = ++this.revision;
    this.pending.set(true);
    this.error.set('');
    try {
      const page = await this.api().catalog.list(
        this.tenantId(),
        {...this.libraryFilter(),parent_id:this.parentId()||undefined,workspace_id:this.workspaceId()||undefined},
      );
      if (revision === this.revision) this.acceptLibraryPage(page);
    } catch (error) {
      if (revision === this.revision) this.error.set(this.message(error));
    } finally {
      if (revision === this.revision) this.pending.set(false);
    }
  }
  private acceptLibraryPage(page:Page<CatalogEntry>){this.libraryPage.set(page);this.entries.update(rows=>[...new Map([...rows,...page.items].map(x=>[x.id,x])).values()]);}
  async loadLibrary(filter:CatalogFilter={}):Promise<void>{this.libraryFilter.update(current=>({...current,...filter,view:'library'}));await this.refresh();}
  private clearResults(): void {
    this.archivedPage.set({items:[]});
    this.archivedFilter.set({page:1,page_size:25,q:"",sort:"name",order:"asc"});
    this.searchResult.set(null);
    this.queryResult.set(null);
    this.schema.set(null);
    this.jobs.set([]);
    this.lineage.set(null);
    this.members.set([]);
    this.audit.set([]);
    this.advancedResult.set(undefined);
  }
  async action<T>(
    operation: () => Promise<T>,
    apply: (value: T) => void,
    notice = '',
  ): Promise<boolean> {
    const revision = this.revision;
    this.pending.set(true);
    this.error.set('');
    this.notice.set('');
    try {
      const result = await operation();
      if (revision === this.revision) {
        apply(result);
        this.notice.set(notice);
        return true;
      }
      return false;
    } catch (error) {
      if (revision === this.revision) this.error.set(this.message(error));
      return false;
    } finally {
      if (revision === this.revision) this.pending.set(false);
    }
  }
  async create(input: EntryCreate): Promise<boolean> {
    const scope=this.scopeStamp();
    const done=await this.action(
      () => this.api().catalog.create(this.tenantId(), input),
      (entry) => {
        this.entries.update((rows) => [...rows, entry]);
        this.selected.set(entry);
      },
      'Created',
    );
    return this.finishMutation(done,scope);
  }
  async update(id: string, input: EntryUpdate): Promise<boolean> {
    const scope=this.scopeStamp();
    const done=await this.action(
      () => this.api().catalog.update(this.tenantId(), id, input),
      (entry) => {
        this.entries.update((rows) => rows.map((row) => (row.id === entry.id ? entry : row)));
        this.selected.set(entry);
      },
      'Changes saved',
    );
    return this.finishMutation(done,scope);
  }
  private scopeStamp(){return JSON.stringify([this.tenantId(),this.workspaceId(),this.parentId()]);}
  private async finishMutation(done:boolean,scope:string){if(!done||scope!==this.scopeStamp())return false;await this.loadLibrary({page:1});return scope===this.scopeStamp();}
  async archive(entry:CatalogEntry):Promise<boolean>{const scope=this.scopeStamp();const done=await this.action(()=>this.api().catalog.archive(this.tenantId(),entry.id),archived=>{this.entries.update(rows=>[...rows.filter(x=>x.id!==archived.id),archived]);},'Archived');const confirmed=await this.finishMutation(done,scope);if(confirmed)this.selected.set(null);return confirmed;}
  async loadArchived(filter:CatalogFilter={}){this.archivedFilter.update(current=>({...current,...filter}));return this.action(()=>this.api().catalog.list(this.tenantId(),{...this.archivedFilter(),workspace_id:this.workspaceId()||undefined,view:'raw',include_archived:true,status:'archived'}),page=>this.archivedPage.set(page));}
  async restore(entry:CatalogEntry):Promise<boolean>{const scope=this.scopeStamp();const done=await this.action(()=>this.api().catalog.restore(this.tenantId(),entry.id),restored=>{this.entries.update(rows=>[...rows.filter(x=>x.id!==restored.id),restored]);},'Restored');return this.finishMutation(done,scope);}
  async loadCapabilities(): Promise<void> {
    try {
      this.capabilities.set(await this.api().capabilities());
      this.capabilitiesError.set('');
    } catch (error) {
      this.capabilitiesError.set(this.message(error));
    }
  }
  async upload(form: FormData): Promise<boolean> {
    const scope=this.scopeStamp();
    const done=await this.action(
      () => this.api().sources.upload(this.tenantId(), form),
      (response) => {
        const added = [response.source, ...response.assets];
        this.entries.update((rows) => [
          ...rows.filter((row) => !added.some((x) => x.id === row.id)),
          ...added,
        ]);
        this.selected.set(response.assets[0]??response.source);
      },
      'Source received',
    );
    return this.finishMutation(done,scope);
  }
  async search(question: string, answer: boolean): Promise<boolean> {
    return this.action(
      () =>
        this.api().search(this.tenantId(), {
          question,
          answer,
          ...(this.workspaceId() ? { workspace_id: this.workspaceId() } : {}),
          ...(this.projectId() ? { project_id: this.projectId() } : {}),
          limit: 20,
        }),
      (result) => this.searchResult.set(result),
    );
  }
  async query(datasetId: string, question: string, conversationId?: string): Promise<boolean> {
    return this.action(
      () =>
        this.api().query(this.tenantId(), {
          dataset_id: datasetId,
          question,
          ...(conversationId ? { conversation_id: conversationId } : {}),
        }),
      (result) => this.queryResult.set(result),
    );
  }
  async loadSchema(datasetId: string): Promise<boolean> {
    this.schema.set(null);
    return this.action(
      () => this.api().dataset.schema(this.tenantId(), datasetId),
      (schema) => this.schema.set(schema),
    );
  }
  async loadJobs(): Promise<boolean> {
    return this.action(
      () => this.api().jobs.list(this.tenantId()),
      (page) => this.jobs.set(page.items),
    );
  }
  async cancelJob(id: string): Promise<boolean> {
    return this.action(
      () => this.api().jobs.cancel(this.tenantId(), id),
      (job) => this.jobs.update((rows) => rows.map((row) => (row.id === id ? job : row))),
      'Cancellation requested',
    );
  }
  async loadLineage(assetId?: string): Promise<boolean> {
    return this.action(
      () => this.api().lineage(this.tenantId(), assetId),
      (value) => this.lineage.set(value),
    );
  }
  async loadMembers(): Promise<boolean> {
    return this.action(
      () => this.api().members.list(this.tenantId()),
      (page) => this.members.set(page.items),
    );
  }
  async addMember(member: MemberInput): Promise<boolean> {
    return this.action(
      () => this.api().members.add(this.tenantId(), member),
      (value) => this.members.update((rows) => [...rows, value]),
      'Member added',
    );
  }
  async updateMember(id: string, role: Membership['role']): Promise<boolean> {
    return this.action(
      () => this.api().members.update(this.tenantId(), id, { role }),
      (value) => this.members.update((rows) => rows.map((row) => (row.id === id ? value : row))),
      'Role updated',
    );
  }
  async removeMember(id: string): Promise<boolean> {
    return this.action(
      () => this.api().members.remove(this.tenantId(), id),
      () => this.members.update((rows) => rows.filter((row) => row.id !== id)),
      'Membership removed',
    );
  }
  async loadAudit(): Promise<boolean> {
    return this.action(
      () => this.api().audit.list(this.tenantId()),
      (page) => this.audit.set(page.items),
    );
  }
  async execute(method: HttpMethod, path: string, options: RequestOptions): Promise<boolean> {
    if (!this.transport) {
      this.error.set('The host has not provided an advanced API transport.');
      return false;
    }
    return this.action(
      () => this.transport!.request<unknown>(method, path, options),
      (value) => this.advancedResult.set(value),
    );
  }
  async loadChildren(parentId:string,page=1):Promise<FolderPageState|null>{
    const parent=[...(this.context()?.workspaces??[]),...this.entries()].find(x=>x.id===parentId);
    const workspaceId=parent?.kind==='workspace'?parent.id:parent?.workspace_id;
    let pagination:FolderPageState|null=null;
    const done=await this.action(()=>this.api().catalog.list(this.tenantId(),{view:'library',parent_id:parentId||undefined,kind:parentId?undefined:'workspace',page,page_size:100,...(workspaceId?{workspace_id:workspaceId}:{})}),result=>{
      this.entries.update(rows=>[...new Map([...rows,...result.items].map(x=>[x.id,x])).values()]);pagination={ids:result.items.map(x=>x.id),page:result.page,pages:result.pages,total:result.total};
    });return done?pagination:null;
  }
  async loadResource(id: string): Promise<boolean> {
    return this.action(
      async () => {
        const entry = await this.api().catalog.get(this.tenantId(), id);
        if (this.workspaceId() && entry.workspace_id !== this.workspaceId())
          throw new Error('The resource is outside the selected workspace.');
        if (this.projectId() && entry.project_id !== this.projectId())
          throw new Error('The resource is outside the selected project.');
        return entry;
      },
      (entry) => {
        this.selected.set(entry);
        if (!this.entries().some((x) => x.id === entry.id))
          this.entries.update((rows) => [...rows, entry]);
      },
    );
  }
}
