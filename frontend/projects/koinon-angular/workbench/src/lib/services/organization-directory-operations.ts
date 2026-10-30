// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import type {
  OrganizationPerson,
  OrganizationPersonPage,
  OrganizationPersonPatch,
  OrganizationPeopleFilter,
  OrganizationUnit,
  OrganizationUnitFilter,
  OrganizationUnitInput,
  OrganizationUnitPatch,
  OrganizationDirectorySettings,
  OrganizationProfileMappingInput,
} from '@fireflyframework/koinon-sdk';
import type { KoinonOrganizationDirectory } from './organization-directory';
export class OrganizationDirectoryOperations {
  constructor(private readonly state: KoinonOrganizationDirectory) {}
  loadSelf() {
    return this.state.run(
      'self',
      (signal) =>
        this.state.clients
          .get()
          .organizationPeople.me(this.state.f.tenantId(), this.state.scope(), { signal }),
      (value) => this.state.self.set(value),
    );
  }
  loadPeople(filter: OrganizationPeopleFilter = this.state.peopleFilter) {
    this.state.peopleFilter = {
      ...filter,
      page: filter.page ?? 1,
      page_size: 25,
      ...this.state.scope(),
    };
    this.state.clearAvatars();
    return this.state.run(
      'people',
      (signal) =>
        this.state.clients
          .get()
          .organizationPeople.list(this.state.f.tenantId(), this.state.peopleFilter, { signal }),
      (value) => {
        this.state.people.set(value);
        void this.loadAvatars(value);
      },
    );
  }
  private async loadAvatars(page: OrganizationPersonPage) {
    const key = this.state.key;
    await Promise.all(
      page.items
        .filter((person) => (person.id || person.profile_id) && person.avatar_version)
        .map((person) =>
          this.state.run(
            'avatar:' + (person.id || person.profile_id),
            (signal) =>
              this.state.clients
                .get()
                .organizationPeople.avatar(
                  this.state.f.tenantId(),
                  (person.id || person.profile_id)!,
                  this.state.scope(),
                  { signal },
                ),
            (value) => {
              if (key !== this.state.key || this.state.people() !== page || value.not_modified)
                return;
              const url = URL.createObjectURL(value.blob);
              this.state.avatars.update((old) => ({
                ...old,
                [(person.id || person.profile_id)!]: url,
              }));
            },
            true,
          ),
        ),
    );
  }
  async savePerson(
    person: OrganizationPerson,
    fields: Pick<OrganizationPersonPatch, 'job_title' | 'unit_id' | 'manager_id'>,
    manageLocally = false,
    managedProviderId?: string,
  ) {
    if (!person.id && !person.profile_id) {
      this.state.error.set(
        'This person needs to sign in and complete their profile before organization information can be added.',
      );
      return false;
    }
    if (!this.state.f.tenantPermissions().has('members:write') || this.state.pending())
      return false;
    if (
      managedProviderId &&
      (!person.id || manageLocally || !this.state.f.tenantPermissions().has('identity:manage'))
    )
      return false;
    const key = this.state.contextIdentity();
    const saved = await this.state.run(
      'write',
      (signal) =>
        person.id
          ? this.state.clients.get().organizationPeople.update(
              this.state.f.tenantId(),
              person.id,
              managedProviderId
                ? {
                    expected_revision: person.revision ?? 0,
                    managed_provider_id: managedProviderId,
                  }
                : {
                    ...fields,
                    expected_revision: person.revision ?? 0,
                    manage_locally: manageLocally,
                  },
              { signal },
            )
          : this.state.clients
              .get()
              .organizationPeople.create(
                this.state.f.tenantId(),
                { ...fields, profile_id: person.profile_id! },
                { signal },
              ),
      (value) => this.state.selected.set(value),
    );
    if (saved && key === this.state.contextIdentity()) {
      await this.state.loadPeople();
      if (key === this.state.contextIdentity())
        this.state.notice.set('Organization information saved.');
    }
    return saved;
  }
  loadUnits(filter: OrganizationUnitFilter = {}) {
    return this.state.run(
      'units',
      (signal) =>
        this.state.clients
          .get()
          .organizationPeople.units(
            this.state.f.tenantId(),
            { page: 1, page_size: 25, ...filter, ...this.state.scope() },
            { signal },
          ),
      (value) => this.state.units.set(value),
    );
  }
  searchUnits(q: string, page = 1) {
    return this.state.run(
      'unitChoices',
      (signal) =>
        this.state.clients
          .get()
          .organizationPeople.units(
            this.state.f.tenantId(),
            { q, page, page_size: 25, ...this.state.scope() },
            { signal },
          ),
      (value) => this.state.unitChoices.set(value),
    );
  }
  searchManagers(q: string, page = 1) {
    return this.state.run(
      'managerChoices',
      (signal) =>
        this.state.clients
          .get()
          .organizationPeople.list(
            this.state.f.tenantId(),
            { q, page, page_size: 25, ...this.state.scope() },
            { signal },
          ),
      (value) => this.state.managerChoices.set(value),
    );
  }
  loadReports(personId: string, page = 1) {
    return this.state.run(
      'reports',
      (signal) =>
        this.state.clients
          .get()
          .organizationPeople.reports(
            this.state.f.tenantId(),
            personId,
            { page, page_size: 25, ...this.state.scope() },
            { signal },
          ),
      (value) => this.state.reports.set(value),
    );
  }
  saveUnit(unit: OrganizationUnit | null, input: OrganizationUnitInput | OrganizationUnitPatch) {
    if (!this.state.f.tenantPermissions().has('members:write') || this.state.pending())
      return Promise.resolve(false);
    return this.state.run(
      'write',
      (signal) =>
        unit
          ? this.state.clients
              .get()
              .organizationPeople.updateUnit(
                this.state.f.tenantId(),
                unit.id,
                input as OrganizationUnitPatch,
                { signal },
              )
          : this.state.clients
              .get()
              .organizationPeople.createUnit(
                this.state.f.tenantId(),
                input as OrganizationUnitInput,
                {
                  signal,
                },
              ),
      () => this.state.notice.set('Organization unit saved.'),
    );
  }
  deleteUnit(unit: OrganizationUnit) {
    if (!this.state.f.tenantPermissions().has('members:write') || this.state.pending())
      return Promise.resolve(false);
    return this.state.run(
      'write',
      (signal) =>
        this.state.clients
          .get()
          .organizationPeople.deleteUnit(this.state.f.tenantId(), unit.id, unit.revision, {
            signal,
          }),
      () => this.state.notice.set('Organization unit removed.'),
    );
  }
  loadSettings() {
    return this.state.run(
      'settings',
      (signal) =>
        this.state.clients.get().organizationPeople.settings(this.state.f.tenantId(), { signal }),
      (value) => this.state.settings.set(value),
    );
  }
  saveVisibility(visibility: NonNullable<OrganizationDirectorySettings['visibility']>) {
    const setting = this.state.settings();
    if (!setting || !this.state.f.tenantPermissions().has('members:write') || this.state.pending())
      return Promise.resolve(false);
    return this.state.run(
      'write',
      (signal) =>
        this.state.clients
          .get()
          .organizationPeople.updateSettings(
            this.state.f.tenantId(),
            { visibility, expected_revision: setting.revision ?? 0 },
            { signal },
          ),
      (value) => {
        this.state.settings.set(value);
        this.state.notice.set('Directory visibility saved.');
      },
    );
  }
  loadProviders(page = 1) {
    return this.state.run(
      'providers',
      (signal) =>
        this.state.clients
          .get()
          .identity.list(this.state.f.tenantId(), { signal, query: { page, page_size: 25 } }),
      (value) => this.state.providers.set(value),
    );
  }
  loadMapping(providerId: string) {
    this.state.mapping.set(null);
    return this.state.run(
      'mapping',
      (signal) =>
        this.state.clients
          .get()
          .organizationPeople.mapping(this.state.f.tenantId(), providerId, { signal }),
      (value) => this.state.mapping.set(value),
    );
  }
  saveMapping(providerId: string, input: OrganizationProfileMappingInput) {
    if (
      !this.state.f.tenantPermissions().has('identity:manage') ||
      this.state.pending() ||
      this.state.mapping()?.provider_id !== providerId
    )
      return Promise.resolve(false);
    return this.state.run(
      'write',
      (signal) =>
        this.state.clients
          .get()
          .organizationPeople.updateMapping(this.state.f.tenantId(), providerId, input, { signal }),
      (value) => {
        if (this.state.mapping()?.provider_id !== providerId || value.provider_id !== providerId)
          return;
        this.state.mapping.set(value);
        this.state.notice.set('Profile mapping saved.');
      },
    );
  }
}
