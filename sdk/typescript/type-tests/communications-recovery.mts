// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { createCommunicationsApi, type WelcomeRecoveryInput } from '../src/communications.js';
import type { KoinonTransport } from '../src/transport.js';
declare const transport: KoinonTransport;
const api = createCommunicationsApi(transport);
const input: WelcomeRecoveryInput = {
  expected_generation: 0,
  contact_id: 'approved-contact',
  expected_contact_revision: 1,
  reason: 'recipient_reported_not_received',
  acknowledge_possible_duplicate: true,
};
void api.administration.recoverWelcome('organization', 'original', input, 'retained-request-key');
// @ts-expect-error A new welcome requires a stable caller-supplied request key.
void api.administration.recoverWelcome('organization', 'original', input);
// @ts-expect-error The recovery contract requires explicit possible-duplicate consent.
const missingConsent: WelcomeRecoveryInput = { ...input, acknowledge_possible_duplicate: false };
// @ts-expect-error An approved target cannot be replaced with an arbitrary email address.
const arbitraryRecipient: WelcomeRecoveryInput = { ...input, recipient_email: 'person@example.invalid' };
void missingConsent;
void arbitraryRecipient;
