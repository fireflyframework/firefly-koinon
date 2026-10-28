// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { Injectable, EventEmitter, OnDestroy, signal } from '@angular/core';
import type { Citation, EvidenceResult, Presentation } from '@fireflyframework/koinon-sdk';
export type EvidenceResolver = (
  runId: string,
  resultId: string,
  signal?: AbortSignal,
) => Promise<EvidenceResult>;
@Injectable()
export class KoinonEvidenceContext implements OnDestroy {
  readonly presentation = signal<Presentation | undefined>(undefined);
  readonly mode = signal<'answer' | 'audit'>('answer');
  private runId = '';
  private contextKey = '';
  private resolver?: EvidenceResolver;
  private revision = 0;
  private readonly requests = new Map<
    string,
    { abort: AbortController; promise: Promise<EvidenceResult> }
  >();
  readonly citationRequested = new EventEmitter<Citation>();
  readonly resourceRequested = new EventEmitter<string>();
  bind(
    runId: string,
    resolver: EvidenceResolver,
    contextKey: string,
    presentation?: Presentation,
    mode: 'answer' | 'audit' = 'answer',
  ) {
    this.presentation.set(presentation);
    this.mode.set(mode);
    if (runId === this.runId && resolver === this.resolver && contextKey === this.contextKey)
      return;
    this.clear();
    this.runId = runId;
    this.resolver = resolver;
    this.contextKey = contextKey;
  }
  read(resultId: string): Promise<EvidenceResult> {
    const cached = this.requests.get(resultId);
    if (cached) return cached.promise;
    const revision = this.revision,
      runId = this.runId,
      resolver = this.resolver,
      abort = new AbortController();
    const promise = (async () => {
      if (!runId || !resolver)
        throw new Error('This answer has no authorized evidence connection.');
      const result = await resolver(runId, resultId, abort.signal);
      if (revision !== this.revision || abort.signal.aborted)
        throw new DOMException('Evidence context changed', 'AbortError');
      if (result.run_id !== runId || result.id !== resultId)
        throw new Error('This evidence belongs to a different answer.');
      if (!['search', 'query', 'schema', 'lineage', 'attachment', 'proposal'].includes(result.kind))
        throw new Error('This evidence type is not supported.');
      return result;
    })();
    this.requests.set(resultId, { abort, promise });
    return promise;
  }
  private clear() {
    ++this.revision;
    for (const request of this.requests.values()) request.abort.abort();
    this.requests.clear();
  }
  ngOnDestroy() {
    this.clear();
  }
}
