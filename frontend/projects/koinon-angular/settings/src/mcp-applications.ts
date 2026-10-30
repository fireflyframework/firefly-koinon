// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import {
  ChangeDetectionStrategy,
  Component,
  PendingTasks,
  computed,
  effect,
  inject,
  signal,
  untracked,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import {
  KoinonBadge,
  KoinonButton,
  KoinonDatePipe,
  KoinonIcon,
  KoinonPagination,
  KoinonSearchField,
  KoinonTextPipe,
} from '@fireflyframework/koinon-angular';
import { registerKoinonSpanish } from '@fireflyframework/koinon-angular/workbench';
import type {
  McpOAuthClient,
  McpOAuthClientInput,
  McpOAuthScope,
} from '@fireflyframework/koinon-sdk';
import { KoinonMcpApplicationsState } from './mcp-applications-state';
import { MCP_APPLICATIONS_SPANISH } from './mcp-applications-spanish';
registerKoinonSpanish(MCP_APPLICATIONS_SPANISH);

export function callbackIssue(value: string): string {
  const urls = value
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean);
  if (!urls.length || urls.length > 8)
    return 'Enter between one and eight callback URLs, one per line.';
  if (new Set(urls).size !== urls.length) return 'Each callback URL must be distinct.';
  for (const raw of urls) {
    try {
      const url = new URL(raw),
        local =
          url.hostname === 'localhost' ||
          url.hostname === '[::1]' ||
          /^127(?:\.\d{1,3}){3}$/.test(url.hostname);
      if (
        !/^https?:\/\/[^/]/i.test(raw) ||
        raw.length > 2048 ||
        /[^\x21-\x7e]|[*\\]/.test(raw) ||
        url.username ||
        url.password ||
        url.hash ||
        (url.protocol !== 'https:' && !(url.protocol === 'http:' && local))
      )
        throw new Error();
    } catch {
      return 'Use exact HTTPS callback URLs without wildcards, credentials or fragments. HTTP is allowed only for local development.';
    }
  }
  return '';
}
export function applicationScopes(
  current: McpOAuthScope[],
  scope: McpOAuthScope,
  checked: boolean,
): McpOAuthScope[] {
  const values = new Set(current);
  if (checked) values.add(scope);
  else values.delete(scope);
  if (scope === 'catalog:write' && !checked) values.delete('ingest:write');
  if (values.has('ingest:write')) values.add('catalog:write');
  values.add('catalog:read');
  return [...values].sort();
}

@Component({
  selector: 'ffk-mcp-applications',
  imports: [
    FormsModule,
    KoinonBadge,
    KoinonButton,
    KoinonDatePipe,
    KoinonIcon,
    KoinonPagination,
    KoinonSearchField,
    KoinonTextPipe,
  ],
  providers: [KoinonMcpApplicationsState],
  templateUrl: './mcp-applications.html',
  styleUrl: './mcp-applications.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonMcpApplications {
  readonly state = inject(KoinonMcpApplicationsState);
  private readonly tasks = inject(PendingTasks);
  readonly editor = signal<'create' | 'edit' | null>(null);
  readonly step = signal(1);
  readonly name = signal('');
  readonly callbacks = signal('');
  readonly clientType = signal<McpOAuthClientInput['client_type']>('public');
  readonly scopes = signal<McpOAuthScope[]>(['catalog:read']);
  readonly enabled = signal(true);
  readonly acknowledged = signal(false);
  readonly revealSecret = signal(false);
  readonly localNotice = signal('');
  readonly confirmation = signal<{
    kind: 'disable' | 'rotate';
    id: string;
    name: string;
    revision: number;
    identity: number;
  } | null>(null);
  private formIdentity = -1;
  private formRecord: McpOAuthClient | null = null;
  query = '';
  readonly callbackProblem = computed(() => callbackIssue(this.callbacks()));
  readonly nameProblem = computed(() =>
    !this.name().trim() || this.name().length > 120 || /[\p{C}\p{Zl}\p{Zp}]/u.test(this.name())
      ? 'Enter an application name of up to 120 characters.'
      : '',
  );
  readonly valid = computed(() => !this.nameProblem() && !this.callbackProblem());
  readonly scopeOptions: { id: McpOAuthScope; label: string; help: string }[] = [
    {
      id: 'catalog:read',
      label: 'Browse knowledge',
      help: 'Find folders, files and datasets. Required for every application.',
    },
    {
      id: 'knowledge:search',
      label: 'Search knowledge',
      help: 'Search the organization’s permitted knowledge.',
    },
    { id: 'query:execute', label: 'Query datasets', help: 'Ask questions about structured data.' },
    {
      id: 'chat:use',
      label: 'Inspect saved answers',
      help: 'Inspect existing answer audits when Read answer evidence is also allowed.',
    },
    {
      id: 'evidence:read',
      label: 'Read answer evidence',
      help: 'Inspect sources and the execution audit.',
    },
    {
      id: 'catalog:write',
      label: 'Maintain knowledge',
      help: 'Propose changes for human review in a compatible chat application.',
    },
    {
      id: 'ingest:write',
      label: 'Upload files',
      help: 'Upload files after human review. Includes Maintain knowledge.',
    },
  ];
  readonly setupLabels: Record<string, string> = {
    mcp_endpoint: 'Enable the MCP endpoint.',
    oauth_enabled: 'Enable OAuth connections.',
    oauth_encryption_key: 'Configure an OAuth encryption key.',
  };
  constructor() {
    effect(() => {
      this.state.identity();
      const allowed = this.state.allowed();
      untracked(() => {
        this.closeEditor();
        this.confirmation.set(null);
        this.revealSecret.set(false);
        this.localNotice.set('');
        this.query = '';
        if (allowed) this.tasks.run(() => this.state.reload());
      });
    });
  }
  beginCreate() {
    if (!this.state.canWrite()) return;
    this.state.closeDetail();
    this.resetForm();
    this.formRecord = null;
    this.clientType.set('public');
    this.enabled.set(true);
    this.name.set('');
    this.callbacks.set('');
    this.scopes.set(['catalog:read']);
    this.editor.set('create');
  }
  async open(id: string) {
    this.closeEditor();
    this.confirmation.set(null);
    await this.state.open(id);
  }
  beginEdit() {
    const row = this.state.detail();
    if (!row || !this.state.canWrite()) return;
    this.resetForm();
    this.formRecord = structuredClone(row);
    this.name.set(row.name);
    this.callbacks.set(row.redirect_uris.join('\n'));
    this.clientType.set(row.client_type);
    this.enabled.set(row.enabled);
    this.scopes.set([...row.scopes]);
    this.editor.set('edit');
  }
  private resetForm() {
    this.formIdentity = this.state.identity();
    this.step.set(1);
    this.acknowledged.set(false);
    this.localNotice.set('');
    this.confirmation.set(null);
    this.state.dismissSecret();
    this.revealSecret.set(false);
  }
  closeEditor() {
    this.editor.set(null);
    this.formRecord = null;
    this.formIdentity = -1;
    this.acknowledged.set(false);
  }
  scope(id: McpOAuthScope, event: Event) {
    this.scopes.set(
      applicationScopes(this.scopes(), id, (event.target as HTMLInputElement).checked),
    );
  }
  next() {
    if (this.valid() && this.step() < 3) {
      this.step.update((value) => value + 1);
      this.acknowledged.set(false);
    }
  }
  previous() {
    this.step.update((value) => Math.max(1, value - 1));
    this.acknowledged.set(false);
  }
  async save() {
    if (
      !this.editor() ||
      this.step() !== 3 ||
      !this.valid() ||
      !this.acknowledged() ||
      !this.state.canWrite()
    )
      return;
    const values = {
      name: this.name().trim(),
      redirect_uris: this.callbacks()
        .split('\n')
        .map((line) => line.trim())
        .filter(Boolean),
      scopes: [...this.scopes()],
    };
    const result =
      this.editor() === 'create'
        ? await this.state.create({ ...values, client_type: this.clientType() }, this.formIdentity)
        : this.formRecord &&
          (await this.state.update(
            this.formRecord.id,
            { ...values, enabled: this.enabled(), expected_revision: this.formRecord.revision },
            this.formIdentity,
          ));
    if (result || this.state.stale()) this.closeEditor();
  }
  confirm(kind: 'disable' | 'rotate') {
    const row = this.state.detail();
    if (
      !row ||
      !this.state.canWrite() ||
      (kind === 'disable' && !row.enabled) ||
      (kind === 'rotate' && row.client_type !== 'confidential')
    )
      return;
    this.acknowledged.set(false);
    this.confirmation.set({
      kind,
      id: row.id,
      name: row.name,
      revision: row.revision,
      identity: this.state.identity(),
    });
  }
  async applyConfirmation() {
    const action = this.confirmation();
    if (!action || !this.acknowledged()) return;
    const result =
      action.kind === 'disable'
        ? await this.state.disable(action.id, action.identity, action.revision)
        : await this.state.rotateSecret(action.id, action.identity, action.revision);
    if (result || this.state.stale()) this.confirmation.set(null);
    this.acknowledged.set(false);
  }
  async copySecret() {
    const credential = this.state.secret();
    if (!credential?.client_secret) return;
    try {
      await navigator.clipboard.writeText(credential.client_secret);
      if (this.state.secret() === credential)
        this.localNotice.set('Secret copied. Store it securely before closing this view.');
    } catch {
      if (this.state.secret() === credential)
        this.localNotice.set('The secret could not be copied. Reveal it and copy it manually.');
    }
  }
  dismissSecret() {
    this.state.dismissSecret();
    this.revealSecret.set(false);
    this.localNotice.set('');
  }
  filter() {
    this.tasks.run(() => this.state.load({ q: this.query, page: 1 }));
  }
  status(value: 'all' | 'enabled' | 'disabled') {
    this.tasks.run(() => this.state.load({ status: value, page: 1 }));
  }
  sort(value: 'name' | 'updated_at') {
    this.tasks.run(() => this.state.load({ sort: value, page: 1 }));
  }
  order(value: 'asc' | 'desc') {
    this.tasks.run(() => this.state.load({ order: value, page: 1 }));
  }
}
