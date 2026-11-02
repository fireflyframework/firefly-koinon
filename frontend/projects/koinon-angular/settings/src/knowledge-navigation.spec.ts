// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { knowledgeDomainRegistered } from './knowledge-navigation';
import type { Capabilities } from '@fireflyframework/koinon-sdk';
it('checks the actual native domain registration without treating installed as registered', () => {
  const capabilities = {
    providers: [],
    features: [],
    domains: {
      canon: { installed: true, registered: true },
      structured: { installed: true, registered: false },
    },
  } satisfies Capabilities;
  expect(knowledgeDomainRegistered(capabilities, 'documents')).toBe(true);
  expect(knowledgeDomainRegistered(capabilities, 'structured')).toBe(false);
  expect(knowledgeDomainRegistered(null, 'documents')).toBe(false);
});
