// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
const reasons: Record<string, string> = {
  WELCOME_RECOVERY_IDEMPOTENCY_REQUIRED:
    'A stable request key is required. Review the original request before continuing.',
  EMAIL_INSPECTION_IDEMPOTENCY_REQUIRED:
    'A stable request key is required. Review the original request before continuing.',
  EMAIL_OPERATION_LOOKUP_UNAVAILABLE: 'The configured email service cannot inspect this operation.',
  EMAIL_PROVIDER_BINDING_REQUIRED:
    'A deployment operator must verify the original email service before a new check.',
  EMAIL_PROVIDER_BINDING_CHANGED:
    'The email service changed. A deployment operator must review the original operation.',
  EMAIL_DELIVERY_CHANGED: 'The delivery changed. Refresh its details before continuing.',
  EMAIL_INSPECTION_THROTTLED:
    'A recent check already exists. Wait before requesting another check.',
  EMAIL_INSPECTION_EXPIRED: 'The earlier check did not complete. Its result remains unknown.',
  EMAIL_INSPECTION_CANCELLED: 'The check was cancelled. No recipient receipt was established.',
  EMAIL_INSPECTION_CONFLICT:
    'The saved inspection request differs. Refresh the delivery before continuing.',
  EMAIL_STATUS_UNAVAILABLE: 'The email service did not return a usable status.',
  EMAIL_INVALID_OPERATION: 'The retained operation could not be verified.',
  EMAIL_INVALID_PROVIDER_RECEIPT: 'The email service receipt could not be verified.',
  EMAIL_SEND_REJECTED: 'The email service rejected the operation.',
  WELCOME_RECOVERY_REQUEST_CONFLICT: 'This request key belongs to a different welcome recovery.',
  WELCOME_RECOVERY_CHANGED:
    'The welcome or approved contact changed. Refresh before reviewing another request.',
  WELCOME_RECOVERY_THROTTLED:
    'A recent welcome recovery exists. Review it before requesting another welcome.',
  WELCOME_RECOVERY_OPERATOR_REQUIRED:
    'A deployment operator must review this welcome before it can be recovered.',
  WELCOME_RECOVERY_CONTACT_UNAVAILABLE:
    'A current approved recipient is required before sending another welcome.',
  WELCOME_RECOVERY_NOT_WELCOME: 'This delivery is not an eligible welcome.',
  COMMUNICATIONS_NOT_READY:
    'The email service or sender needs configuration before another welcome can be queued.',
  EMAIL_INVITATION_UNAVAILABLE: 'The recipient is no longer eligible for this operation.',
};
export const deliveryReason = (code: string | null | undefined) =>
  code
    ? (reasons[code] ??
      'No action is available. Ask a deployment operator to inspect this delivery.')
    : '';
export const operationLabel = (state: string) =>
  ({
    checking: 'Check in progress',
    pending: 'Provider operation pending',
    accepted: 'Accepted by email service',
    rejected: 'Rejected by email service',
    unknown: 'Provider outcome unknown',
    unavailable: 'Provider status unavailable',
  })[state] ?? 'Provider outcome unknown';
