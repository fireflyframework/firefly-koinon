// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { TestBed } from '@angular/core/testing';
import {
  KoinonClient,
  type HttpMethod,
  type RequestOptions,
  type KoinonTransport,
} from '@fireflyframework/koinon-sdk';
import { KoinonFacade, provideKoinonClient } from '@fireflyframework/koinon-angular/workbench/core';
import { KoinonSourceMappings } from './source-mappings';
import type { MappingPolicy, PolicyReceipt, ReviewPage, SourceMapping } from './mapping-contracts';
const policy: MappingPolicy = {
  connection_id: 'account',
  drive_id: 'drive',
  root_id: 'root',
  destination: { workspace_id: 'space', project_id: 'project', parent_id: 'folder' },
  recursive: true,
  removal_policy: 'pause_for_review',
  schema_version: 1,
  mode: 'document',
  hierarchy: 'preserve',
  excluded_ids: [],
  formats: ['.pdf'],
  schedule: { kind: 'manual' },
};
const receipt: PolicyReceipt = {
  operation_id: 'operation',
  receipt_id: 'receipt',
  action: 'review',
  mapping_id: 'mapping',
  policy_id: 'review',
  expected_policy_revision: null,
  result_policy_revision: 4,
  review_digest: 'digest',
  review_expires_at: '2099-01-01T00:00:00Z',
  disposition: 'reviewed',
};
const review: ReviewPage = {
  review_id: 'review',
  policy_revision: 4,
  review_digest: 'digest',
  expires_at: '2099-01-01T00:00:00Z',
  items: [],
  next_cursor: null,
  enumeration_complete: true,
  total: null,
  observed_count: 0,
  known_bytes: 0,
  unknown_size_count: 0,
  can_apply: true,
  destination: { segments: [{ id: 'folder', kind: 'collection', name: 'Policies' }] },
};
const mapping: SourceMapping = {
  id: 'mapping',
  revision: 4,
  policy_revision: 4,
  latest_review_revision: 4,
  control_revision: 9,
  connection_id: 'account',
  policy,
  status: 'active',
  next_run_at: null,
  can_pause: true,
  can_resume: false,
  can_retire: true,
  can_sync: true,
  presentation: {
    source_root: { name: 'Policies', relative_path: [] },
    destination: { segments: [{ id: 'folder', kind: 'collection', name: 'Research' }] },
    unavailable_reason: null,
  },
};
function setup(
  handler: (method: HttpMethod, path: string, options?: RequestOptions) => Promise<unknown>,
) {
  const transport: KoinonTransport = {
    request: <T>(method: HttpMethod, path: string, options?: RequestOptions) =>
      handler(method, path, options) as Promise<T>,
    stream: () => {
      throw Error('Unexpected stream');
    },
  };
  TestBed.configureTestingModule({
    providers: [
      KoinonFacade,
      KoinonSourceMappings,
      ...provideKoinonClient(new KoinonClient({ transport }), transport),
    ],
  });
  const f = TestBed.inject(KoinonFacade);
  f.tenantId.set('tenant');
  f.context.set({ subject: 'reader', tenants: [], workspaces: [], memberships: [] });
  return { state: TestBed.inject(KoinonSourceMappings), f };
}
describe('source policy review and command authority', () => {
  it('keeps accepted policy visible while a separate exact review expires', async () => {
    const { state } = setup(async (method, path) =>
      method === 'POST' ? receipt : path.endsWith('/items') ? review : mapping,
    );
    await state.open('mapping');
    await state.prepare({ ...policy, hierarchy: 'flatten' });
    expect(state.detail()?.policy.hierarchy).toBe('preserve');
    expect(state.canApprove()).toBe(true);
    state.clock.set(Date.parse('2100-01-01T00:00:00Z'));
    expect(state.canApprove()).toBe(false);
    expect(await state.approve()).toBe(false);
  });
  it('never approves an incomplete manifest even if the response claims it can apply', async () => {
    const { state } = setup(async (_method, path) =>
      path.endsWith('/items') ? { ...review, enumeration_complete: false } : receipt,
    );
    await state.prepare(policy);
    expect(state.canApprove()).toBe(false);
    expect(await state.approve()).toBe(false);
  });
  it('reads a lost preparation continuation before an explicit resume and never approves a partial scan', async () => {
    const writes: string[] = [];
    let revision = 1;
    const validation = () => ({
      validation_id: 'validation',
      revision,
      state: revision === 3 ? 'complete' : 'scanning',
      enumeration_complete: revision === 3,
      manifest_sha256: revision === 3 ? 'manifest' : null,
      continuation_token: revision === 3 ? null : 'token-' + revision,
      expires_at: '2099-01-01T00:00:00Z',
      observed_count: null,
      total: null,
    });
    const { state } = setup(async (method, path) => {
      if (method === 'POST') writes.push(path);
      if (path.endsWith('/continue')) {
        revision++;
        if (revision === 2) throw Error('lost response');
      }
      return validation();
    });
    await state.beginPreparation(policy);
    expect(state.preparation()?.state).toBe('scanning');
    expect(state.canApprove()).toBe(false);
    expect(await state.resumePreparation()).toBe(false);
    expect(state.preparationUncertain()).toBe(true);
    expect(await state.resumePreparation()).toBe(false);
    await state.checkPreparation();
    expect(state.preparation()?.revision).toBe(2);
    expect(writes).toHaveLength(2);
    expect(state.canResumePreparation()).toBe(true);
    await state.resumePreparation();
    expect(state.preparationComplete()).toBe(true);
    expect(state.canApprove()).toBe(false);
    expect(writes).toHaveLength(3);
  });
  it('keeps an uncertain preparation identity when another creation is requested', async () => {
    const writes: string[] = [];
    const { state } = setup(async (method, path) => {
      if (method === 'POST') {
        writes.push(path);
        throw Error('lost creation response');
      }
      return {
        validation_id: 'same-validation',
        revision: 1,
        state: 'scanning',
        continuation_token: 'token',
        enumeration_complete: false,
        expires_at: '2099-01-01T00:00:00Z',
      };
    });
    await state.beginPreparation(policy);
    await state.beginPreparation({ ...policy, root_id: 'different' });
    expect(state.preparationUncertain()).toBe(true);
    expect(writes).toHaveLength(1);
    await state.checkOperation();
    expect(state.preparation()?.validation_id).toBe('same-validation');
    expect(state.preparedPolicy()?.root_id).toBe('root');
  });
  it('abandons preparation without activating its reviewed policy', async () => {
    const writes: string[] = [];
    const { state } = setup(async (method, path) => {
      if (method === 'POST') writes.push(path);
      return {
        validation_id: 'validation',
        revision: path.endsWith('/abandon') ? 2 : 1,
        state: path.endsWith('/abandon') ? 'cleaning' : 'complete',
        enumeration_complete: true,
        manifest_sha256: 'manifest',
        expires_at: '2099-01-01T00:00:00Z',
      };
    });
    await state.beginPreparation(policy);
    expect(state.preparationComplete()).toBe(true);
    await state.abandonPreparation();
    expect(state.preparation()?.state).toBe('cleaning');
    expect(state.preparationComplete()).toBe(false);
    expect(state.canApprove()).toBe(false);
    expect(writes.map((path) => path.split('/').at(-1))).toEqual([
      'mapping-validations',
      'abandon',
    ]);
  });
  it('honors server denial and invalidates a review when the policy changes', async () => {
    const { state } = setup(async (_method, path) =>
      path.endsWith('/items') ? { ...review, can_apply: false } : receipt,
    );
    await state.prepare(policy);
    expect(state.canApprove()).toBe(false);
    expect(state.review()?.total).toBeNull();
    state.invalidateReview();
    expect(state.review()).toBeNull();
    expect(state.reviewReceipt()).toBeNull();
  });
  it('observes the exact control receipt after a lost response without replaying the command', async () => {
    const bodies: Record<string, unknown>[] = [];
    const { state } = setup(async (method, path, options) => {
      if (method === 'GET')
        return path.includes('/operations/')
          ? {
              kind: 'control',
              receipt: {
                action: 'pause',
                operation_id: bodies[0]['operation_id'],
                control_revision: 10,
                disposition: 'paused',
              },
            }
          : mapping;
      bodies.push(options?.body as Record<string, unknown>);
      throw Error('lost response');
    });
    await state.open('mapping');
    expect(await state.command('pause')).toBe(false);
    expect(state.uncertain()).toBe(true);
    expect(await state.command('pause')).toBe(false);
    expect(await state.checkOperation()).toBe(true);
    expect(bodies).toHaveLength(1);
    expect(bodies[0]['expected_revision']).toBe(9);
  });
  it('recovers a lost initial review through a read-only receipt and rejects a mismatched receipt', async () => {
    let operationId = '',
      valid = false;
    const posts: string[] = [],
      reads: string[] = [];
    const { state } = setup(async (method, path, options) => {
      if (method === 'POST') {
        posts.push(path);
        operationId = (options?.body as Record<string, string>)['operation_id'];
        throw Error('lost review response');
      }
      reads.push(path);
      if (path.includes('/operations/'))
        return {
          kind: 'policy',
          receipt: { ...receipt, operation_id: valid ? operationId : 'another-operation' },
        };
      return review;
    });
    expect(await state.prepare(policy)).toBe(false);
    expect(await state.checkOperation()).toBe(false);
    expect(state.uncertain()).toBe(true);
    expect(state.review()).toBeNull();
    valid = true;
    expect(await state.checkOperation()).toBe(true);
    expect(state.canApprove()).toBe(true);
    expect(posts).toHaveLength(1);
    expect(reads[0]).toBe('/tenants/tenant/content-sources/operations/' + operationId);
  });
  it('recovers an existing mapping review through that mapping operation scope', async () => {
    let operationId = '';
    const reads: string[] = [];
    const { state } = setup(async (method, path, options) => {
      if (method === 'POST') {
        operationId = (options?.body as Record<string, string>)['operation_id'];
        throw Error('lost review response');
      }
      reads.push(path);
      if (path.includes('/operations/'))
        return { kind: 'policy', receipt: { ...receipt, operation_id: operationId } };
      return path.endsWith('/items') ? review : mapping;
    });
    await state.open('mapping');
    await state.prepare(policy);
    await state.checkOperation();
    expect(reads).toContain(
      '/tenants/tenant/content-sources/mappings/mapping/operations/' + operationId,
    );
    expect(state.canApprove()).toBe(true);
  });
  it('rejects a pending review response after the screen is closed in the same session', async () => {
    let finish!: (value: unknown) => void;
    const { state } = setup(async (method) =>
      method === 'POST'
        ? new Promise((resolve) => {
            finish = resolve;
          })
        : review,
    );
    const pending = state.prepare(policy);
    state.close();
    await state.load();
    finish(receipt);
    expect(await pending).toBe(false);
    expect(state.reviewReceipt()).toBeNull();
    expect(state.review()).toBeNull();
  });
  it.each(['other-mapping', 'forbidden'])(
    'does not report apply readiness after a %s refresh',
    async (outcome) => {
      let applied = false,
        finish!: (value: unknown) => void,
        reject!: (error: Error) => void;
      const { state } = setup(async (method, path) => {
        if (method === 'POST' && path.endsWith('/mapping-reviews')) return receipt;
        if (method === 'POST') {
          applied = true;
          return { ...receipt, action: 'apply' };
        }
        if (path.endsWith('/items')) return review;
        if (applied && path.endsWith('/mapping'))
          return new Promise((resolve, fail) => {
            finish = resolve;
            reject = fail;
          });
        return { ...mapping, id: 'other' };
      });
      await state.prepare(policy);
      const approval = state.approve();
      await Promise.resolve();
      await Promise.resolve();
      if (outcome === 'other-mapping') {
        state.close();
        await state.open('other');
        finish(mapping);
      } else reject(Object.assign(new Error('forbidden'), { status: 403 }));
      expect(await approval).toBe(false);
      expect(state.notice()).not.toContain('approved');
      expect(state.detail()?.id).toBe(outcome === 'other-mapping' ? 'other' : undefined);
    },
  );
  it('does not revive protected review data or replay approval after session renewal', async () => {
    let resolve!: (value: unknown) => void;
    let posts = 0;
    const { state, f } = setup(async (method, path) => {
      if (method === 'POST') {
        posts++;
        return receipt;
      }
      if (path.endsWith('/items'))
        return new Promise((done) => {
          resolve = done;
        });
      return mapping;
    });
    const pending = state.prepare(policy);
    await Promise.resolve();
    await Promise.resolve();
    f.authRequired.set(true);
    TestBed.tick();
    f.authRequired.set(false);
    TestBed.tick();
    resolve(review);
    await pending;
    expect(state.review()).toBeNull();
    expect(state.canApprove()).toBe(false);
    expect(state.uncertain()).toBe(false);
    expect(posts).toBe(1);
  });
});
