// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import type { EmailInvitationActionReason } from '@fireflyframework/koinon-sdk';
const reasons: Record<EmailInvitationActionReason, string> = {
  closed: 'This invitation is closed. Ask an administrator for a new invitation.',
  cooldown: 'Wait before sending this invitation again.',
  send_limit: 'This invitation has reached its send limit.',
  delivery_outcome_unknown:
    'The previous delivery outcome is unknown. Check delivery history before taking another action.',
  inviter_authority_lost:
    'The inviter no longer has authority to grant this access. Ask an administrator for a new invitation.',
  origin_token_revoked:
    'The original authorization was revoked. Ask an administrator for a new invitation.',
  origin_token_expired:
    'The original authorization expired. Ask an administrator for a new invitation.',
  origin_scope_changed:
    'The original access scope changed. Ask an administrator for a new invitation.',
  recipient_connection_changed:
    'The recipient directory connection changed. Ask an administrator for a new invitation.',
};
export function invitationActionReason(value: EmailInvitationActionReason | undefined) {
  return value
    ? (reasons[value] ??
        'This action is not available. Refresh the invitation for its current status.')
    : '';
}
