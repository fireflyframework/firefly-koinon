// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import {
  ChangeDetectionStrategy,
  Component,
  Input,
  OnInit,
  ViewChild,
  PendingTasks,
  effect,
  inject,
  signal,
  untracked,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import {
  KoinonButton,
  KoinonFacade,
  KoinonFilterBar,
  KoinonSidePanel,
  KoinonIcon,
  KoinonDatePipe,
  KoinonI18n,
  KoinonPagination,
  KoinonSearchField,
  KoinonSkeleton,
  KoinonTextPipe,
  KoinonValuePipe,
} from '@fireflyframework/koinon-angular';
import { KoinonError, type AuditEvent, type AuditFilter } from '@fireflyframework/koinon-sdk';
import { KoinonAuditService } from './audit-service';
import {
  auditChips,
  auditDirty,
  auditRequest,
  emptyAuditDraft,
  type AuditDraft,
  type AuditChip,
} from './audit-filters';
const ACTIONS = [
  ['catalog.created', 'Knowledge created'],
  ['catalog.updated', 'Knowledge updated'],
  ['catalog.archived', 'Knowledge archived'],
  ['catalog.restored', 'Knowledge restored'],
  ['membership.created', 'Membership created'],
  ['membership.updated', 'Membership updated'],
  ['invitation.created', 'Invitation created'],
  ['invitation.accepted', 'Invitation accepted'],
  ['invitation.revoked', 'Invitation revoked'],
  ['token.created', 'API token created'],
  ['token.revoked', 'API token revoked'],
  ['identity.provider.created', 'Corporate connection created'],
  ['identity.provider.updated', 'Corporate connection updated'],
  ['identity.provider.activated', 'Corporate connection activated'],
  ['identity.provider.disabled', 'Corporate connection disabled'],
] as const;
@Component({
  selector: 'ffk-audit-panel',
  imports: [
    FormsModule,
    KoinonButton,
    KoinonFilterBar,
    KoinonSidePanel,
    KoinonIcon,
    KoinonDatePipe,
    KoinonPagination,
    KoinonSearchField,
    KoinonSkeleton,
    KoinonTextPipe,
    KoinonValuePipe,
  ],
  providers: [KoinonAuditService],
  templateUrl: './audit-panel.html',
  styleUrl: './audit-panel.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonAuditPanel implements OnInit {
  @Input() resource?: (id: string) => void;
  readonly service = inject(KoinonAuditService);
  readonly i18n = inject(KoinonI18n);
  private readonly tasks = inject(PendingTasks);
  private readonly facade = inject(KoinonFacade);
  @ViewChild(KoinonSidePanel) private detailPanel?: KoinonSidePanel;
  readonly selected = signal<AuditEvent | null>(null);
  readonly selectedActor = signal<{ name: string; avatar: string | null } | null>(null);
  readonly expanded = signal(false);
  readonly applied = signal<AuditDraft>(emptyAuditDraft());
  readonly actions = ACTIONS;
  readonly person = signal<{ subject: string; name: string } | null>(null);
  readonly validation = signal('');
  query = '';
  action = '';
  from = '';
  through = '';
  sort = 'newest';
  private key = this.service.scope();
  constructor() {
    effect(() => {
      const key = this.service.scope();
      if (key !== this.key) {
        this.key = key;
        untracked(() => {
          this.closeDetails();
          this.clear();
        });
      }
    });
    effect(() => {
      if (this.facade.authRequired()) untracked(() => this.closeDetails());
    });
  }
  ngOnInit() {
    this.load();
  }
  draftState(): AuditDraft {
    return {
      q: this.query,
      action: this.action,
      from: this.from,
      through: this.through,
      sort: this.sort,
      subject: this.person()?.subject ?? '',
      personName: this.person()?.name ?? '',
    };
  }
  draftChanged() {
    return auditDirty(this.draftState(), this.applied());
  }
  chips() {
    return auditChips(this.applied());
  }
  apply() {
    const next = this.draftState();
    try {
      auditRequest(next);
      this.validation.set('');
    } catch (error) {
      this.validation.set(
        error instanceof Error ? error.message : 'Check the audit filters and try again.',
      );
      return;
    }
    this.applied.set({ ...next, q: next.q.trim() });
    this.load();
  }
  load(page = 1, pageSize?: number) {
    const filter: AuditFilter = auditRequest(
      this.applied(),
      page,
      pageSize ?? this.service.filters().page_size ?? 25,
    );
    this.tasks.run(() => this.service.load(filter));
  }
  refresh() {
    this.load(this.service.filters().page ?? 1);
  }
  resetDraft() {
    const value = this.applied();
    this.query = value.q;
    this.action = value.action;
    this.from = value.from;
    this.through = value.through;
    this.sort = value.sort;
    this.person.set(value.subject ? { subject: value.subject, name: value.personName } : null);
    this.validation.set('');
  }
  clear() {
    this.applied.set(emptyAuditDraft());
    this.resetDraft();
    this.load();
  }
  filterPerson(event: AuditEvent) {
    const selected = { subject: event.subject, name: this.personName(event.subject) };
    this.person.set(selected);
    this.applied.update((value) => ({
      ...value,
      subject: selected.subject,
      personName: selected.name,
    }));
    this.load();
  }
  clearPerson() {
    this.person.set(null);
    this.applied.update((value) => ({ ...value, subject: '', personName: '' }));
    this.load();
  }
  removeChip(id: AuditChip['id']) {
    const value = this.applied(),
      next = { ...value };
    if (id === 'q') {
      next.q = '';
      if (this.query.trim() === value.q) this.query = '';
    }
    if (id === 'action') {
      next.action = '';
      if (this.action === value.action) this.action = '';
    }
    if (id === 'dates') {
      next.from = '';
      next.through = '';
      if (this.from === value.from) this.from = '';
      if (this.through === value.through) this.through = '';
    }
    if (id === 'sort') {
      next.sort = 'newest';
      if (this.sort === value.sort) this.sort = 'newest';
    }
    if (id === 'subject') {
      this.clearPerson();
      return;
    }
    this.applied.set(next);
    this.load();
  }
  openDetails(event: AuditEvent) {
    this.selectedActor.set({
      name: this.personName(event.subject),
      avatar: this.avatar(event.subject),
    });
    this.selected.set(event);
  }
  closeDetails() {
    this.selected.set(null);
    this.selectedActor.set(null);
  }
  openKnowledge(event: AuditEvent) {
    this.detailPanel?.dismiss();
    this.resource?.(event.resource_id!);
  }
  observedTarget(event: AuditEvent) {
    for (const key of ['resource_name', 'name', 'title']) {
      const value = event.details[key];
      if (typeof value === 'string' && value.trim()) return value;
    }
    return null;
  }
  targetName(event: AuditEvent) {
    for (const key of ['resource_name', 'name', 'title']) {
      const value = event.details[key];
      if (typeof value === 'string' && value.trim()) return value;
    }
    if (!event.resource_id) return this.i18n.text('Not recorded');
    const prefix = event.action.split('.')[0];
    return this.i18n.text(
      prefix === 'catalog'
        ? 'Knowledge item'
        : prefix === 'membership'
          ? 'Role assignment'
          : prefix === 'invitation'
            ? 'Invitation'
            : prefix === 'token'
              ? 'API token'
              : prefix === 'identity'
                ? 'Corporate connection'
                : 'Recorded resource',
    );
  }
  rawDetails(event: AuditEvent) {
    return JSON.stringify(event.details, null, 2);
  }
  personName(subject: string) {
    return this.service.page()?.actors?.[subject]?.display_name || this.i18n.text('Unnamed person');
  }
  avatar(subject: string) {
    return this.service.page()?.actors?.[subject]?.avatar_data_url ?? null;
  }
  initials(subject: string) {
    return this.personName(subject)
      .trim()
      .split(/\s+/)
      .slice(0, 2)
      .map((word) => Array.from(word)[0])
      .join('')
      .toLocaleUpperCase();
  }
  actionName(action: string) {
    return (
      ACTIONS.find((row) => row[0] === action)?.[1] ??
      action.replace(/[._]+/g, ' ').replace(/^./, (letter) => letter.toUpperCase())
    );
  }
  details(event: AuditEvent) {
    return Object.entries(event.details).filter(
      ([key, value]) =>
        !key.endsWith('_id') &&
        !key.endsWith('_ids') &&
        (value === null || ['string', 'number', 'boolean'].includes(typeof value)),
    );
  }
  detailValue(key: string, value: unknown) {
    if (key === 'role' && typeof value === 'string') {
      const labels: Record<string, string> = {
        viewer: 'Viewer',
        analyst: 'Analyst',
        editor: 'Editor',
        operator: 'Operator',
        admin: 'Administrator',
      };
      return this.i18n.text(labels[value] ?? value);
    }
    if (typeof value === 'boolean') return this.i18n.text(value ? 'Yes' : 'No');
    if (value === null) return this.i18n.text('Not recorded');
    return value;
  }
  label(key: string) {
    return key.replace(/[._]+/g, ' ').replace(/^./, (letter) => letter.toUpperCase());
  }
  canOpen(event: AuditEvent) {
    return Boolean(
      this.resource &&
      event.resource_id &&
      ['catalog.created', 'catalog.updated', 'catalog.restored'].includes(event.action),
    );
  }
  errorHelp() {
    const error = this.service.error();
    if (error instanceof KoinonError) {
      if (error.status === 401) return 'Your session has expired. Sign in again.';
      if (error.status === 403)
        return 'You do not have permission to read this organization’s audit activity.';
      if (error.status === 400) return 'Check the audit filters and try again.';
    }
    return 'Try again. If the problem continues, contact your administrator.';
  }
  hasFilters() {
    return this.chips().length > 0;
  }
}
