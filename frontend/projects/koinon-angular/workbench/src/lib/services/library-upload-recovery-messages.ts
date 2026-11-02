// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
const reasons: Record<string, string> = {
  BULK_RECOVERY_UNAVAILABLE:
    'Recovery is not available for this upload. Check whether it was cancelled, expired or submitted.',
  BULK_RECOVERY_NOT_REQUIRED: 'No recovery action is required for the recorded processing state.',
  BULK_RECOVERY_BUSY: 'Processing is still active or queued. Wait, then inspect recovery again.',
  BULK_NATIVE_RECEIPT_REQUIRED:
    'A processing receipt is needed before recovery can be offered. Ask an administrator to inspect the processing job.',
  BULK_CONNECTION_CHANGED:
    'The source connection changed. An administrator must review it before recovery.',
  BULK_NATIVE_SCOPE_CHANGED:
    'The knowledge destination changed. An administrator must review its scope before recovery.',
  BULK_NATIVE_REQUIRED:
    'The processing service is not available. An administrator must restore it before recovery.',
  BULK_NATIVE_OUTCOME_UNRESOLVED:
    'The processing outcome is not confirmed. Nothing will be repeated until a safe recovery action is available.',
  BULK_NATIVE_RECEIPT_CONFLICT:
    'The recorded processing receipts disagree. An administrator must inspect them before recovery.',
  BULK_RETRY_EXHAUSTED:
    'The processing attempt limit has been reached. Ask an administrator to inspect the failure.',
  BULK_ORIGINAL_UNAVAILABLE:
    'The retained original is not available for this recovery. Ask an administrator to check storage.',
  BULK_RECOVERY_STATE_CHANGED:
    'The processing state changed. Inspect recovery again before choosing an action.',
};
export function uploadRecoveryReason(code: string | null | undefined) {
  return (
    (code && reasons[code]) ||
    'No safe recovery action could be confirmed. Refresh the upload and ask an administrator to inspect processing.'
  );
}
export function uploadProcessingHelp(code: string | null | undefined) {
  return code === 'INGEST_EXECUTION_CONTEXT_REQUIRED'
    ? 'The service could not start this processing step securely. An administrator must update the processing service, then review recovery.'
    : code
      ? 'This processing step needs attention. Inspect recovery to see whether the retained original can be used safely.'
      : '';
}
export const PROCESSING_RECOVERY_OPERATIONS = [
  'retry_processing',
  'finalize_publication',
  'acknowledge_commit',
] as const;
export function isProcessingRecovery(
  value: string,
): value is (typeof PROCESSING_RECOVERY_OPERATIONS)[number] {
  return PROCESSING_RECOVERY_OPERATIONS.some((operation) => operation === value);
}
