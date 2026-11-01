// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { signal } from '@angular/core';
import { KoinonError } from '@fireflyframework/koinon-sdk';
import { createAvailabilityApi } from '@fireflyframework/koinon-sdk/availability';
import type {
  AssetAvailability,
  FileBatchCapabilities,
  FileBatchCreate,
  FileBatchItemView,
  FileBatchView,
  KoinonClient,
  KoinonTransport,
} from '@fireflyframework/koinon-sdk';

export interface UploadScope {
  owner: object | null;
  clientRevision: number;
  tenantId: string;
  workspaceId: string;
  projectId: string;
  parentId: string;
  transport: KoinonTransport | null;
  navigationId?: string;
  allowed?: boolean;
}
export interface UploadView {
  stage:
    | 'idle'
    | 'checking'
    | 'hashing'
    | 'creating'
    | 'staging'
    | 'submitting'
    | 'observed'
    | 'unknown';
  busy: boolean;
  transferring: boolean;
  message: string;
  currentFile: string;
  received: number;
  uncertain: boolean;
  capabilities: FileBatchCapabilities | null;
  batch: FileBatchView | null;
  items: FileBatchItemView[];
  availability: Record<string, AssetAvailability>;
  availabilityObservedAt: string | null;
}
interface UploadPorts {
  scope(): UploadScope;
  client(): KoinonClient;
  synchronous(
    file: File,
    mode: 'document' | 'dataset',
    scope: UploadScope,
    signal: AbortSignal,
  ): Promise<boolean>;
  hash(file: File, signal: AbortSignal): Promise<string>;
  changed(): Promise<void>;
  authorityLost?(status: number): void;
}
interface Session {
  scope: UploadScope;
  api: KoinonClient['fileBatches'];
  observations: ReturnType<typeof createAvailabilityApi>;
  controller: AbortController;
  files: File[];
  mode: 'document' | 'dataset';
  manifest: FileBatchCreate;
  createKey: string;
  submitKey: string;
  cancelKey: string;
  uploadKeys: Map<string, string>;
  recoveryKeys: Map<string, string>;
  attemptedUploads: Set<string>;
  pendingWrite: boolean;
  createAttempted: boolean;
  submitAttempted: boolean;
  cancelAttempted: boolean;
  synchronousAttempted: boolean;
  batchId: string | null;
}
const empty = (): UploadView => ({
  stage: 'idle',
  busy: false,
  transferring: false,
  message: '',
  currentFile: '',
  received: 0,
  uncertain: false,
  capabilities: null,
  batch: null,
  items: [],
  availability: {},
  availabilityObservedAt: null,
});
const active = new Set(['queued', 'running']);
const terminal = new Set(['succeeded', 'partial', 'failed', 'cancelled', 'expired', 'reconciling']);
const sameScope = (a: UploadScope, b: UploadScope) =>
  a.owner === b.owner &&
  a.clientRevision === b.clientRevision &&
  a.transport === b.transport &&
  a.tenantId === b.tenantId &&
  a.workspaceId === b.workspaceId &&
  a.projectId === b.projectId &&
  a.parentId === b.parentId &&
  a.navigationId === b.navigationId &&
  a.allowed === b.allowed;

/** Mutation keys live with one verified client/scope; ambiguous writes are never replayed. */
export class LibraryUploadCoordinator {
  private session: Session | null = null;
  private readonly state = signal<UploadView>(empty());
  constructor(private readonly ports: UploadPorts) {}
  readonly view = () =>
    this.session && !sameScope(this.session.scope, this.ports.scope()) ? empty() : this.state();
  private current(session: Session) {
    return (
      this.session === session &&
      !session.controller.signal.aborted &&
      sameScope(session.scope, this.ports.scope())
    );
  }
  private check(session: Session) {
    if (!this.current(session)) throw new DOMException('Scope changed', 'AbortError');
  }
  private set(session: Session, value: Partial<UploadView>) {
    this.check(session);
    this.state.update((old) => ({ ...old, ...value }));
  }
  invalidate() {
    this.session?.controller.abort();
    this.session = null;
    this.state.set(empty());
  }
  dispose() {
    this.invalidate();
  }
  syncScope() {
    if (this.session && !this.current(this.session)) {
      this.invalidate();
      return false;
    }
    return true;
  }
  reset() {
    const view = this.view();
    if (
      view.busy ||
      view.uncertain ||
      view.batch?.status === 'reconciling' ||
      (view.batch && !terminal.has(view.batch.status))
    )
      return false;
    this.invalidate();
    return true;
  }
  canContinue() {
    const view = this.view();
    return (
      !!this.session &&
      !this.session.submitAttempted &&
      view.batch?.status === 'staging' &&
      !view.busy &&
      !view.uncertain &&
      view.items.length > 0
    );
  }

  private options(session: Session) {
    return { signal: AbortSignal.any([session.controller.signal, AbortSignal.timeout(150000)]) };
  }
  private async run(session: Session, work: () => Promise<void>, transferring = false) {
    if (this.state().busy) return;
    this.set(session, { busy: true, transferring, message: '' });
    try {
      await work();
    } catch (error) {
      if (
        this.current(session) &&
        error instanceof KoinonError &&
        [401, 403].includes(error.status)
      ) {
        this.invalidate();
        this.state.set({
          ...empty(),
          message:
            'Current upload access could not be verified. Refresh your account access before continuing.',
        });
        this.ports.authorityLost?.(error.status);
        return;
      }
      if (this.current(session)) {
        if (session.pendingWrite || this.state().uncertain) {
          this.set(session, {
            stage: 'unknown',
            uncertain: true,
            message:
              'The upload outcome is not confirmed. Check status before taking another action. Files were not sent again.',
          });
        } else if (session.batchId) {
          this.set(session, {
            stage: 'observed',
            message: 'Status could not be refreshed. Last observations are retained.',
          });
        } else {
          this.set(session, {
            stage: 'idle',
            message: 'Upload readiness could not be verified. No files were sent.',
          });
        }
      }
    } finally {
      if (this.current(session))
        this.set(session, { busy: false, transferring: false, currentFile: '' });
    }
  }
  async start(files: File[], mode: 'document' | 'dataset') {
    if (this.view().busy) return;
    if (
      this.session &&
      sameScope(this.session.scope, this.ports.scope()) &&
      (this.session.createAttempted || this.session.synchronousAttempted)
    ) {
      await this.refresh();
      return;
    }
    this.invalidate();
    const scope = { ...this.ports.scope() };
    if (
      scope.allowed === false ||
      !scope.owner ||
      !scope.transport ||
      !scope.tenantId ||
      !scope.workspaceId ||
      !scope.projectId ||
      !scope.parentId ||
      !files.length
    ) {
      this.state.set({
        ...empty(),
        message: 'Choose files and a connected destination folder before uploading.',
      });
      return;
    }
    const session: Session = {
      scope,
      api: this.ports.client().fileBatches,
      observations: createAvailabilityApi(scope.transport),
      controller: new AbortController(),
      files: [...files],
      mode,
      manifest: {
        processing_policy: 'extract_only_v1',
        destination: {
          workspace_id: scope.workspaceId,
          project_id: scope.projectId,
          parent_id: scope.parentId,
        },
        items: [],
      },
      createKey: crypto.randomUUID(),
      submitKey: crypto.randomUUID(),
      cancelKey: crypto.randomUUID(),
      uploadKeys: new Map(),
      recoveryKeys: new Map(),
      attemptedUploads: new Set(),
      pendingWrite: false,
      createAttempted: false,
      submitAttempted: false,
      cancelAttempted: false,
      synchronousAttempted: false,
      batchId: null,
    };
    this.session = session;
    await this.run(
      session,
      async () => {
        this.set(session, { stage: 'checking' });
        const caps = await session.api.capabilities(
          scope.tenantId,
          scope.workspaceId,
          this.options(session),
        );
        this.check(session);
        this.set(session, { capabilities: caps });
        if (
          !caps.modes.includes(mode) ||
          !Number.isSafeInteger(caps.max_files) ||
          files.length > Math.min(caps.max_files, 100) ||
          !Number.isSafeInteger(caps.max_file_bytes) ||
          !Number.isSafeInteger(caps.max_batch_bytes) ||
          files.some(
            (file) => file.size < 1 || file.size > Math.min(caps.max_file_bytes, 134217728),
          ) ||
          files.reduce((size, file) => size + file.size, 0) >
            Math.min(caps.max_batch_bytes, 536870912)
        ) {
          this.set(session, {
            stage: 'idle',
            message:
              'These files exceed the observed upload limits or use an unavailable processing mode.',
          });
          return;
        }
        if (!caps.configured) {
          const bound = caps.synchronous_max_file_bytes;
          if (
            !bound ||
            !Number.isSafeInteger(bound) ||
            files.some((file) => file.size > Math.min(bound, 33554432))
          ) {
            this.set(session, {
              stage: 'idle',
              message:
                'Large files need configured queued storage. They were not sent to synchronous processing.',
            });
            return;
          }
          for (const file of files) {
            this.set(session, { stage: 'staging', currentFile: file.name });
            session.synchronousAttempted = true;
            session.pendingWrite = true;
            if (!(await this.ports.synchronous(file, mode, scope, session.controller.signal)))
              throw new Error('Unconfirmed synchronous result');
            this.check(session);
            session.pendingWrite = false;
            this.set(session, { received: this.state().received + 1 });
          }
          this.set(session, {
            stage: 'observed',
            message: 'Files received. Check their observed availability in the Library.',
          });
          return;
        }
        for (const file of files) {
          this.set(session, { stage: 'hashing', currentFile: file.name });
          const sha256 = await this.ports.hash(file, session.controller.signal);
          this.check(session);
          if (!/^[a-f0-9]{64}$/.test(sha256)) throw new Error('Invalid original digest');
          session.manifest.items.push({
            client_item_id: crypto.randomUUID(),
            filename: file.name,
            mode,
            size_bytes: file.size,
            sha256,
          });
        }
        this.set(session, { stage: 'creating' });
        session.createAttempted = true;
        session.pendingWrite = true;
        const batch = await session.api.create(
          scope.tenantId,
          session.manifest,
          session.createKey,
          this.options(session),
        );
        this.acceptBatch(session, batch);
        await this.observe(session);
        await this.stage(session);
        await this.submit(session);
      },
      true,
    );
  }
  private acceptBatch(session: Session, batch: FileBatchView) {
    this.check(session);
    if (
      !batch.id ||
      batch.id.length > 64 ||
      (session.batchId && batch.id !== session.batchId) ||
      batch.tenant_id !== session.scope.tenantId ||
      batch.destination.workspace_id !== session.scope.workspaceId ||
      batch.destination.project_id !== session.scope.projectId ||
      batch.destination.parent_id !== session.scope.parentId ||
      batch.total_items !== session.files.length ||
      !Number.isSafeInteger(batch.revision) ||
      batch.revision < 1
    )
      throw new Error('Batch acknowledgement scope changed');
    session.batchId = batch.id;
    session.pendingWrite = false;
    this.set(session, { batch });
  }
  private async observe(session: Session) {
    this.check(session);
    if (!session.batchId) return;
    const batch = await session.api.get(
      session.scope.tenantId,
      session.batchId,
      this.options(session),
    );
    this.check(session);
    if (
      batch.tenant_id !== session.scope.tenantId ||
      batch.id !== session.batchId ||
      batch.total_items !== session.files.length ||
      batch.destination.workspace_id !== session.scope.workspaceId ||
      batch.destination.project_id !== session.scope.projectId ||
      batch.destination.parent_id !== session.scope.parentId
    )
      throw new Error('Batch scope changed');
    const items: FileBatchItemView[] = [];
    for (let page = 1; page <= 2; page++) {
      const result = await session.api.items(
        session.scope.tenantId,
        session.batchId,
        { page, page_size: 50 },
        this.options(session),
      );
      this.check(session);
      if (result.pages > 2 || result.total !== session.files.length)
        throw new Error('Unexpected item bounds');
      items.push(...result.items);
      if (page >= result.pages) break;
    }
    if (
      items.length !== session.manifest.items.length ||
      new Set(items.map((item) => item.id)).size !== items.length ||
      items.some((item) => {
        const manifest = session.manifest.items.find(
          (record) => record.client_item_id === item.client_item_id,
        );
        return (
          !manifest ||
          item.sha256 !== manifest.sha256 ||
          item.size_bytes !== manifest.size_bytes ||
          item.filename !== manifest.filename ||
          item.mode !== manifest.mode
        );
      })
    )
      throw new Error('Original identities disagree');
    let availability: Record<string, AssetAvailability> = {};
    let availabilityObservedAt: string | null = null;
    try {
      const observed = await session.observations.observe(
        session.scope.tenantId,
        { asset_ids: items.map((item) => item.asset_id), workspace_id: session.scope.workspaceId },
        this.options(session),
      );
      this.check(session);
      availabilityObservedAt = observed.observed_at;
      availability = Object.fromEntries(
        items.flatMap((item) =>
          observed.items[item.asset_id] ? [[item.asset_id, observed.items[item.asset_id]!]] : [],
        ),
      );
    } catch (error) {
      if (error instanceof KoinonError && [401, 403].includes(error.status)) throw error;
      this.check(session);
    }
    const accepted = active.has(batch.status) || terminal.has(batch.status);
    const unresolved =
      (session.submitAttempted && !accepted) ||
      (session.cancelAttempted && !batch.cancellation_requested && batch.status !== 'cancelled') ||
      items.some(
        (item) => session.attemptedUploads.has(item.id) && item.status === 'awaiting_upload',
      );
    if (!unresolved) session.pendingWrite = false;
    this.set(session, {
      stage: 'observed',
      batch,
      items,
      availability,
      availabilityObservedAt,
      received: items.filter((item) => !['awaiting_upload', 'cancelled'].includes(item.status))
        .length,
      uncertain: unresolved,
      message: accepted
        ? 'Processing status comes from the worker. Completed extraction does not establish search readiness.'
        : unresolved
          ? 'A previous request is not confirmed. Check status or reconcile the retained original; do not send it again.'
          : 'Files are processed only after their originals are staged and the batch is submitted.',
    });
  }
  private async stage(session: Session) {
    if (!session.batchId || this.state().uncertain || this.state().batch?.status !== 'staging')
      return;
    for (const item of this.state().items) {
      if (item.status !== 'awaiting_upload') continue;
      if (session.attemptedUploads.has(item.id))
        throw new Error('Original requires reconciliation');
      const index = session.manifest.items.findIndex(
        (record) => record.client_item_id === item.client_item_id,
      );
      const file = session.files[index];
      if (!file) throw new Error('Original unavailable');
      this.set(session, { stage: 'staging', currentFile: file.name });
      const key = crypto.randomUUID();
      session.uploadKeys.set(item.id, key);
      session.attemptedUploads.add(item.id);
      session.pendingWrite = true;
      const receipt = await session.api.upload(
        session.scope.tenantId,
        session.batchId,
        item.id,
        file,
        key,
        this.options(session),
      );
      this.check(session);
      if (
        receipt.batch_id !== session.batchId ||
        receipt.item_id !== item.id ||
        receipt.status !== 'staged' ||
        receipt.sha256 !== item.sha256 ||
        receipt.size_bytes !== item.size_bytes
      )
        throw new Error('Original receipt disagrees');
      session.pendingWrite = false;
      this.set(session, { received: this.state().received + 1 });
    }
    await this.observe(session);
  }
  private async submit(session: Session) {
    if (
      !session.batchId ||
      this.state().batch?.status !== 'staging' ||
      session.submitAttempted ||
      this.state().uncertain ||
      !this.state().items.length ||
      this.state().items.some((item) => item.status !== 'staged')
    )
      return;
    const fresh = await session.api.get(
      session.scope.tenantId,
      session.batchId,
      this.options(session),
    );
    this.check(session);
    if (fresh.status !== 'staging' || fresh.cancellation_requested) {
      await this.observe(session);
      return;
    }
    this.set(session, { stage: 'submitting' });
    session.submitAttempted = true;
    session.pendingWrite = true;
    const batch = await session.api.submit(
      session.scope.tenantId,
      session.batchId,
      { expected_revision: fresh.revision },
      session.submitKey,
      this.options(session),
    );
    this.acceptBatch(session, batch);
    await this.observe(session);
    this.check(session);
    await this.ports.changed();
  }
  async refresh() {
    const session = this.session;
    if (!session || !this.current(session)) {
      this.invalidate();
      return;
    }
    await this.run(session, async () => {
      if (session.synchronousAttempted && !session.batchId) {
        await this.ports.changed();
        this.check(session);
        this.set(session, {
          stage: 'unknown',
          uncertain: true,
          message:
            'The synchronous upload did not confirm every result. Inspect the current folder before recovery. No files were sent again.',
        });
        return;
      }
      if (!session.batchId && session.createAttempted) {
        const page = await session.api.list(
          session.scope.tenantId,
          { page: 1, page_size: 10 },
          this.options(session),
        );
        this.check(session);
        for (const candidate of page.items) {
          if (
            candidate.destination.parent_id !== session.scope.parentId ||
            candidate.destination.workspace_id !== session.scope.workspaceId ||
            candidate.destination.project_id !== session.scope.projectId ||
            candidate.total_items !== session.files.length
          )
            continue;
          const records = await session.api.items(
            session.scope.tenantId,
            candidate.id,
            { page: 1, page_size: 50 },
            this.options(session),
          );
          this.check(session);
          if (
            records.items.some((item) =>
              session.manifest.items.some(
                (record) => record.client_item_id === item.client_item_id,
              ),
            )
          ) {
            session.batchId = candidate.id;
            break;
          }
        }
      }
      if (session.batchId) await this.observe(session);
      else
        this.set(session, {
          stage: 'unknown',
          uncertain: true,
          message:
            'No accepted batch could be confirmed. The original request was not repeated. Keep this page open and ask an administrator to inspect retained uploads.',
        });
    });
  }
  async continue() {
    const session = this.session;
    if (!session || !this.current(session)) return;
    await this.run(
      session,
      async () => {
        await this.observe(session);
        await this.stage(session);
        await this.submit(session);
      },
      true,
    );
  }
  canRecover(item: FileBatchItemView) {
    return (
      !!this.session &&
      this.current(this.session) &&
      !this.view().busy &&
      item.status === 'awaiting_upload' &&
      this.session.attemptedUploads.has(item.id) &&
      !this.session.recoveryKeys.has(item.id)
    );
  }
  async recoverOriginal(itemId: string) {
    const session = this.session;
    const item = this.view().items.find((row) => row.id === itemId);
    if (!session?.batchId || !item || !this.canRecover(item)) return;
    await this.run(session, async () => {
      const fresh = await session.api.get(
        session.scope.tenantId,
        session.batchId!,
        this.options(session),
      );
      this.check(session);
      if (fresh.status !== 'staging' || fresh.cancellation_requested) {
        await this.observe(session);
        return;
      }
      const key = crypto.randomUUID();
      session.recoveryKeys.set(itemId, key);
      session.pendingWrite = true;
      const result = await session.api.recoverOriginal(
        session.scope.tenantId,
        session.batchId!,
        itemId,
        { expected_revision: fresh.revision },
        key,
        this.options(session),
      );
      this.acceptBatch(session, result);
      await this.observe(session);
    });
  }
  async cancel() {
    const session = this.session;
    if (!session?.batchId || !this.current(session)) return;
    if (session.cancelAttempted) {
      await this.refresh();
      return;
    }
    await this.run(session, async () => {
      const fresh = await session.api.get(
        session.scope.tenantId,
        session.batchId!,
        this.options(session),
      );
      this.check(session);
      if (terminal.has(fresh.status) || fresh.cancellation_requested) {
        await this.observe(session);
        return;
      }
      session.cancelAttempted = true;
      session.pendingWrite = true;
      const result = await session.api.cancel(
        session.scope.tenantId,
        session.batchId!,
        { expected_revision: fresh.revision },
        session.cancelKey,
        this.options(session),
      );
      this.acceptBatch(session, result);
      await this.observe(session);
    });
  }
}
