// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { Injectable, OnDestroy, computed, effect, inject, signal } from '@angular/core';
import type {
  AttachmentCapabilities,
  AttachmentView,
  AttachmentHistorySummary,
} from '@fireflyframework/koinon-sdk';
import {
  KoinonAssistant,
  KoinonClientContext,
  KoinonFacade,
} from '@fireflyframework/koinon-angular';
import type { ComposerAttachment } from '../composer/composer-models';
interface DraftFile {
  key: string;
  file: File;
  uploadKey: string;
  remote?: AttachmentView;
  previewUrl?: string;
  state: ComposerAttachment['state'];
  detail?: string;
  removing?: boolean;
}
@Injectable()
export class KoinonChatAttachments implements OnDestroy {
  private readonly facade = inject(KoinonFacade);
  private readonly assistant = inject(KoinonAssistant);
  private readonly clients = inject(KoinonClientContext);
  private readonly rows = signal<DraftFile[]>([]);
  readonly error = signal('');
  readonly selecting = signal(false);
  readonly capabilities = signal<AttachmentCapabilities | null>(null);
  readonly checking = signal(false);
  private bound = '';
  private generation = 0;
  private readonly aborts = new Set<AbortController>();
  private timer?: ReturnType<typeof setTimeout>;
  private polling = false;
  private expiryTimer?: ReturnType<typeof setTimeout>;
  private readonly now = signal(Date.now());
  readonly enabled = computed(() => {
    const value = this.capabilities();
    return (
      !!value &&
      value.storage.available === true &&
      value.database.available === true &&
      value.extraction.available !== false
    );
  });
  readonly unavailableReason = computed(() => {
    if (this.checking()) return 'Checking file availability…';
    const value = this.capabilities();
    if (!value) return 'File uploads are not enabled in this workspace.';
    if (value.storage.available !== true || value.database.available !== true)
      return 'File uploads are not configured. Ask your administrator to enable private file storage.';
    if (value.extraction.available === false)
      return 'File processing is unavailable. Ask your administrator to check the file worker.';
    return '';
  });
  readonly attachments = computed<ComposerAttachment[]>(() =>
    this.rows().map((row) => ({
      id: row.key,
      name: row.file.name,
      size: row.file.size,
      mediaType: row.file.type || row.remote?.media_type || 'application/octet-stream',
      state: row.state,
      removeDisabled: row.state === 'uploading' || !!row.removing,
      ...(row.previewUrl ? { previewUrl: row.previewUrl } : {}),
      ...(row.remote ? { progress: row.remote.progress.percent } : {}),
      ...(row.detail ? { detail: row.detail } : {}),
    })),
  );
  readonly ids = computed(() =>
    this.rows().flatMap((row) =>
      row.remote?.status === 'ready' &&
      !row.removing &&
      Date.parse(row.remote.expires_at) > this.now()
        ? [row.remote.id]
        : [],
    ),
  );
  readonly ready = computed(() =>
    this.rows().every(
      (row) =>
        row.state === 'ready' &&
        !row.removing &&
        !!row.remote &&
        Date.parse(row.remote.expires_at) > this.now() &&
        (row.remote.kind !== 'image' ||
          !!this.assistant.selectedAgent()?.input_modalities?.includes('image')),
    ),
  );
  readonly modelHint = computed(() =>
    this.rows().some((row) => row.remote?.kind === 'image') &&
    !this.assistant.selectedAgent()?.input_modalities?.includes('image')
      ? 'Choose an agent that supports images to send these files.'
      : '',
  );
  readonly downloading = signal(new Set<string>());
  readonly accept = computed(
    () =>
      this.capabilities()
        ?.formats.filter(
          (format) =>
            format.extraction.available === true &&
            (format.kind !== 'image' ||
              this.assistant.selectedAgent()?.input_modalities?.includes('image')),
        )
        .flatMap((format) => format.extensions)
        .join(',') ?? '',
  );
  constructor() {
    effect(() => {
      this.switchContext();
      const global = this.facade.capabilities()?.attachments;
      if (global && !this.assistant.threadId()) this.capabilities.set(global);
    });
  }
  private contextKey() {
    return [
      this.facade.tenantId(),
      this.assistant.threadId(),
      this.assistant.contextVersion(),
      this.clients.revision(),
    ].join(':');
  }
  private switchContext() {
    const key = this.contextKey();
    if (key === this.bound) return;
    this.reset();
    this.bound = key;
    if (this.assistant.threadId()) void this.check();
  }
  async check() {
    const thread = this.assistant.threadId(),
      tenant = this.facade.tenantId();
    if (!thread || !tenant) return;
    const generation = this.generation;
    this.checking.set(true);
    try {
      const value = await this.clients.get().chat.attachments.capabilities(tenant, thread);
      if (generation === this.generation) this.capabilities.set(value);
    } catch (error) {
      if (generation === this.generation) this.failure(error);
    } finally {
      if (generation === this.generation) this.checking.set(false);
    }
  }
  private failure(error: unknown) {
    if (error instanceof Error && 'status' in error && error.status === 401)
      this.facade.authRequired.set(true);
    this.error.set(
      error instanceof Error ? error.message : 'The file could not be processed. Try again.',
    );
  }
  async select(files: File[]) {
    if (!this.enabled() || this.selecting() || this.assistant.running() || this.assistant.pending())
      return;
    this.error.set('');
    const limits = this.capabilities()!.limits;
    const accepted: File[] = [];
    for (const file of files) {
      if (this.rows().length + accepted.length >= limits.max_selected) {
        this.error.set(`You can attach up to ${limits.max_selected} files to a message.`);
        break;
      }
      const format = this.capabilities()!.formats.find(
        (format) =>
          format.extensions.some((extension) =>
            file.name.toLowerCase().endsWith(extension.toLowerCase()),
          ) && format.extraction.available === true,
      );
      if (!format) {
        this.error.set('This file type is not supported by the configured file processor.');
        continue;
      }
      if (
        format.kind === 'image' &&
        !this.assistant.selectedAgent()?.input_modalities?.includes('image')
      ) {
        this.error.set('Choose an agent that supports images before attaching an image.');
        continue;
      }
      if (
        !file.size ||
        file.size >
          Math.min(
            limits.max_file_bytes,
            format.kind === 'image' ? limits.max_image_bytes : Infinity,
          )
      ) {
        this.error.set('This file is empty or exceeds the workspace file size limit.');
        continue;
      }
      accepted.push(file);
    }
    if (!accepted.length) return;
    this.selecting.set(true);
    const thread = await this.assistant.ensureThread();
    if (!thread) {
      this.selecting.set(false);
      return;
    }
    this.switchContext();
    this.selecting.set(true);
    const generation = this.generation;
    for (const file of accepted) {
      if (generation !== this.generation) break;
      const key = crypto.randomUUID();
      const previewUrl = ['image/png', 'image/jpeg', 'image/webp', 'image/gif'].includes(file.type)
        ? URL.createObjectURL(file)
        : undefined;
      const row: DraftFile = {
        key,
        file,
        uploadKey: crypto.randomUUID(),
        state: 'uploading',
        ...(previewUrl ? { previewUrl } : {}),
      };
      this.rows.update((rows) => [...rows, row]);
      await this.upload(row, generation);
    }
    if (generation === this.generation) this.selecting.set(false);
  }
  private update(key: string, patch: Partial<DraftFile>) {
    this.rows.update((rows) => rows.map((row) => (row.key === key ? { ...row, ...patch } : row)));
  }
  private async upload(row: DraftFile, generation: number) {
    const abort = new AbortController();
    this.aborts.add(abort);
    try {
      const remote = await this.clients
        .get()
        .chat.attachments.upload(
          this.facade.tenantId(),
          this.assistant.threadId(),
          row.file,
          row.uploadKey,
          { filename: row.file.name, signal: abort.signal },
        );
      if (generation !== this.generation) return;
      this.received(row.key, remote);
      this.schedule();
    } catch (error) {
      if (generation === this.generation) {
        this.update(row.key, {
          state: 'failed',
          detail: 'Upload failed. Retry to resume this file.',
        });
        this.failure(error);
      }
    } finally {
      this.aborts.delete(abort);
    }
  }
  private received(key: string, remote: AttachmentView) {
    this.update(key, {
      remote,
      state:
        remote.status === 'ready'
          ? 'ready'
          : ['storing', 'queued', 'extracting'].includes(remote.status)
            ? 'processing'
            : 'failed',
      detail:
        remote.error ||
        (['expired', 'deleted', 'cancelled'].includes(remote.status)
          ? 'This file is unavailable. Remove it or upload it again.'
          : undefined),
    });
    this.scheduleExpiry();
  }
  private scheduleExpiry() {
    if (this.expiryTimer) clearTimeout(this.expiryTimer);
    this.now.set(Date.now());
    const dates = this.rows()
      .filter((row) => row.state === 'ready' && row.remote)
      .map((row) => Date.parse(row.remote!.expires_at));
    if (!dates.length) return;
    const delay = Math.max(0, Math.min(...dates) - Date.now());
    this.expiryTimer = setTimeout(
      () => {
        this.expiryTimer = undefined;
        this.now.set(Date.now());
        this.rows.update((rows) =>
          rows.map((row) =>
            row.state === 'ready' && row.remote && Date.parse(row.remote.expires_at) <= this.now()
              ? { ...row, state: 'failed', detail: 'This file has expired. Upload it again.' }
              : row,
          ),
        );
        this.scheduleExpiry();
      },
      Math.min(delay, 2147483647),
    );
  }
  private schedule() {
    if (
      this.timer ||
      this.polling ||
      !this.rows().some(
        (row) => row.remote && ['storing', 'queued', 'extracting'].includes(row.remote.status),
      )
    )
      return;
    this.timer = setTimeout(() => {
      this.timer = undefined;
      void this.poll();
    }, 1500);
  }
  private async poll() {
    const generation = this.generation;
    this.polling = true;
    try {
      for (const row of this.rows())
        if (
          row.remote &&
          !row.removing &&
          ['storing', 'queued', 'extracting'].includes(row.remote.status)
        ) {
          try {
            const remote = await this.clients
              .get()
              .chat.attachments.get(
                this.facade.tenantId(),
                this.assistant.threadId(),
                row.remote.id,
              );
            if (generation !== this.generation) return;
            this.received(row.key, remote);
          } catch (error) {
            if (generation !== this.generation) return;
            this.update(row.key, {
              state: 'failed',
              detail: 'File status could not be loaded. Retry to check again.',
            });
            this.failure(error);
          }
        }
    } finally {
      if (generation === this.generation) {
        this.polling = false;
        this.schedule();
      }
    }
  }
  async retry(key: string) {
    const row = this.rows().find((row) => row.key === key);
    if (!row || row.removing || this.assistant.running()) return;
    this.error.set('');
    const generation = this.generation;
    if (!row.remote) {
      this.update(key, { state: 'uploading', detail: undefined });
      await this.upload(row, generation);
      return;
    }
    try {
      const current = await this.clients
        .get()
        .chat.attachments.get(this.facade.tenantId(), this.assistant.threadId(), row.remote.id);
      if (generation !== this.generation) return;
      if (['failed', 'cancelled'].includes(current.status)) {
        const remote = await this.clients
          .get()
          .chat.attachments.retry(
            this.facade.tenantId(),
            this.assistant.threadId(),
            current.id,
            { expected_revision: current.revision },
            crypto.randomUUID(),
          );
        if (generation !== this.generation) return;
        this.received(key, remote);
      } else if (['expired', 'deleted'].includes(current.status)) {
        const next = {
          ...row,
          remote: undefined,
          uploadKey: crypto.randomUUID(),
          state: 'uploading' as const,
          detail: undefined,
        };
        this.update(key, next);
        await this.upload(next, generation);
      } else this.received(key, current);
      this.schedule();
    } catch (error) {
      if (generation === this.generation) this.failure(error);
    }
  }
  async remove(key: string) {
    const row = this.rows().find((row) => row.key === key);
    if (!row || row.removing || row.state === 'uploading' || this.assistant.running()) return;
    const generation = this.generation;
    this.update(key, { removing: true });
    try {
      if (row.remote)
        await this.clients
          .get()
          .chat.attachments.remove(
            this.facade.tenantId(),
            this.assistant.threadId(),
            row.remote.id,
            row.remote.revision,
          );
      if (generation !== this.generation) return;
      this.forget(key);
    } catch (error) {
      if (generation === this.generation) {
        this.update(key, { removing: false, detail: 'The file could not be removed. Try again.' });
        if (error instanceof Error && 'status' in error && error.status === 409 && row.remote) {
          try {
            const current = await this.clients
              .get()
              .chat.attachments.get(
                this.facade.tenantId(),
                this.assistant.threadId(),
                row.remote.id,
              );
            if (generation === this.generation) this.received(key, current);
          } catch {
            /* Keep the original removal error visible. */
          }
        }
        this.failure(error);
      }
    }
  }
  private forget(key: string) {
    const row = this.rows().find((row) => row.key === key);
    if (row?.previewUrl) URL.revokeObjectURL(row.previewUrl);
    this.rows.update((rows) => rows.filter((row) => row.key !== key));
  }
  async download(file: AttachmentHistorySummary) {
    if (!file.available || this.downloading().has(file.id)) return;
    const generation = this.generation;
    this.downloading.update((rows) => new Set([...rows, file.id]));
    this.error.set('');
    try {
      const result = await this.clients
        .get()
        .chat.attachments.original(this.facade.tenantId(), this.assistant.threadId(), file.id);
      if (generation !== this.generation) return;
      const url = URL.createObjectURL(result.blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = result.filename || file.filename;
      anchor.click();
      setTimeout(() => URL.revokeObjectURL(url), 0);
    } catch (error) {
      if (generation === this.generation) this.failure(error);
    } finally {
      if (generation === this.generation)
        this.downloading.update((rows) => new Set([...rows].filter((id) => id !== file.id)));
    }
  }
  sent() {
    if (this.expiryTimer) clearTimeout(this.expiryTimer);
    this.expiryTimer = undefined;
    for (const row of this.rows()) if (row.previewUrl) URL.revokeObjectURL(row.previewUrl);
    this.rows.set([]);
    this.error.set('');
  }
  private reset() {
    ++this.generation;
    for (const abort of this.aborts) abort.abort();
    this.aborts.clear();
    if (this.timer) clearTimeout(this.timer);
    this.timer = undefined;
    this.polling = false;
    this.sent();
    this.downloading.set(new Set());
    this.capabilities.set(null);
    this.checking.set(false);
    this.selecting.set(false);
  }
  ngOnDestroy() {
    this.reset();
  }
}
