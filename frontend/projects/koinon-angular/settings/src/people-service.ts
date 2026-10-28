// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { Injectable, OnDestroy, effect, inject, signal } from '@angular/core';
import { KoinonClientContext, KoinonFacade } from '@fireflyframework/koinon-angular';
import type {
  Membership,
  MembershipFilter,
  Invitation,
  InvitationInput,
  InvitationCreated,
  InvitationFilter,
  Person,
  Page,
  MemberInput,
  MemberUpdate,
} from '@fireflyframework/koinon-sdk';
@Injectable()
export class KoinonPeopleService implements OnDestroy {
  private readonly clients = inject(KoinonClientContext);
  private readonly facade = inject(KoinonFacade);
  private epoch = 0;
  private directoryEpoch = 0;
  private key = this.contextKey();
  readonly members = signal<Page<Membership> | null>(null);
  readonly invitations = signal<Page<Invitation> | null>(null);
  readonly directory = signal<Page<Person> | null>(null);
  readonly directoryAvatars = signal<Record<string, string>>({});
  readonly created = signal<InvitationCreated | null>(null);
  readonly pending = signal(false);
  readonly searching = signal(false);
  readonly error = signal<Error | null>(null);
  readonly notice = signal('');
  private filters: MembershipFilter = { page: 1, page_size: 25 };
  constructor() {
    effect(() => {
      const key = this.contextKey();
      if (key !== this.key) {
        this.key = key;
        ++this.epoch;
        ++this.directoryEpoch;
        this.members.set(null);
        this.directory.set(null);
        this.releaseAvatars();
        this.invitations.set(null);
        this.clearSecret();
        this.pending.set(false);
        this.searching.set(false);
        this.error.set(null);
        this.notice.set('');
      }
    });
  }
  private contextKey() {
    return this.facade.tenantId() + ':' + this.clients.revision();
  }
  private fail(error: unknown) {
    const value = error instanceof Error ? error : new Error('Access could not be loaded.');
    if ('status' in value && value.status === 401) this.facade.authRequired.set(true);
    this.error.set(value);
  }
  clearSecret() {
    this.created.set(null);
  }
  private releaseAvatars() {
    for (const url of Object.values(this.directoryAvatars())) URL.revokeObjectURL(url);
    this.directoryAvatars.set({});
  }
  async load(filters: MembershipFilter = this.filters) {
    const epoch = ++this.epoch;
    const key = this.contextKey();
    this.filters = { ...filters };
    this.pending.set(true);
    this.error.set(null);
    try {
      const result = await this.clients
        .get()
        .members.list(this.facade.tenantId(), { query: filters });
      if (epoch !== this.epoch || key !== this.contextKey()) return false;
      this.members.set(result);
      return true;
    } catch (error) {
      if (epoch === this.epoch) this.fail(error);
      return false;
    } finally {
      if (epoch === this.epoch) this.pending.set(false);
    }
  }
  async searchPeople(q: string, after?: string) {
    const epoch = ++this.directoryEpoch,
      key = this.contextKey();
    const grants = this.facade.context()?.memberships ?? [];
    const organizationAdmin = grants.some(
      (row) =>
        row.tenant_id === this.facade.tenantId() &&
        row.active &&
        row.role === 'admin' &&
        row.workspace_id === null,
    );
    const workspace =
      !organizationAdmin &&
      grants.some(
        (row) =>
          row.tenant_id === this.facade.tenantId() &&
          row.active &&
          row.role === 'admin' &&
          row.workspace_id === this.facade.workspaceId(),
      )
        ? this.facade.workspaceId()
        : undefined;
    this.searching.set(true);
    this.error.set(null);
    try {
      const result = await this.clients
        .get()
        .people.list(this.facade.tenantId(), {
          q,
          limit: 20,
          ...(after ? { after } : {}),
          ...(workspace ? { workspace_id: workspace } : {}),
        });
      if (epoch !== this.directoryEpoch || key !== this.contextKey()) return;
      this.directory.set(result);
      this.releaseAvatars();
      for (const person of result.items) {
        if (!person.profile_id || !person.avatar_version) continue;
        void this.clients
          .get()
          .people.avatar(this.facade.tenantId(), person.profile_id, workspace)
          .then(
            (download) => {
              if (
                epoch !== this.directoryEpoch ||
                key !== this.contextKey() ||
                download.not_modified
              )
                return;
              const url = URL.createObjectURL(download.blob);
              this.directoryAvatars.update((values) => ({ ...values, [person.subject]: url }));
            },
            (error: unknown) => {
              if (
                epoch === this.directoryEpoch &&
                key === this.contextKey() &&
                error instanceof Error &&
                'status' in error &&
                error.status === 401
              )
                this.facade.authRequired.set(true);
            },
          );
      }
    } catch (error) {
      if (epoch === this.directoryEpoch && key === this.contextKey()) this.fail(error);
    } finally {
      if (epoch === this.directoryEpoch) this.searching.set(false);
    }
  }
  async save(input: MemberInput | MemberUpdate, existing: Membership | null) {
    const key = this.contextKey();
    this.pending.set(true);
    this.error.set(null);
    this.notice.set('');
    try {
      if (existing)
        await this.clients
          .get()
          .members.update(this.facade.tenantId(), existing.id, input as MemberUpdate);
      else await this.clients.get().members.add(this.facade.tenantId(), input as MemberInput);
      if (key !== this.contextKey()) return false;
      await this.load();
      this.notice.set('Access saved.');
      return true;
    } catch (error) {
      if (key === this.contextKey()) this.fail(error);
      return false;
    } finally {
      if (key === this.contextKey()) this.pending.set(false);
    }
  }
  async remove(member: Membership) {
    const key = this.contextKey();
    this.pending.set(true);
    this.error.set(null);
    try {
      await this.clients.get().members.remove(this.facade.tenantId(), member.id);
      if (key !== this.contextKey()) return false;
      await this.load();
      this.notice.set('Access removed.');
      return true;
    } catch (error) {
      if (key === this.contextKey()) this.fail(error);
      return false;
    } finally {
      if (key === this.contextKey()) this.pending.set(false);
    }
  }
  async loadInvitations(filter: InvitationFilter = {}) {
    const epoch = ++this.epoch;
    this.pending.set(true);
    this.error.set(null);
    try {
      const value = await this.clients
        .get()
        .invitations.list(this.facade.tenantId(), { query: filter });
      if (epoch === this.epoch) this.invitations.set(value);
    } catch (error) {
      if (epoch === this.epoch) this.fail(error);
    } finally {
      if (epoch === this.epoch) this.pending.set(false);
    }
  }
  async invite(input: InvitationInput) {
    const key = this.contextKey();
    this.pending.set(true);
    this.error.set(null);
    this.clearSecret();
    try {
      const value = await this.clients.get().invitations.create(this.facade.tenantId(), input);
      if (key !== this.contextKey()) return false;
      this.created.set(value);
      return true;
    } catch (error) {
      if (key === this.contextKey()) this.fail(error);
      return false;
    } finally {
      if (key === this.contextKey()) this.pending.set(false);
    }
  }
  async revoke(invitation: Invitation) {
    const key = this.contextKey();
    this.pending.set(true);
    this.error.set(null);
    try {
      await this.clients.get().invitations.revoke(this.facade.tenantId(), invitation.id);
      if (key !== this.contextKey()) return false;
      this.notice.set('Invitation revoked.');
      return true;
    } catch (error) {
      if (key === this.contextKey()) this.fail(error);
      return false;
    } finally {
      if (key === this.contextKey()) this.pending.set(false);
    }
  }
  ngOnDestroy() {
    ++this.epoch;
    ++this.directoryEpoch;
    this.clearSecret();
    this.releaseAvatars();
  }
}
