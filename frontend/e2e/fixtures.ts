// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { expect, type Page } from '@playwright/test';
import type {
  CatalogEntry,
  CatalogSummary,
  ContextResponse,
  PublicActor,
} from '@fireflyframework/koinon-sdk';
export const entry = (
  id: string,
  kind: CatalogEntry['kind'],
  name: string,
  parent_id: string | null,
  extra: Partial<CatalogEntry> = {},
): CatalogEntry => ({
  id,
  tenant_id: 'tenant-one',
  kind,
  name,
  parent_id,
  workspace_id: kind === 'workspace' ? id : 'workspace-one',
  project_id: kind === 'workspace' ? null : kind === 'project' ? id : 'project-one',
  description: '',
  status: 'ready',
  metadata: {},
  created_at: '2026-10-26T09:00:00Z',
  ...extra,
});
export const fixtures: CatalogEntry[] = [
  entry('workspace-one', 'workspace', 'Research operations', null, {
    description: 'A shared home for policy evidence and operational data.',
  }),
  entry('project-one', 'project', 'Operations intelligence', 'workspace-one', {
    description: 'Documents and datasets supporting the operating model.',
  }),
  entry('collection-one', 'collection', 'Reference library', 'project-one'),
  entry('source-one', 'source', 'Policy and service records', 'collection-one'),
  entry('document-one', 'document', 'Service operating policy.pdf', 'source-one', {
    description: 'Policy source with indexed sections and provenance.',
  }),
  entry('dataset-one', 'dataset', 'Quarterly service activity', 'source-one', {
    description: 'Structured activity with published tables.',
  }),
  entry('table-one', 'table', 'service_activity', 'dataset-one'),
  entry('chunk-one', 'chunk', 'Service ownership and review', 'document-one'),
];
export const context: ContextResponse = {
  subject: 'synthetic.reviewer',
  tenants: [
    {
      id: 'tenant-one',
      name: 'Knowledge operations',
      roles: ['admin'],
      permissions: [
        'catalog:read',
        'catalog:write',
        'ingest:write',
        'query:execute',
        'knowledge:search',
        'members:write',
        'audit:read',
        'providers:write',
        'agents:write',
        'sources:configure',
        'indexes:manage',
        'jobs:manage',
        'settings:write',
        'identity:manage',
        'chat:use',
      ],
    },
    {
      id: 'tenant-two',
      name: 'Read-only organization',
      roles: ['viewer'],
      permissions: ['catalog:read', 'knowledge:search'],
    },
  ],
  memberships: [],
  workspaces: [fixtures[0]],
};
export async function mockService(
  page: Page,
  options: {
    authenticated?: boolean;
    error?: boolean;
    summaries?: Record<string, CatalogSummary>;
    actors?: Record<string, PublicActor>;
    organizationAgent?: string | null;
  } = {},
) {
  const rows = structuredClone(fixtures);
  const reads: { path: string; query: Record<string, string> }[] = [];
  const previousStatus = new Map<string, string>();
  const writes: { path: string; method: string; body: unknown; csrf?: string }[] = [];
  await page
    .context()
    .addCookies([
      { name: 'XSRF-TOKEN', value: 'synthetic-csrf%2Btoken', domain: '127.0.0.1', path: '/' },
    ]);
  await page.route('**/bff/api/v1/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname.replace('/bff/api/v1', '');
    const respond = (body: unknown, status = 200) =>
      route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });
    if (options.authenticated === false)
      return respond({ detail: 'Sign in is required', code: 'UNAUTHENTICATED' }, 401);
    if (options.error)
      return respond({ detail: 'Catalog database is unavailable', code: 'UNAVAILABLE' }, 503);
    if (path === '/profile')
      return respond({
        subject: 'synthetic.reviewer',
        display_name: 'Alex Rivera',
        locale: 'en-US',
        time_zone: 'UTC',
        response_language: 'en',
        avatar_url: null,
        avatar_version: null,
      });
    if (path === '/context') return respond(context);
    if (path.endsWith('/chat/settings')) {
      const id = options.organizationAgent ?? null;
      return respond({
        tenant_id: path.split('/')[2],
        default_agent_id: id,
        revision: 1,
        configured: !!id,
        can_run: !!id,
        status: id ? 'ready' : 'unconfigured',
      });
    }
    if (path.endsWith('/configuration'))
      return respond({
        providers: [],
        provider_types: [],
        connections: [],
        checks: [
          {
            id: 'model_setup',
            status: 'needs_setup',
            message: 'Configure a supported local or hosted model.',
          },
        ],
      });
    if (path === '/capabilities')
      return respond({
        providers: [
          {
            id: 'local-storage',
            name: 'Local source storage',
            kind: 'storage',
            configured: true,
            available: true,
            capabilities: ['source files', 'local Parquet'],
          },
          {
            id: 'language-model',
            name: 'Language model',
            kind: 'language model',
            configured: false,
            available: false,
            reason:
              'Configure a supported local or hosted model before running grounded generation.',
            capabilities: ['grounded answers', 'SQL generation'],
          },
        ],
        features: [
          { id: 'catalog', name: 'Knowledge catalog', available: true },
          {
            id: 'query',
            name: 'Natural-language query',
            available: false,
            reason: 'A model provider is required.',
          },
        ],
      });
    if (request.method() === 'GET')
      reads.push({ path, query: Object.fromEntries(url.searchParams) });
    if (request.method() !== 'GET') {
      let body: unknown;
      try {
        body = request.postDataJSON();
      } catch {
        body = request.postData();
      }
      writes.push({
        path,
        method: request.method(),
        body,
        csrf: request.headers()['x-xsrf-token'],
      });
    }
    if (path.endsWith('/chat/folders') && request.method() === 'GET')
      return respond({
        items: [],
        total: 0,
        page: Number(url.searchParams.get('page') || 1),
        page_size: Number(url.searchParams.get('page_size') || 25),
        pages: 0,
      });
    if (path.endsWith('/catalog')) {
      if (request.method() === 'POST') {
        const body = request.postDataJSON();
        const created = entry(
          'created-' + rows.length,
          body.kind,
          body.name,
          body.parent_id ?? null,
          { description: body.description ?? '' },
        );
        rows.push(created);
        return respond(created, 201);
      }
      const tenant = path.includes('tenant-two') ? 'tenant-two' : 'tenant-one';
      const archived = (row: CatalogEntry) => {
        let current: CatalogEntry | undefined = row;
        const seen = new Set<string>();
        while (current && !seen.has(current.id)) {
          if (current.status === 'archived') return true;
          seen.add(current.id);
          current = rows.find((x) => x.id === current?.parent_id);
        }
        return false;
      };
      let selected = rows.filter(
        (row) =>
          row.tenant_id === tenant &&
          (url.searchParams.get('include_archived') === 'true' || !archived(row)) &&
          (!url.searchParams.get('workspace_id') ||
            row.workspace_id === url.searchParams.get('workspace_id')),
      );
      const parent = url.searchParams.get('parent_id') || '';
      if (url.searchParams.get('view') === 'library') {
        const folder = rows.find((row) => row.id === parent);
        if (folder?.kind === 'collection' || folder?.kind === 'corpus') {
          const sources = selected.filter(
            (row) => row.kind === 'source' && row.parent_id === parent,
          );
          selected = selected.filter(
            (row) =>
              (['document', 'dataset'].includes(row.kind) &&
                sources.some((source) => source.id === row.parent_id)) ||
              (row.kind === 'source' &&
                row.parent_id === parent &&
                !rows.some(
                  (file) =>
                    file.parent_id === row.id && ['document', 'dataset'].includes(file.kind),
                )),
          );
        } else
          selected = selected.filter(
            (row) =>
              ['workspace', 'project', 'collection', 'corpus'].includes(row.kind) &&
              (row.parent_id ?? '') === parent,
          );
      } else if (parent) selected = selected.filter((row) => row.parent_id === parent);
      const q = (url.searchParams.get('q') || '').toLowerCase(),
        kind = url.searchParams.get('kind'),
        status = url.searchParams.get('status');
      selected = selected.filter(
        (row) =>
          (!q || row.name.toLowerCase().includes(q)) &&
          (!kind || row.kind === kind) &&
          (!status || row.status === status) &&
          (!url.searchParams.get('format') ||
            options.summaries?.[row.id]?.format === url.searchParams.get('format')) &&
          (!url.searchParams.get('tag') ||
            options.summaries?.[row.id]?.tags.includes(url.searchParams.get('tag')!)),
      );
      const sort = url.searchParams.get('sort') || 'name',
        order = url.searchParams.get('order') === 'desc' ? -1 : 1;
      selected.sort(
        (a, b) =>
          String(a[sort as keyof CatalogEntry] || '').localeCompare(
            String(b[sort as keyof CatalogEntry] || ''),
          ) * order,
      );
      const page = Number(url.searchParams.get('page') || 1),
        page_size = Number(url.searchParams.get('page_size') || 25),
        total = selected.length;
      return respond({
        items: selected.slice((page - 1) * page_size, page * page_size),
        summaries: Object.fromEntries(
          selected
            .slice((page - 1) * page_size, page * page_size)
            .flatMap((row) =>
              options.summaries?.[row.id] ? [[row.id, options.summaries[row.id]]] : [],
            ),
        ),
        actors: options.actors ?? {},
        total,
        page,
        page_size,
        pages: Math.max(1, Math.ceil(total / page_size)),
      });
    }
    if (path.includes('/catalog/') && (path.endsWith('/archive') || path.endsWith('/restore'))) {
      const id = path.split('/').at(-2),
        row = rows.find((item) => item.id === id);
      if (!row) return respond({ detail: 'Resource is not accessible' }, 404);
      if (path.endsWith('/archive')) {
        previousStatus.set(row.id, row.status);
        row.status = 'archived';
      } else {
        row.status = previousStatus.get(row.id) || 'ready';
        previousStatus.delete(row.id);
      }
      return respond(row);
    }
    if (path.includes('/catalog/')) {
      const id = path.split('/').pop();
      const row = rows.find((item) => item.id === id);
      if (!row) return respond({ detail: 'Resource is not accessible' }, 404);
      if (request.method() === 'PATCH') {
        Object.assign(row, request.postDataJSON());
        return respond(row);
      }
      if (request.method() === 'DELETE')
        return respond(
          { detail: 'Permanent deletion is not part of this controlled user workflow' },
          405,
        );
      return respond(row);
    }
    if (path.endsWith('/search'))
      return respond({
        answer: 'Service ownership is reviewed with the policy evidence.',
        hits: [
          {
            id: 'hit-one',
            title: 'Service operating policy.pdf',
            text: 'The service owner maintains the documented review and supporting evidence.',
            asset_id: 'document-one',
            source_id: 'source-one',
          },
        ],
        citations: [
          {
            title: 'Service operating policy.pdf',
            document_id: 'document-one',
            text: 'The service owner maintains the documented review.',
            page: 3,
          },
        ],
      });
    if (path.endsWith('/query'))
      return respond({
        query_id: 'query-one',
        sql: 'SELECT region, COUNT(*) AS activity_count FROM service_activity GROUP BY region',
        execution_status: 'OK',
        preview: [
          { region: 'North', activity_count: 18 },
          { region: 'South', activity_count: 12 },
        ],
        row_count: 2,
        truncated: false,
        elapsed_ms: 37,
        chart_hint: 'bar',
        explanation: 'The returned activity is grouped by region.',
        snapshot_pins: { service_activity: 'snapshot-one' },
      });
    if (path.includes('/schema'))
      return respond({
        tables: [
          {
            id: 'table-one',
            name: 'service_activity',
            snapshot_id: 'snapshot-one',
            columns: [
              {
                id: 'column-one',
                name: 'region',
                data_type: 'VARCHAR',
                description: 'Recorded service region.',
              },
              { id: 'column-two', name: 'activity_count', data_type: 'BIGINT' },
            ],
          },
        ],
      });
    if (path.endsWith('/jobs'))
      return respond({
        items: [
          {
            id: 'job-one',
            tenant_id: 'tenant-one',
            resource_id: 'source-one',
            kind: 'INGEST',
            status: 'RUNNING',
            attempts: 1,
            max_attempts: 3,
            progress: 50,
            error: null,
            created_at: '2026-10-26T09:00:00Z',
            updated_at: '2026-10-26T09:01:00Z',
            result: null,
          },
        ],
      });
    if (path.endsWith('/cancel'))
      return respond({
        id: 'job-one',
        status: 'CANCELLED',
        progress: 50,
        attempts: 1,
        max_attempts: 3,
        updated_at: '2026-10-26T09:02:00Z',
      });
    if (path.endsWith('/lineage'))
      return respond({
        nodes: [
          { id: 'source-one', label: 'Policy and service records', kind: 'source' },
          { id: 'document-one', label: 'Service operating policy.pdf', kind: 'document' },
          { id: 'dataset-one', label: 'Quarterly service activity', kind: 'dataset' },
        ],
        edges: [
          { source: 'source-one', target: 'document-one', label: 'produces' },
          { source: 'source-one', target: 'dataset-one', label: 'produces' },
        ],
      });
    if (path.endsWith('/members'))
      return respond({
        items: [
          {
            id: 'member-one',
            subject: 'synthetic.reviewer',
            tenant_id: 'tenant-one',
            workspace_id: null,
            role: 'admin',
            active: true,
          },
        ],
      });
    if (path.endsWith('/audit'))
      return respond({
        items: [
          {
            id: 'event-one',
            subject: 'synthetic.reviewer',
            action: 'catalog.created',
            resource_id: 'workspace-one',
            details: { kind: 'workspace' },
            created_at: '2026-10-26T09:00:00Z',
          },
        ],
      });
    if (path.endsWith('/sources/upload'))
      return respond(
        {
          source: entry('source-uploaded', 'source', 'Uploaded source', 'collection-one'),
          assets: [],
        },
        201,
      );
    if (path.startsWith('/structured'))
      return respond({ items: [], total: 0, limit: 50, offset: 0 });
    return respond({ detail: 'No controlled test fixture is defined for this operation.' }, 404);
  });
  return { rows, writes, reads };
}
export async function setDarkAppearance(page: Page, spanish = false) {
  const label = spanish ? 'Usar tema oscuro' : 'Use dark theme';
  const header = page.getByRole('button', { name: label, exact: true });
  if (await header.isVisible()) {
    await header.click();
    return;
  }
  await page
    .getByRole('button', { name: spanish ? 'Menú de cuenta' : 'Account menu', exact: true })
    .click();
  await page.getByRole('menuitem', { name: label, exact: true }).click();
  await page.keyboard.press('Escape');
  await expect(
    page.getByRole('menuitem', {
      name: spanish ? 'Usar tema claro' : 'Use light theme',
      exact: true,
    }),
  ).not.toBeVisible();
}
