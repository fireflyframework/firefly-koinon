// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { Injectable, OnDestroy, computed, effect, inject, signal } from '@angular/core';
import type {
  OrganizationPerson,
  OrganizationPersonPage,
  OrganizationPersonPatch,
  OrganizationPeopleFilter,
  OrganizationUnit,
  OrganizationUnitPage,
  OrganizationUnitFilter,
  OrganizationUnitInput,
  OrganizationUnitPatch,
  OrganizationDirectorySettings,
  OrganizationProfileMapping,
  OrganizationProfileMappingInput,
  IdentityProviderPage,
} from '@fireflyframework/koinon-sdk';
import { organizationContextKey } from './organization-directory-context';
import { KoinonClientContext } from './client-context';
import { KoinonFacade } from '../koinon-facade';
@Injectable()
export class KoinonOrganizationDirectory implements OnDestroy {
  readonly clients = inject(KoinonClientContext);
  readonly f = inject(KoinonFacade);
  key = organizationContextKey(this.f, this.clients);
  private readonly requests = new Map<string, AbortController>();
  readonly busy = signal<ReadonlySet<string>>(new Set());
  readonly workspaceOnly = signal(false);
  readonly pending = computed(() => this.busy().has('write'));
  readonly self = signal<OrganizationPerson | null>(null);
  readonly people = signal<OrganizationPersonPage | null>(null);
  readonly selected = signal<OrganizationPerson | null>(null);
  readonly units = signal<OrganizationUnitPage | null>(null);
  readonly unitChoices = signal<OrganizationUnitPage | null>(null);
  readonly managerChoices = signal<OrganizationPersonPage | null>(null);
  readonly reports = signal<OrganizationPersonPage | null>(null);
  readonly settings = signal<OrganizationDirectorySettings | null>(null);
  readonly mapping = signal<OrganizationProfileMapping | null>(null);
  readonly providers = signal<IdentityProviderPage | null>(null);
  readonly avatars = signal<Record<string, string>>({});
  readonly denied = signal(false);
  private readonly accessRevision = signal(0);
  readonly error = signal('');
  readonly notice = signal('');
  peopleFilter: OrganizationPeopleFilter = { page: 1, page_size: 25 };
  constructor() {
    effect(() => this.sync());
  }
  contextIdentity() {
    return organizationContextKey(this.f, this.clients) + ':' + this.accessRevision();
  }
  clearAvatars() {
    for (const url of Object.values(this.avatars())) URL.revokeObjectURL(url);
    this.avatars.set({});
  }
  private sync() {
    const key = organizationContextKey(this.f, this.clients);
    if (key === this.key) return;
    this.key = key;
    this.clearData();
    this.denied.set(false);
  }
  private clearData() {
    for (const request of this.requests.values()) request.abort();
    this.requests.clear();
    this.busy.set(new Set());
    this.self.set(null);
    this.people.set(null);
    this.selected.set(null);
    this.units.set(null);
    this.unitChoices.set(null);
    this.managerChoices.set(null);
    this.reports.set(null);
    this.settings.set(null);
    this.mapping.set(null);
    this.providers.set(null);
    this.error.set('');
    this.notice.set('');
    this.clearAvatars();
    this.peopleFilter = { page: 1, page_size: 25 };
  }
  scope() {
    return !this.workspaceOnly() && this.f.tenantPermissions().has('members:write')
      ? {}
      : { workspace_id: this.f.workspaceId() || undefined };
  }
  async run<T>(
    channel: string,
    operation: (signal: AbortSignal) => Promise<T>,
    apply: (value: T) => void,
    quiet = false,
  ): Promise<boolean> {
    this.sync();
    if (!this.f.tenantId()) return false;
    this.requests.get(channel)?.abort();
    const request = new AbortController(),
      key = this.contextIdentity();
    this.requests.set(channel, request);
    this.busy.update((value) => new Set([...value, channel]));
    if (!quiet) {
      this.error.set('');
      this.notice.set('');
    }
    try {
      const value = await operation(request.signal);
      if (
        request.signal.aborted ||
        key !== this.contextIdentity() ||
        this.requests.get(channel) !== request
      )
        return false;
      this.denied.set(false);
      apply(value);
      return true;
    } catch (error) {
      if (!request.signal.aborted && key === this.contextIdentity()) {
        const status = error instanceof Error && 'status' in error ? error.status : null;
        if (status === 401 || status === 403) {
          this.clearData();
          this.denied.set(true);
          this.accessRevision.update((value) => value + 1);
          if (status === 401) this.f.authRequired.set(true);
          this.error.set('You do not have permission to view or change this information.');
        } else if (!quiet) {
          this.error.set(
            status === 409
              ? 'This information changed. Refresh it before saving again.'
              : 'Organization information could not be loaded or saved. Try again.',
          );
        }
      }
      return false;
    } finally {
      if (this.requests.get(channel) === request) {
        this.requests.delete(channel);
        this.busy.update((value) => new Set([...value].filter((item) => item !== channel)));
      }
    }
  }
  private operations: Promise<
    import('./organization-directory-operations').OrganizationDirectoryOperations
  > | null = null;
  private destroyed = false;
  private async delegate(
    operation: (
      runtime: import('./organization-directory-operations').OrganizationDirectoryOperations,
    ) => Promise<boolean>,
  ) {
    this.sync();
    const key = this.contextIdentity();
    try {
      const runtime = await (this.operations ??= import('./organization-directory-operations').then(
        (module) => new module.OrganizationDirectoryOperations(this),
      ));
      if (this.destroyed || key !== this.contextIdentity()) return false;
      return operation(runtime);
    } catch {
      this.operations = null;
      if (!this.destroyed && key === this.contextIdentity())
        this.error.set('This section could not be opened. Refresh this page and try again.');
      return false;
    }
  }

  loadSelf() {
    return this.delegate((runtime) => runtime.loadSelf());
  }
  loadPeople(filter?: OrganizationPeopleFilter) {
    return this.delegate((runtime) => runtime.loadPeople(filter));
  }
  loadUnits(filter: OrganizationUnitFilter = {}) {
    return this.delegate((runtime) => runtime.loadUnits(filter));
  }
  searchUnits(q: string, page = 1) {
    return this.delegate((runtime) => runtime.searchUnits(q, page));
  }
  searchManagers(q: string, page = 1) {
    return this.delegate((runtime) => runtime.searchManagers(q, page));
  }
  loadReports(id: string, page = 1) {
    return this.delegate((runtime) => runtime.loadReports(id, page));
  }
  savePerson(
    person: OrganizationPerson,
    fields: Pick<OrganizationPersonPatch, 'job_title' | 'unit_id' | 'manager_id'>,
    manageLocally = false,
    managedProviderId?: string,
  ) {
    return this.delegate((runtime) =>
      runtime.savePerson(person, fields, manageLocally, managedProviderId),
    );
  }
  refreshPerson(person: OrganizationPerson) {
    return this.delegate((runtime) => runtime.refreshPerson(person));
  }
  saveUnit(unit: OrganizationUnit | null, input: OrganizationUnitInput | OrganizationUnitPatch) {
    return this.delegate((runtime) => runtime.saveUnit(unit, input));
  }
  deleteUnit(unit: OrganizationUnit) {
    return this.delegate((runtime) => runtime.deleteUnit(unit));
  }
  loadSettings() {
    return this.delegate((runtime) => runtime.loadSettings());
  }
  saveVisibility(visibility: NonNullable<OrganizationDirectorySettings['visibility']>) {
    return this.delegate((runtime) => runtime.saveVisibility(visibility));
  }
  loadProviders(page = 1) {
    return this.delegate((runtime) => runtime.loadProviders(page));
  }
  loadMapping(id: string) {
    return this.delegate((runtime) => runtime.loadMapping(id));
  }
  saveMapping(id: string, input: OrganizationProfileMappingInput) {
    return this.delegate((runtime) => runtime.saveMapping(id, input));
  }
  selectPerson(person: OrganizationPerson) {
    this.selected.set(person);
    return Promise.resolve();
  }
  ngOnDestroy() {
    this.destroyed = true;
    for (const request of this.requests.values()) request.abort();
    this.requests.clear();
    this.clearAvatars();
  }
}
