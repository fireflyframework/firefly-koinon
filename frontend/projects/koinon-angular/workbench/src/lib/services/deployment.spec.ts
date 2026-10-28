// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { observationLabel } from '../../../../settings/src/deployment-panel';
describe('observed deployment readiness', () => {
  it('keeps unverified observations distinct from available and failed resources', () => {
    expect(observationLabel({ available: null })).toBe('Not checked');
    expect(observationLabel({ available: false })).toBe('Needs attention');
    expect(observationLabel({ available: true })).toBe('Available');
  });
});
it('does not infer a configured storage backend from missing observation metadata', async () => {
  const { KoinonDeploymentPanel } = await import('../../../../settings/src/deployment-panel');
  const panel = new KoinonDeploymentPanel();
  expect(panel.backendName(null)).toBe('Not reported');
  expect(panel.backendName(undefined)).toBe('Not reported');
  expect(panel.backendName('s3')).toBe('Amazon S3');
});
