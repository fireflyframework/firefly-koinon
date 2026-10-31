// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import {
  ChangeDetectionStrategy,
  Component,
  OnDestroy,
  OnInit,
  PendingTasks,
  computed,
  effect,
  inject,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import {
  KoinonButton,
  KoinonClientContext,
  KoinonFacade,
  KoinonIcon,
  KoinonTextPipe,
} from '@fireflyframework/koinon-angular';
import { registerKoinonSpanish } from '@fireflyframework/koinon-angular/workbench';
import type {
  AgentConfiguration,
  OrganizationChatSettings,
  OrganizationMemoryPolicy,
} from '@fireflyframework/koinon-sdk';
import { ORGANIZATION_CHAT_SPANISH } from './organization-chat-spanish';
registerKoinonSpanish(ORGANIZATION_CHAT_SPANISH);
@Component({
  selector: 'ffk-organization-chat-settings',
  imports: [FormsModule, KoinonButton, KoinonIcon, KoinonTextPipe],
  templateUrl: './organization-chat-settings.html',
  styleUrl: './organization-chat-settings.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonOrganizationChatSettings implements OnInit, OnDestroy {
  private readonly f = inject(KoinonFacade);
  private readonly clients = inject(KoinonClientContext);
  private readonly tasks = inject(PendingTasks);
  private epoch = 0;
  private key = this.contextKey();
  readonly allowed = computed(() => this.f.tenantPermissions().has('agents:write'));
  readonly settings = signal<OrganizationChatSettings | null>(null);
  readonly agents = signal<AgentConfiguration[]>([]);
  readonly selectedId = signal('');
  readonly memory = signal<Required<OrganizationMemoryPolicy>>({
    allow_project_memory: true,
    max_history_messages: 40,
    max_history_tokens: 8192,
    max_project_memory_messages: 20,
  });
  readonly memoryChanged = computed(() => {
    const saved = this.settings()?.memory;
    return (
      !!saved &&
      (Object.keys(this.memory()) as (keyof OrganizationMemoryPolicy)[]).some(
        (key) => this.memory()[key] !== saved[key],
      )
    );
  });
  readonly memoryError = computed(() => {
    const policy = this.memory();
    if (
      [policy.max_history_messages, policy.max_project_memory_messages].some(
        (value) => typeof value !== 'number' || !Number.isInteger(value) || value < 0 || value > 40,
      ) ||
      typeof policy.max_history_tokens !== 'number' ||
      !Number.isInteger(policy.max_history_tokens) ||
      policy.max_history_tokens < 0 ||
      policy.max_history_tokens > 65536
    )
      return 'Enter whole numbers within the memory limits.';
    return policy.max_project_memory_messages > policy.max_history_messages
      ? 'Project memory cannot exceed the total history limit.'
      : '';
  });
  updateMemory<K extends keyof OrganizationMemoryPolicy>(
    key: K,
    value: Required<OrganizationMemoryPolicy>[K],
  ) {
    this.memory.update((policy) => ({ ...policy, [key]: value }));
  }
  readonly pending = signal(false);
  readonly saving = signal(false);
  readonly stale = signal(false);
  readonly error = signal('');
  readonly notice = signal('');
  readonly missingDefault = computed(() => {
    const id = this.settings()?.default_agent_id;
    return id && !this.agents().some((agent) => agent.id === id) ? id : '';
  });
  readonly canSave = computed(
    () =>
      this.allowed() &&
      !!this.settings() &&
      !this.pending() &&
      !this.saving() &&
      !this.stale() &&
      !this.memoryError() &&
      ((this.selectedId() || null) !== this.settings()?.default_agent_id || this.memoryChanged()),
  );
  constructor() {
    effect(() => {
      const key = this.contextKey();
      if (key !== this.key) {
        this.key = key;
        ++this.epoch;
        this.settings.set(null);
        this.agents.set([]);
        this.selectedId.set('');
        this.pending.set(false);
        this.saving.set(false);
        this.error.set('');
        this.notice.set('');
        this.tasks.run(() => this.load());
      }
    });
  }
  ngOnInit() {
    this.tasks.run(() => this.load());
  }
  private contextKey() {
    return (
      this.f.tenantId() +
      ':' +
      this.clients.revision() +
      ':' +
      this.f.tenantPermissions().has('agents:write')
    );
  }
  private current(epoch: number) {
    return epoch === this.epoch && this.key === this.contextKey() && this.allowed();
  }
  private fail(error: unknown) {
    if (error instanceof Error && 'status' in error && error.status === 401)
      this.f.authRequired.set(true);
    this.error.set(
      error instanceof Error ? error.message : 'Organization chat settings could not be loaded.',
    );
  }
  async load() {
    if (!this.allowed()) return;
    const epoch = ++this.epoch,
      tenant = this.f.tenantId(),
      client = this.clients.get();
    this.pending.set(true);
    this.error.set('');
    this.notice.set('');
    this.stale.set(true);
    try {
      const [settings, agents] = await Promise.all([
        client.organizationChat.get(tenant),
        (async () => {
          const result: AgentConfiguration[] = [];
          let page = 1;
          for (;;) {
            const response = await client.agents.list(tenant, { query: { page, page_size: 100 } });
            if (!this.current(epoch)) return [];
            result.push(
              ...response.items.filter((agent) => !Object.keys(agent.scope ?? {}).length),
            );
            if (!response.pages || page >= response.pages) return result;
            ++page;
          }
        })(),
      ]);
      if (!this.current(epoch)) return;
      this.settings.set(settings);
      this.agents.set(agents);
      this.selectedId.set(settings.default_agent_id ?? '');
      if (settings.memory) this.memory.set({ ...this.memory(), ...settings.memory });
      this.stale.set(false);
    } catch (error) {
      if (this.current(epoch)) this.fail(error);
    } finally {
      if (this.current(epoch)) this.pending.set(false);
    }
  }
  async save() {
    if (!this.canSave()) return;
    const epoch = this.epoch,
      tenant = this.f.tenantId();
    this.saving.set(true);
    this.error.set('');
    this.notice.set('');
    try {
      const value = await this.clients.get().organizationChat.update(tenant, {
        default_agent_id: this.selectedId() || null,
        expected_revision: this.settings()!.revision,
        ...(this.memoryChanged() ? { memory: this.memory() } : {}),
      });
      if (!this.current(epoch)) return;
      this.settings.set(value);
      this.selectedId.set(value.default_agent_id ?? '');
      if (value.memory) this.memory.set({ ...this.memory(), ...value.memory });
      this.notice.set('Organization chat saved.');
    } catch (error) {
      if (this.current(epoch)) {
        if (error instanceof Error && 'status' in error && error.status === 409) {
          this.stale.set(true);
          this.error.set('Organization chat changed. Reload the settings before saving again.');
        } else this.fail(error);
      }
    } finally {
      if (this.current(epoch)) this.saving.set(false);
    }
  }
  ngOnDestroy() {
    ++this.epoch;
  }
}
