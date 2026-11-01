// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import type {
  DigestFrequency,
  DigestSchedule,
  DigestSchedulePreview,
  AdministrativeSummarySchedule,
  Membership,
  Page,
  BrandingValues,
} from '@fireflyframework/koinon-sdk';

export interface DirectoryRecipientView {
  recipient_ref: string | null;
  display_name: string;
  email: string | null;
  provider_label: string;
  delivery_address_status: 'verified_directory' | 'missing' | 'unverified' | 'unavailable';
  eligibility: 'eligible' | 'already_has_access' | 'unavailable';
  eligibility_reason: string | null;
}
export interface RecipientPage {
  items: DirectoryRecipientView[];
  next_cursor: string | null;
}
export interface CommunicationRole {
  id: Membership['role'];
  label: string;
  description: string;
}
export interface CommunicationScope {
  id: string;
  name: string;
}
export interface EmailInvitationDraft {
  recipient_ref: string;
  role: Membership['role'];
  workspace_id: string | null;
  expires_in_hours: number;
}
export interface CommunicationEmailPreview {
  branding?: BrandingValues;
  product_name?: string;
  accent_color?: string;
  recipient_display_name?: string;
  recipient_email?: string;
  subject: string;
  sender_name: string;
  heading: string;
  paragraphs: string[];
  action_label: string;
  footer: string;
  rendered_html?: string;
  rendered_text?: string;
  organization_name?: string;
  workspace_name?: string | null;
  effective_locale?: string;
}
export interface InvitationEmailPreview extends CommunicationEmailPreview {
  draft: EmailInvitationDraft;
}

export type DeliveryState =
  | 'queued'
  | 'sending'
  | 'sent'
  | 'delivered'
  | 'deferred'
  | 'failed'
  | 'suppressed'
  | 'cancelled'
  | 'unknown';
export interface InvitationQueuedView {
  invitation_id: string;
  recipient_display_name: string;
  recipient_email: string;
  delivery_status: DeliveryState;
}
export type CommunicationEvent =
  | 'invitation'
  | 'access_granted'
  | 'role_changed'
  | 'access_removed'
  | 'digest'
  | 'security'
  | 'welcome';
export interface NotificationTarget {
  kind: 'invitation' | 'workspace' | 'access' | 'none';
  id: string;
}
export interface OwnNotificationView {
  id: string;
  kind: CommunicationEvent;
  title: string;
  body: string;
  created_at: string;
  read_at: string | null;
  organization_name: string | null;
  target: NotificationTarget;
}
export interface NotificationFilter {
  page: number;
  page_size: number;
  read: 'all' | 'unread';
  kind: CommunicationEvent | '';
}
export interface NotificationPreferenceRule {
  kind: CommunicationEvent;
  label: string;
  description: string;
  required: boolean;
  inbox: boolean;
  email: boolean;
  email_available: boolean;
}
export interface NotificationPreferencesView {
  admin_summaries?: boolean | null;
  admin_summaries_available?: boolean;
  admin_summaries_enabled?: boolean;
  notification_locale?: string | null;
  effective_locale?: string;
  locale_origin?: 'user' | 'organization' | 'installation' | 'default';
  revision: number;
  rules: NotificationPreferenceRule[];
  digest: DigestFrequency;
  allowed_digests: DigestFrequency[];
  locale: string;
  time_zone: string;
  schedule?: DigestSchedule;
  next_run_at?: string | null;
  next_run_local?: string | null;
}
export type {
  DigestFrequency,
  DigestSchedule,
  DigestSchedulePreview,
  AdministrativeSummarySchedule,
};
export interface NotificationPreferencesUpdate {
  admin_summaries?: boolean | null;
  notification_locale?: string | null;
  expected_revision: number;
  rules: { kind: CommunicationEvent; inbox: boolean; email: boolean }[];
  digest: DigestFrequency;
  schedule: DigestSchedule;
}
export interface CommunicationReadiness {
  state: 'disabled' | 'not_configured' | 'ready' | 'degraded';
  provider_label: string;
  sender_name: string;
  sender_address: string;
  reply_to: string | null;
  sender_options?: { id: string; display_name: string; address: string }[];
  public_address_configured: boolean;
  issues: { code: string; explanation: string }[];
}
export interface CommunicationPolicyView {
  admin_summaries?: AdministrativeSummarySchedule[];
  default_locale?: string | null;
  revision: number;
  sender_id?: string | null;
  rules: NotificationPreferenceRule[];
  digest_enabled: boolean;
  can_update: boolean;
  allowed_digests?: DigestFrequency[];
  default_digest?: DigestFrequency;
  default_schedule?: DigestSchedule;
}
export interface DeliveryRecordView {
  id: string;
  kind: CommunicationEvent;
  recipient_display: string;
  scope_name: string;
  status: DeliveryState;
  created_at: string;
  last_attempt_at: string | null;
  next_attempt_at: string | null;
  attempt_count: number;
  failure_code: string | null;
  safe_explanation: string | null;
  can_retry: boolean;
}
export interface DeliveryFilter {
  page: number;
  page_size: number;
  status: DeliveryState | '';
  kind: CommunicationEvent | '';
  from: string;
  to: string;
}
export type NotificationPage = Page<OwnNotificationView>;
export type DeliveryPage = Page<DeliveryRecordView>;
export interface RecipientInvitationReviewView {
  id: string;
  organization_name: string;
  workspace_name: string | null;
  role_name: string;
  role_description: string;
  expires_at: string;
  status: 'pending' | 'accepted' | 'declined' | 'revoked' | 'expired';
  accept_reason?: string;
  can_accept: boolean;
  can_decline: boolean;
}
