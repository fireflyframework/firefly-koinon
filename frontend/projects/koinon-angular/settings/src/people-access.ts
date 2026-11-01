// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  Input,
  OnInit,
  OnDestroy,
  PendingTasks,
  afterNextRender,
  computed,
  effect,
  inject,
  Injector,
  signal,
  untracked,
  viewChild,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import {
  KoinonButton,
  KoinonTextPipe,
  KoinonDatePipe,
  KoinonFacade,
  KoinonClientContext,
  KoinonPagination,
  KoinonSearchField,
  KoinonSkeleton,
} from '@fireflyframework/koinon-angular';
import type {
  Membership,
  Person,
  Invitation,
  InvitationFilter,
} from '@fireflyframework/koinon-sdk';
import {KoinonEmailInvitations} from '@fireflyframework/koinon-angular/communications/invitations';
import { KoinonPeopleService } from './people-service';
export const ACCESS_ROLES = [
  { id: 'viewer', label: 'Viewer', description: 'Read knowledge, search and use chat.' },
  { id: 'analyst', label: 'Analyst', description: 'Read knowledge and run dataset queries.' },
  { id: 'editor', label: 'Editor', description: 'Add and update knowledge and run queries.' },
  {
    id: 'operator',
    label: 'Operator',
    description: 'Manage sources, models, agents and processing.',
  },
  {
    id: 'admin',
    label: 'Administrator',
    description: 'Manage all knowledge settings and people’s access.',
  },
] as const;
@Component({
  selector: 'ffk-people-access',
  imports: [
    KoinonEmailInvitations,
    FormsModule,
    KoinonButton,
    KoinonTextPipe,
    KoinonDatePipe,
    KoinonPagination,
    KoinonSearchField,
    KoinonSkeleton,
  ],
  providers: [KoinonPeopleService],
  templateUrl: './people-access.html',
  styleUrl: './people-access.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonPeopleAccess implements OnInit, OnDestroy {
  @Input() invitationBaseUrl = '';
  readonly emailMode=signal<'list'|'compose'|null>(null);
  openEmail(mode:'list'|'compose',event?:Event){this.openerName=(event?.target instanceof HTMLElement?event.target.closest('button')?.textContent:'')?.trim()??'';this.emailMode.set(mode);}
  closeEmail(){this.emailMode.set(null);this.close();}
  readonly service = inject(KoinonPeopleService);
  readonly facade = inject(KoinonFacade);
  private readonly clients = inject(KoinonClientContext);
  private readonly tasks = inject(PendingTasks);
  private readonly injector = inject(Injector);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  private readonly heading = viewChild<ElementRef<HTMLHeadingElement>>('editorHeading');
  readonly tab = signal<'members' | 'invitations'>('members');
  readonly editor = signal<'existing' | 'invite' | 'edit' | null>(null);
  readonly record = signal<Membership | null>(null);
  readonly removing = signal<Membership | null>(null);
  readonly revoking = signal<Invitation | null>(null);
  readonly selected = signal<Person | null>(null);
  readonly copied = signal(false);
  readonly formError = signal('');
  readonly roles = ACCESS_ROLES;
  query = '';
  roleFilter = '';
  scopeFilter = 'all';
  directoryQuery = '';
  targetScope = '';
  role: Membership['role'] = 'viewer';
  label = '';
  hours = 24;
  inviteStatus: NonNullable<InvitationFilter['status']> = 'pending';
  pageSize = 25;
  private opener: HTMLElement | null = null;
  private openerName = '';
  private context = this.facade.tenantId() + ':' + this.clients.revision();
  readonly workspaces = computed(() =>
    (this.facade.context()?.workspaces ?? []).filter(
      (row) =>
        row.tenant_id === this.facade.tenantId() &&
        row.kind === 'workspace' &&
        row.status !== 'archived',
    ),
  );
  readonly organizationAdmin = computed(() =>
    (this.facade.context()?.memberships ?? []).some(
      (row) =>
        row.tenant_id === this.facade.tenantId() &&
        !row.workspace_id &&
        row.active &&
        row.role === 'admin',
    ),
  );
  constructor() {
    effect(() => {
      const key = this.facade.tenantId() + ':' + this.clients.revision();
      if (key !== this.context) {
        this.context = key;
        this.editor.set(null);
        this.emailMode.set(null);
        this.removing.set(null);
        this.revoking.set(null);
        this.selected.set(null);
        this.query = '';
        this.roleFilter = '';
        untracked(() => this.tasks.run(() => this.initialize()));
      }
    });
  }
  ngOnInit() {
    this.tasks.run(() => this.initialize());
  }
  private initialize() {
    this.scopeFilter = this.organizationAdmin() ? 'all' : this.facade.workspaceId();
    return this.load();
  }
  load(page = 1) {
    return this.service.load({
      q: this.query,
      role: (this.roleFilter as Membership['role']) || undefined,
      scope:
        this.scopeFilter === 'tenant' ? 'tenant' : this.scopeFilter === 'all' ? 'all' : 'workspace',
      workspace_id: ['all', 'tenant'].includes(this.scopeFilter) ? undefined : this.scopeFilter,
      page,
      page_size: this.pageSize,
    });
  }
  navigate(tab: 'members' | 'invitations') {
    this.tab.set(tab);
    this.service.clearSecret();
    this.service.notice.set('');
    this.tasks.run(() => (tab === 'members' ? this.load() : this.loadInvitations()));
  }
  loadInvitations(page = 1) {
    return this.service.loadInvitations({
      status: this.inviteStatus,
      workspace_id: this.organizationAdmin() ? undefined : this.facade.workspaceId() || undefined,
      page,
      page_size: this.pageSize,
    });
  }
  open(kind: 'existing' | 'invite' | 'edit', member: Membership | null = null, event?: Event) {
    this.opener = event?.target instanceof HTMLElement ? event.target.closest('button') : null;
    this.openerName = (this.opener?.getAttribute('aria-label') || this.opener?.textContent || '')
      .trim()
      .replace(/\s+/g, ' ');
    this.editor.set(kind);
    this.record.set(member);
    this.selected.set(null);
    this.role = member?.role ?? 'viewer';
    this.targetScope =
      member?.workspace_id ??
      (this.workspaces().some((row) => row.id === this.facade.workspaceId())
        ? this.facade.workspaceId()
        : '');
    this.label = '';
    this.hours = 24;
    this.directoryQuery = '';
    this.service.directory.set(null);
    this.formError.set('');
    this.service.error.set(null);
    this.service.clearSecret();
    this.copied.set(false);
    afterNextRender(() => this.heading()?.nativeElement.focus(), { injector: this.injector });
  }
  close() {
    this.editor.set(null);
    this.service.clearSecret();
    this.selected.set(null);
    afterNextRender(
      () => {
        const buttons = Array.from(
          this.host.nativeElement.querySelectorAll<HTMLButtonElement>('button'),
        );
        const restored = buttons.find(
          (button) =>
            (button.getAttribute('aria-label') || button.textContent || '')
              .trim()
              .replace(/\s+/g, ' ') === this.openerName,
        );
        (restored ?? buttons[0])?.focus();
      },
      { injector: this.injector },
    );
  }
  select(person: Person) {
    this.selected.set(person);
  }
  name(member: Membership) {
    return (
      this.service.members()?.actors?.[member.subject]?.display_name ||
      (member.subject === this.facade.context()?.subject ? 'You' : 'Unnamed member')
    );
  }
  avatar(member: Membership) {
    return this.service.members()?.actors?.[member.subject]?.avatar_data_url;
  }
  initials(name: string) {
    return (
      name
        .trim()
        .split(/\s+/)
        .slice(0, 2)
        .map((part) => part[0])
        .join('')
        .toUpperCase() || '?'
    );
  }
  scopeName(workspace: string | null) {
    return workspace
      ? (this.workspaces().find((row) => row.id === workspace)?.name ?? 'Workspace')
      : 'Entire organization';
  }
  roleName(role: string) {
    return this.roles.find((value) => value.id === role)?.label ?? role;
  }
  invitationStatusLabel(status: Invitation['status']) {
    return { pending: 'Pending', accepted: 'Accepted', expired: 'Expired', revoked: 'Revoked' }[
      status
    ];
  }
  roleDescription() {
    return this.roles.find((value) => value.id === this.role)?.description ?? '';
  }
  async save() {
    this.formError.set('');
    if (this.editor() === 'existing' && !this.selected()) {
      this.formError.set('Choose a person from the directory.');
      return;
    }
    if (!this.organizationAdmin() && !this.targetScope) {
      this.formError.set('Choose a workspace you administer.');
      return;
    }
    if (this.editor() === 'invite') {
      if (!this.invitationBaseUrl) {
        this.formError.set('Invitation links are available in the management application.');
        return;
      }
      await this.service.invite({
        role: this.role,
        workspace_id: this.targetScope || null,
        label: this.label,
        expires_in_hours: this.hours,
      });
      return;
    }
    const existing = this.record();
    const saved = await this.service.save(
      existing
        ? { role: this.role }
        : {
            subject: this.selected()!.subject,
            role: this.role,
            workspace_id: this.targetScope || null,
          },
      existing,
    );
    if (saved) this.close();
  }
  invitationLink() {
    const token = this.service.created()?.token;
    if (!token || !this.invitationBaseUrl) return '';
    try {
      const url = new URL(this.invitationBaseUrl);
      if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password) return '';
      url.hash = 'invite=' + encodeURIComponent(token);
      return url.toString();
    } catch {
      return '';
    }
  }
  async copyLink() {
    try {
      await navigator.clipboard.writeText(this.invitationLink());
      this.copied.set(true);
    } catch {
      this.formError.set('Copy is unavailable. Select and copy the invitation link.');
    }
  }
  async remove() {
    const member = this.removing();
    if (member && (await this.service.remove(member))) this.removing.set(null);
  }
  async revoke() {
    const invitation = this.revoking();
    if (invitation && (await this.service.revoke(invitation))) {
      this.revoking.set(null);
      await this.loadInvitations();
    }
  }
  errorHelp() {
    const error = this.service.error();
    if (!error) return '';
    const code = 'code' in error ? error.code : '';
    return code === 'LAST_ADMIN'
      ? 'Keep at least one administrator for this organization.'
      : code === 'MEMBERSHIP_EXISTS'
        ? 'This person already has access in this scope. Edit their existing role.'
        : 'status' in error && error.status === 403
          ? 'You do not have permission to manage access in this scope.'
          : 'Access could not be saved or loaded. Try again.';
  }
  ngOnDestroy() {
    this.service.clearSecret();
  }
}
