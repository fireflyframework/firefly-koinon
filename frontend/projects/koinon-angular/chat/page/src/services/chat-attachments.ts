// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { Injectable, OnDestroy, computed, effect, inject, signal } from '@angular/core';
import { KoinonError } from '@fireflyframework/koinon-sdk';
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
      (value.storage.available === true || value.storage.configured === true) &&
      value.database.available === true &&
      value.extraction.available !== false
    );
  });
  readonly unavailableReason = computed(() => {
    if (this.checking()) return 'Checking file availability…';
    const value = this.capabilities();
    if (!value) return 'File uploads are not enabled in this workspace.';
    if (
      (value.storage.available !== true && value.storage.configured !== true) ||
      value.database.available !== true
    )
      return 'File uploads are not configured. Ask your administrator to enable private file storage.';
    if (value.extraction.available === false)
      return 'File processing is unavailable. Ask your administrator to check the file worker.';
    return '';
  });
  readonly storageHint = computed(() => {
    const storage = this.capabilities()?.storage;
    if (!this.enabled() || this.checking() || !storage || storage.available === true) return '';
    return storage.available === false
      ? 'Private file storage is configured, but the last availability check failed. You can try uploading again.'
      : 'Private file storage is configured but has not been verified. Your upload will check availability.';
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
      ...(row.remote && ['processing', 'ready'].includes(row.state)
        ? { progress: row.remote.progress.percent }
        : {}),
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
  readonly imagesEnabled = computed(
    () =>
      !!this.assistant.selectedAgent()?.input_modalities?.includes('image') &&
      !!this.capabilities()?.formats.some(
        (format) => format.kind === 'image' && format.extraction.available === true,
      ),
  );
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
    const rejected: { file: File; reason: string }[] = [];
    const reject = (file: File, reason: string) => rejected.push({ file, reason });
    for (const file of files) {
      if (this.rows().length + accepted.length >= limits.max_selected) {
        reject(file, `You can attach up to ${limits.max_selected} files to a message.`);
        continue;
      }
      const format = this.capabilities()!.formats.find(
        (format) =>
          format.extensions.some((extension) =>
            file.name.toLowerCase().endsWith(extension.toLowerCase()),
          ) && format.extraction.available === true,
      );
      if (!format) {
        reject(file, 'This file type is not supported by the configured file processor.');
        continue;
      }
      if (
        format.kind === 'image' &&
        !this.assistant.selectedAgent()?.input_modalities?.includes('image')
      ) {
        reject(file, 'Choose an agent that supports images before attaching an image.');
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
        reject(file, 'This file is empty or exceeds the workspace file size limit.');
        continue;
      }
      accepted.push(file);
    }
    if (rejected.length)
      this.error.set('Some files were not accepted. Review their details before sending.');
    if (!accepted.length) {
      this.rows.update((rows) => [
        ...rows,
        ...rejected.map(({ file, reason }) => ({
          key: crypto.randomUUID(),
          file,
          uploadKey: '',
          state: 'rejected' as const,
          detail: reason,
        })),
      ]);
      return;
    }
    this.selecting.set(true);
    const thread = await this.assistant.ensureThread();
    if (!thread) {
      this.selecting.set(false);
      return;
    }
    this.switchContext();
    this.selecting.set(true);
    const generation = this.generation;
    if (rejected.length)
      this.error.set('Some files were not accepted. Review their details before sending.');
    const queued: DraftFile[] = accepted.map((file) => ({
      key: crypto.randomUUID(),
      file,
      uploadKey: crypto.randomUUID(),
      state: 'selected',
      ...(['image/png', 'image/jpeg', 'image/webp', 'image/gif'].includes(file.type)
        ? { previewUrl: URL.createObjectURL(file) }
        : {}),
    }));
    this.rows.update((rows) => [
      ...rows,
      ...queued,
      ...rejected.map(({ file, reason }) => ({
        key: crypto.randomUUID(),
        file,
        uploadKey: '',
        state: 'rejected' as const,
        detail: reason,
      })),
    ]);
    for (const row of queued) {
      if (generation !== this.generation) break;
      if (!this.rows().some((current) => current.key === row.key)) continue;
      this.update(row.key, { state: 'uploading' });
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
          state:
            error instanceof KoinonError &&
            error.status >= 400 &&
            error.status < 500 &&
            error.status !== 408
              ? 'failed'
              : 'unknown',
          detail:
            error instanceof KoinonError &&
            error.status >= 400 &&
            error.status < 500 &&
            error.status !== 408
              ? 'Upload failed. Retry to resume this file.'
              : 'Upload outcome not confirmed. Retry checks the same upload request.',
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
          : remote.status === 'extracting'
            ? 'processing'
            : ['storing', 'queued'].includes(remote.status)
              ? 'queued'
              : remote.status === 'cancelled'
                ? 'cancelled'
                : ['expired', 'deleted'].includes(remote.status)
                  ? 'expired'
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
              ? { ...row, state: 'expired', detail: 'This file has expired. Upload it again.' }
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
              state: 'unknown',
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
    if (
      !row ||
      this.selecting() ||
      row.removing ||
      !['failed', 'unknown', 'cancelled', 'expired'].includes(row.state) ||
      this.assistant.running()
    )
      return;
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
