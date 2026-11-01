// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { TestBed } from '@angular/core/testing';
import { KoinonActivitySummary } from '../../../../activity/activity-summary';
it('shows unknown observations without turning them into zero or invented project bars', () => {
  const fixture = TestBed.createComponent(KoinonActivitySummary);
  fixture.componentRef.setInput('value', {
    tenant_id: 'org',
    audience: 'personal',
    window: {
      start_at: '2026-10-01T00:00:00Z',
      end_at: '2026-10-08T00:00:00Z',
      time_zone: 'Europe/Madrid',
    },
    coverage: {
      observed_since: null,
      complete_window: false,
      reasons: ['OBSERVATIONS_STARTED_LATE'],
    },
    knowledge: {
      created: { value: 3, status: 'partial' },
      updated: { value: 0, status: 'observed' },
      consulted: { value: null, status: 'unavailable' },
    },
    top_projects: [],
    daily_activity: [],
    mcp: {
      requests: { value: null, status: 'unavailable' },
      tool_calls: { value: 4, status: 'observed' },
      succeeded: { value: 3, status: 'observed' },
      failed: { value: 1, status: 'observed' },
      rejected: { value: 0, status: 'observed' },
      average_duration_ms: { value: null, status: 'unavailable' },
      p95_duration_ms: { value: null, status: 'unavailable' },
    },
    models: {
      input_tokens: { value: null, status: 'unavailable' },
      output_tokens: { value: null, status: 'unavailable' },
      embedding_tokens: { value: null, status: 'unavailable' },
      cost: { amount: null, currency: null, status: 'unavailable' },
      external_client_consumption: 'not_observed',
    },
  });
  fixture.detectChanges();
  expect(fixture.nativeElement.textContent).toContain('Unavailable');
  expect(fixture.nativeElement.textContent).toContain('Partial coverage');
  expect(fixture.nativeElement.textContent).toContain(
    'External client token usage is not observed.',
  );
  expect(fixture.nativeElement.querySelectorAll('.project-bar').length).toBe(0);
});
