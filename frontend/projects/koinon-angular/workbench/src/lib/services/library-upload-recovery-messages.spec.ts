// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { uploadRecoveryReason, uploadProcessingHelp } from './library-upload-recovery-messages';
it('explains a processing context failure without exposing technical exception prose', () => {
  expect(uploadProcessingHelp('INGEST_EXECUTION_CONTEXT_REQUIRED')).toContain('administrator');
  expect(uploadProcessingHelp('INGEST_EXECUTION_CONTEXT_REQUIRED')).not.toContain('INGEST_');
});
it('keeps unknown native outcomes explicit and never suggests an automatic retry', () => {
  expect(uploadRecoveryReason('BULK_NATIVE_OUTCOME_UNRESOLVED')).toContain('not confirmed');
  expect(uploadRecoveryReason('BULK_RETRY_EXHAUSTED')).toContain('limit');
});
it('does not display an unrecognized server code as user-facing prose', () => {
  expect(uploadRecoveryReason('private-provider-error')).not.toContain('private-provider-error');
  expect(uploadProcessingHelp('private-provider-error')).not.toContain('private-provider-error');
});
