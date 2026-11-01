// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { test, expect, type Page } from '@playwright/test';
import { mockService } from './fixtures';

async function proposalFixture(page: Page, conflict = false) {
  await mockService(page, { organizationAgent: 'guide' });
  const stamp = '2026-10-27T10:00:00Z';
  const thread = {
    id: 'proposal-thread',
    title: 'Review catalog description',
    scope: {},
    created_at: stamp,
    updated_at: stamp,
    title_source: 'manual',
    revision: 1,
    folder_id: null,
    archived_at: null,
  };
  let proposal = {
    id: 'proposal-one',
    run_id: 'proposal-run',
    kind: 'catalog',
    status: 'pending',
    revision: 3,
    asset_id: 'document-one',
    before: { name: 'Service operating policy.pdf', description: '' },
    changes: { description: 'The policy for service ownership and review.' },
    expected_catalog_digest: 'a'.repeat(64),
    created_at: stamp,
  };
  const confirmations: unknown[] = [];
  const activity = {
    call_id: 'proposal-call',
    tool_name: 'propose_catalog_update',
    status: 'completed',
    summary: 'Suggested a catalog description for review.',
    occurred_at: stamp,
    result_id: 'proposal-one',
  };
  await page.route('**/bff/api/v1/tenants/*/**', (route) => {
    const request = route.request(),
      path = new URL(request.url()).pathname;
    const json = (value: unknown, status = 200) => route.fulfill({ status, json: value });
    if (path.endsWith('/agents'))
      return json({ items: [{ id: 'guide', name: 'Guide', status: 'ready', checks: [] }] });
    if (path.endsWith('/chat/threads'))
      return json({ items: [thread], page: 1, pages: 1, total: 1 });
    if (path.endsWith('/chat/threads/proposal-thread')) return json(thread);
    if (path.endsWith('/messages'))
      return json({
        items: [
          {
            id: 'proposal-answer',
            run_id: 'proposal-run',
            role: 'assistant',
            text: 'Review the suggested description before applying it.',
            status: 'completed',
            created_at: stamp,
            citations: [],
            artifacts: [
              {
                id: 'proposal-one',
                kind: 'openui',
                run_id: 'proposal-run',
                complete: true,
                language:
                  'root = KnowledgeAnswer([item])\nitem = Evidence("proposal-one", "proposal")',
              },
            ],
            tool_activities: [activity],
            tool_activity_count: 1,
            tool_activity_has_more: false,
          },
        ],
        next_cursor: null,
      });
    if (path.endsWith('/results/proposal-one'))
      return json({ id: 'proposal-one', run_id: 'proposal-run', kind: 'proposal', data: proposal });
    if (path.endsWith('/proposals/proposal-one')) return json(proposal);
    if (path.endsWith('/proposals/proposal-one/confirm')) {
      confirmations.push(request.postDataJSON());
      if (conflict)
        return json(
          { status: 409, code: 'PROPOSAL_RESOURCE_CHANGED', detail: 'The resource changed.' },
          409,
        );
      proposal = { ...proposal, status: 'applied', revision: 4 };
      return json(proposal);
    }
    return route.fallback();
  });
  await page.goto('/library');
  await page.getByRole('button', { name: 'Chat', exact: true }).click();
  await expect(
    page.getByRole('heading', { name: 'Review suggested changes', exact: true }),
  ).toBeVisible();
  return confirmations;
}

test('catalog edits require an explicit reviewed confirmation with the observed revision', async ({
  page,
}) => {
  const confirmations = await proposalFixture(page);
  expect(confirmations).toHaveLength(0);
  await expect(
    page.getByText('The policy for service ownership and review.', { exact: true }),
  ).toBeVisible();
  await page.getByRole('button', { name: 'Apply changes', exact: true }).click();
  await expect(page.locator('ffk-catalog-proposal .status')).toHaveText('Applied');
  expect(confirmations).toEqual([{ expected_revision: 3, confirm: true }]);
});

test('a changed source blocks applying a proposal even after refreshing the old suggestion', async ({
  page,
}) => {
  const confirmations = await proposalFixture(page, true);
  await page.getByRole('button', { name: 'Apply changes', exact: true }).click();
  await expect(
    page.getByText('The resource changed. Request a new proposal before applying changes.', {
      exact: true,
    }),
  ).toBeVisible();
  await expect(page.getByRole('button', { name: 'Apply changes', exact: true })).toBeDisabled();
  await page.getByRole('button', { name: 'Refresh proposal', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Apply changes', exact: true })).toBeDisabled();
  expect(confirmations).toHaveLength(1);
});
