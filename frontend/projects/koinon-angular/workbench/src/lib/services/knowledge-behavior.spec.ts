// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { TestBed, DeferBlockState } from '@angular/core/testing';
import {
  KoinonClient,
  KoinonError,
  type KoinonTransport,
  type RequestOptions,
} from '@fireflyframework/koinon-sdk';
import { KoinonFacade, KoinonI18n, provideKoinonClient } from '@fireflyframework/koinon-angular';
import { KoinonSettingsPage } from '../../../../settings/src/settings-page';
const documents = {
  answer_mode: 'rag',
  retrieval_top_k: 17,
  retrieval_per_query_k: 35,
  retrieval_rrf_k: 61,
  query_expansion_enabled: false,
  query_expansion_n: 3,
  answer_top_k: 10,
  rlm_max_iters: 8,
  rlm_sub_budget: 12,
  rlm_max_depth: 1,
  rlm_self_consistency: 1,
  rlm_extended_reasoning: false,
};
const structured = {
  top_k_schema: 12,
  top_k_examples: 4,
  top_k_metrics: 3,
  rrf_k: 60,
  generation_candidates: 1,
  max_refine_retries: 2,
  grounding_min_confidence: 0.6,
};
const bounds = (values: Record<string, [number, number]>) =>
  Object.fromEntries(
    Object.entries(values).map(([key, [minimum, maximum]]) => [key, { minimum, maximum }]),
  );
const settings = (tenant = 'tenant') => ({
  tenant_id: tenant,
  schema_version: 1,
  revision: 7,
  origin: 'organization',
  documents: { ...documents },
  structured: { ...structured },
  capabilities: {
    documents: {
      answer_modes: ['rag', 'rlm'],
      rlm_curated_knowledge_supported: false,
      rlm_curated_knowledge_reason: 'KNOWLEDGE_RLM_UNQUALIFIED',
      rlm_model_role: 'documents.rlm',
      rlm_recorded_views_required: true,
      rlm_recorded_views_reason: 'RLM_DOCUMENT_VIEWS_REQUIRED',
      bounds: bounds({
        retrieval_top_k: [1, 200],
        retrieval_per_query_k: [1, 500],
        retrieval_rrf_k: [1, 1000],
        query_expansion_n: [1, 10],
        answer_top_k: [1, 40],
        rlm_max_iters: [1, 64],
        rlm_sub_budget: [0, 128],
        rlm_max_depth: [0, 8],
        rlm_self_consistency: [1, 8],
      }),
    },
    structured: {
      bounds: bounds({
        top_k_schema: [1, 100],
        top_k_examples: [0, 50],
        top_k_metrics: [0, 50],
        rrf_k: [1, 1000],
        generation_candidates: [1, 8],
        max_refine_retries: [0, 8],
        grounding_min_confidence: [0, 1],
      }),
    },
  },
});
function savedSettings(body: unknown, tenant = 'tenant', revision = 8) {
  const fields = body as { documents: typeof documents; structured: typeof structured };
  return {
    ...settings(tenant),
    documents: fields.documents,
    structured: fields.structured,
    revision,
  };
}
async function mount(
  options: {
    write?: boolean;
    providers?: boolean;
    spanish?: boolean;
    failure?: number;
    readFailure?: boolean;
    request?: KoinonTransport['request'];
  } = {},
) {
  const calls: { method: string; path: string; body: unknown }[] = [];
  const transport: KoinonTransport = {
    request: async <T>(method: unknown, path: string, request?: RequestOptions) => {
      calls.push({ method: String(method), path, body: request?.body });
      if (options.request && path.endsWith('/knowledge/settings'))
        return options.request<T>(method as 'GET', path, request);
      if (path.endsWith('/knowledge/settings')) {
        if (options.readFailure || (method === 'PUT' && options.failure))
          throw new KoinonError(
            options.failure ?? 503,
            'OBSERVED_FAILURE',
            'Observed settings failure',
          );
        return (method === 'PUT' ? savedSettings(request?.body) : settings()) as T;
      }
      return (
        path.endsWith('/configuration')
          ? { providers: [], provider_types: [], connections: [], checks: [] }
          : path.endsWith('/knowledge-roles')
            ? {
                roles: [
                  {
                    id: 'documents.rlm',
                    domain: 'documents',
                    label: 'Document evidence tools',
                    purposes: ['rlm'],
                    status: 'disabled',
                    assignment: 'tenant',
                    runtime_qualification: 'not_run',
                  },
                ],
                providers: [],
                model_options_schema: {},
              }
            : { items: [] }
      ) as T;
    },
    stream: () => {
      throw new Error('Unexpected stream');
    },
  };
  TestBed.configureTestingModule({
    imports: [KoinonSettingsPage],
    providers: [KoinonFacade, ...provideKoinonClient(new KoinonClient({ transport }), transport)],
  });
  const facade = TestBed.inject(KoinonFacade);
  const permissions = [
    'catalog:read',
    ...(options.providers === false ? [] : ['providers:write']),
    ...(options.write === false ? [] : ['settings:write']),
  ];
  facade.tenantId.set('tenant');
  facade.context.set({
    subject: 'administrator',
    tenants: ['tenant', 'other'].map((id) => ({
      id,
      name: id === 'tenant' ? 'Research organization' : 'Other organization',
      roles: [],
      permissions,
    })),
    memberships: [],
    workspaces: [],
  });
  if (options.spanish)
    TestBed.inject(KoinonI18n).apply({
      locale: 'es-ES',
      time_zone: 'UTC',
      response_language: 'es',
    });
  const fixture = TestBed.createComponent(KoinonSettingsPage);
  fixture.componentRef.setInput('actions', { section: () => 'models', chat: () => undefined });
  fixture.detectChanges();
  for (const block of await fixture.getDeferBlocks()) await block.render(DeferBlockState.Complete);
  const settle = async () => {
    await fixture.whenStable();
    fixture.detectChanges();
  };
  const field = (name: string) =>
    fixture.nativeElement.querySelector(`[name="${name}"]`) as HTMLInputElement;
  const change = async (name: string, value: string) => {
    const input = field(name);
    expect(input).not.toBeNull();
    input.value = value;
    input.dispatchEvent(new Event('input'));
    input.dispatchEvent(new Event('change'));
    fixture.detectChanges();
    await settle();
  };
  const rlm = () =>
    ([...fixture.nativeElement.querySelectorAll('input[type=radio]')] as HTMLInputElement[]).find(
      (input) => input.closest('label')?.textContent?.includes('(RLM)'),
    )!;
  const selectRlm = async () => {
    const radio = rlm();
    expect(radio).not.toBeNull();
    radio.click();
    fixture.detectChanges();
    await settle();
  };
  const save = async () => {
    (
      fixture.nativeElement.querySelector(
        'ffk-knowledge-behavior button[type=submit]',
      ) as HTMLButtonElement
    ).click();
    await settle();
  };
  return { fixture, facade, calls, settle, field, change, selectRlm, rlm, save };
}
it('offers organization behavior separately from workspace assignments and preserves the actual inherited baseline', async () => {
  const { fixture, settle, field } = await mount({
    request: async <T>() => ({ ...settings(), revision: 0, origin: 'deployment' }) as T,
  });
  await settle();
  const panel = fixture.nativeElement.querySelector('ffk-knowledge-behavior');
  expect(panel).not.toBeNull();
  expect(panel.textContent).toContain('Research organization');
  expect(panel.querySelector('.origin').textContent).toContain('Using deployment settings');
  expect(panel.querySelector('.origin').textContent).toContain('Revision 0');
  expect(field('documents.retrieval_top_k').value).toBe('17');
  expect(
    fixture.nativeElement.querySelector(
      'ffk-knowledge-models select[aria-label="Assignment scope"]',
    ),
  ).not.toBeNull();
  expect(panel.querySelector('button[type=submit]').disabled).toBe(true);
});
it('saves full document and SQL settings using the loaded revision, and cancel restores saved values without a write', async () => {
  const h = await mount();
  await h.settle();
  expect(
    h.fixture.nativeElement.querySelector('ffk-knowledge-behavior .origin').textContent,
  ).toContain('Saved for this organization');
  await h.selectRlm();
  await h.change('structured.grounding_min_confidence', '0.75');
  await h.change('documents.rlm_sub_budget', '0');
  await h.save();
  expect(h.calls.find((c) => c.method === 'PUT')?.body).toEqual({
    expected_revision: 7,
    documents: { ...documents, answer_mode: 'rlm', rlm_sub_budget: 0 },
    structured: { ...structured, grounding_min_confidence: 0.75 },
  });
  await h.change('documents.retrieval_top_k', '22');
  const buttons = [
    ...h.fixture.nativeElement.querySelectorAll('ffk-knowledge-behavior button'),
  ] as HTMLButtonElement[];
  buttons.find((b) => b.textContent?.trim() === 'Cancel')!.click();
  await h.settle();
  expect(h.field('documents.retrieval_top_k').value).toBe('17');
  expect(h.calls.filter((c) => c.method === 'PUT')).toHaveLength(1);
});
it('uses server bounds and blocks blank, fractional, nonfinite or out-of-range values before a write', async () => {
  const h = await mount();
  await h.settle();
  expect(h.field('documents.rlm_max_iters').max).toBe('64');
  for (const value of ['', '1.5', '65', 'Infinity']) {
    await h.change('documents.rlm_max_iters', value);
    await h.save();
    expect(h.calls.some((c) => c.method === 'PUT')).toBe(false);
  }
});
it('shows RLM curated restrictions and disabled model assignment without claiming verified readiness', async () => {
  const h = await mount();
  await h.settle();
  await h.selectRlm();
  const panel = h.fixture.nativeElement.querySelector('ffk-knowledge-behavior');
  expect(panel.textContent).toContain('Curated knowledge');
  expect(panel.textContent).toContain('Disabled');
  expect(panel.textContent).not.toContain('Verified');
  expect(panel.querySelector('input[value="structured.rlm"]')).toBeNull();
});
it('allows a tenant settings administrator into behavior without exposing model assignment editors', async () => {
  const h = await mount({ providers: false });
  await h.settle();
  expect(h.fixture.nativeElement.querySelector('ffk-knowledge-behavior')).not.toBeNull();
  expect(h.fixture.nativeElement.querySelector('ffk-knowledge-models')).toBeNull();
});
it('keeps provider operators read-only and ignores workspace-only settings authority', async () => {
  const h = await mount({ write: false });
  await h.settle();
  h.facade.workspaceId.set('space');
  h.facade.context.update(
    (c) =>
      c && {
        ...c,
        workspaces: [
          {
            id: 'space',
            tenant_id: 'tenant',
            kind: 'workspace',
            name: 'Space',
            status: 'ready',
            workspace_id: 'space',
            project_id: null,
            parent_id: null,
            description: '',
            metadata: {},
            created_at: '',
          },
        ],
        workspace_permissions: { space: ['settings:write'] },
      },
  );
  await h.settle();
  expect(h.rlm().matches(':disabled')).toBe(true);
  expect(h.calls.some((c) => c.method === 'PUT')).toBe(false);
});
it('preserves draft on conflict and requires an explicit reload before another save', async () => {
  const h = await mount({ failure: 409 });
  await h.settle();
  await h.selectRlm();
  await h.save();
  expect(h.rlm().checked).toBe(true);
  expect(
    h.fixture.nativeElement.querySelector('ffk-knowledge-behavior button[type=submit]').disabled,
  ).toBe(true);
  expect(
    h.fixture.nativeElement.querySelector('ffk-knowledge-behavior [role=alert]').textContent,
  ).toContain('Reload');
});
for (const status of [401, 403])
  it(`retains the draft after server save ${status} and preserves authentication semantics`, async () => {
    const h = await mount({ failure: status });
    await h.settle();
    await h.selectRlm();
    await h.save();
    expect(h.facade.authRequired()).toBe(status === 401);
    expect(h.rlm().checked).toBe(true);
    expect(h.fixture.nativeElement.querySelector('[role=alert]').textContent).toContain(
      'Observed settings failure',
    );
  });
it('does not expose invented defaults after a failed read', async () => {
  const h = await mount({ readFailure: true });
  await h.settle();
  expect(
    h.fixture.nativeElement.querySelector('ffk-knowledge-behavior input[value=rag]'),
  ).toBeNull();
  expect(
    h.fixture.nativeElement.querySelector('ffk-knowledge-behavior [role=alert]'),
  ).not.toBeNull();
});
it('localizes behavior within lazy Settings and keeps separate SQL semantics', async () => {
  const h = await mount({ spanish: true });
  await h.settle();
  const panel = h.fixture.nativeElement.querySelector('ffk-knowledge-behavior');
  expect(panel.textContent).toContain('Comportamiento del conocimiento');
  expect(panel.textContent).toContain('Consultas de datos');
  expect(panel.querySelector('label[for="documents.rlm_max_iters"]').textContent).toContain(
    'Pasos de análisis',
  );
  await h.selectRlm();
  expect(panel.textContent).toContain(
    'RLM necesita versiones de documento con el procesamiento registrado.',
  );
});
it('ignores an older organization response and saves only the new organizations revision', async () => {
  let release!: () => void;
  const h = await mount({
    request: async <T>(method: unknown, path: string, options?: RequestOptions) => {
      if (path.includes('/tenant/'))
        return await new Promise<T>((resolve) => {
          release = () => resolve(settings() as T);
        });
      return (
        method === 'PUT'
          ? savedSettings(options?.body, 'other', 12)
          : { ...settings('other'), revision: 11 }
      ) as T;
    },
  });
  h.facade.tenantId.set('other');
  h.fixture.detectChanges();
  release();
  await h.settle();
  await h.selectRlm();
  await h.save();
  const write = h.calls.find((c) => c.method === 'PUT');
  expect(write?.path).toBe('/tenants/other/knowledge/settings');
  expect((write?.body as { expected_revision: number }).expected_revision).toBe(11);
});
it('honors narrower server limits and does not offer an unsupported answer method', async () => {
  const h = await mount({
    request: async <T>() => {
      const value = settings();
      value.capabilities.documents.answer_modes = ['rag'];
      value.capabilities.documents.bounds['rlm_max_iters'] = { minimum: 1, maximum: 9 };
      return value as T;
    },
  });
  await h.settle();
  expect(h.rlm()).toBeUndefined();
  expect(h.field('documents.rlm_max_iters').max).toBe('9');
  await h.change('documents.rlm_max_iters', '10');
  await h.save();
  expect(h.calls.some((c) => c.method === 'PUT')).toBe(false);
});
it('cannot save the previous organization draft while its replacement response is pending', async () => {
  let release!: () => void;
  const h = await mount({
    request: async <T>(method: unknown, path: string) => {
      if (path.includes('/other/'))
        return await new Promise<T>((resolve) => {
          release = () => resolve(settings('other') as T);
        });
      return settings() as T;
    },
  });
  await h.settle();
  await h.selectRlm();
  h.facade.tenantId.set('other');
  (
    h.fixture.nativeElement.querySelector(
      'ffk-knowledge-behavior button[type=submit]',
    ) as HTMLButtonElement
  ).click();
  h.fixture.detectChanges();
  release();
  await h.settle();
  expect(h.calls.some((c) => c.method === 'PUT')).toBe(false);
  expect(h.fixture.nativeElement.querySelector('ffk-knowledge-behavior').textContent).toContain(
    'Other organization',
  );
});
it('opens a collapsed invalid field group and focuses the invalid control after validation', async () => {
  const h = await mount();
  await h.settle();
  await h.change('documents.rlm_max_iters', '65');
  const input = h.field('documents.rlm_max_iters');
  const details = input.closest('details')!;
  details.open = false;
  await h.save();
  expect(details.open).toBe(true);
  expect(document.activeElement).toBe(input);
  expect(h.calls.some((c) => c.method === 'PUT')).toBe(false);
});
it('does not expose organization settings to an ordinary member', async () => {
  const h = await mount({ providers: false, write: false });
  await h.settle();
  expect(h.fixture.nativeElement.querySelector('ffk-knowledge-behavior')).toBeNull();
  expect(h.calls.some((c) => c.path.endsWith('/knowledge/settings'))).toBe(false);
});
it('ignores a pending save response after the host changes organization', async () => {
  let release!: () => void;
  const h = await mount({
    request: async <T>(method: unknown, path: string) => {
      if (method === 'PUT')
        return await new Promise<T>((resolve) => {
          release = () => resolve({ ...settings(), revision: 8 } as T);
        });
      return (path.includes('/other/') ? { ...settings('other'), revision: 11 } : settings()) as T;
    },
  });
  await h.settle();
  await h.selectRlm();
  (
    h.fixture.nativeElement.querySelector(
      'ffk-knowledge-behavior button[type=submit]',
    ) as HTMLButtonElement
  ).click();
  h.facade.tenantId.set('other');
  h.fixture.detectChanges();
  release();
  await h.settle();
  const panel = h.fixture.nativeElement.querySelector('ffk-knowledge-behavior');
  expect(panel.textContent).toContain('Other organization');
  expect(panel.textContent).toContain('11');
  expect(h.calls.filter((c) => c.method === 'PUT').map((c) => c.path)).toEqual([
    '/tenants/tenant/knowledge/settings',
  ]);
  expect(h.rlm().checked).toBe(false);
});

it('shows the server recorded-processing requirement only when RLM is selected', async () => {
  const h = await mount();
  await h.settle();
  const panel = h.fixture.nativeElement.querySelector('ffk-knowledge-behavior');
  expect(panel.textContent).not.toContain('RLM needs document versions');
  await h.selectRlm();
  expect(panel.textContent).toContain(
    'RLM needs document versions with recorded processing details. Older documents may need to be reprocessed.',
  );
});
it('keeps the technical capability code inside collapsed prerequisites instead of the primary warning', async () => {
  const h = await mount();
  await h.settle();
  await h.selectRlm();
  const panel = h.fixture.nativeElement.querySelector('ffk-knowledge-behavior');
  expect(panel.querySelector('.limitation').textContent).not.toContain('KNOWLEDGE_RLM_UNQUALIFIED');
  const prerequisites = panel.querySelector('.prerequisites') as HTMLDetailsElement;
  expect(prerequisites.open).toBe(false);
  expect(prerequisites.textContent).toContain('KNOWLEDGE_RLM_UNQUALIFIED');
  expect(panel.querySelectorAll('button[type=submit]')).toHaveLength(1);
});
