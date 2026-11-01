// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import type { ActivitySummary, ActivityWindow, BrandingValues } from "./generated.js";
import type { Membership, Page } from "./types.js";
export type CommunicationRole = Membership["role"];
export type DeliveryAddressStatus =
  "verified_directory" | "missing" | "unverified" | "unavailable";
export type DeliveryStatus =
  | "queued"
  | "sending"
  | "sent"
  | "delivered"
  | "deferred"
  | "failed"
  | "suppressed"
  | "cancelled"
  | "unknown";
export type EventKind =
  | "invitation"
  | "access_granted"
  | "role_changed"
  | "access_removed"
  | "digest"
  | "security"
  | "welcome";
export type DigestFrequency = "off" | "daily" | "weekly" | "monthly";
export interface DirectoryRecipient {
  recipient_ref: string | null;
  display_name: string;
  email: string | null;
  provider_label: string;
  delivery_address_status: DeliveryAddressStatus;
  eligibility: "eligible" | "already_has_access" | "unavailable";
  eligibility_reason: string | null;
}
export interface DirectoryRecipientPage {
  items: DirectoryRecipient[];
  next_cursor: string | null;
}
export interface EmailInvitationInput {
  recipient_ref: string;
  role: CommunicationRole;
  workspace_id?: string | null;
  expires_in_hours?: number;
  message?: string;
}
export interface InvitationDelivery {
  id: string;
  status: DeliveryStatus;
  queued_at: string;
  last_attempt_at: string | null;
  next_attempt_at: string | null;
  next_resend_at: string | null;
  failure_code: string | null;
}
export type EmailInvitationActionReason='closed'|'cooldown'|'send_limit'|'delivery_outcome_unknown'|'inviter_authority_lost'|'origin_token_revoked'|'origin_token_expired'|'origin_scope_changed'|'recipient_connection_changed';
export type EmailInvitationStatus =
  "pending" | "accepted" | "declined" | "revoked" | "expired";
export interface EmailInvitation {
  id: string;
  tenant_id: string;
  workspace_id: string | null;
  organization_name: string;
  workspace_name: string | null;
  role: CommunicationRole;
  recipient_display_name: string;
  recipient_email: string;
  provider_label: string;
  created_at: string;
  expires_at: string;
  status: EmailInvitationStatus;
  accepted_at: string | null;
  declined_at: string | null;
  revoked_at: string | null;
  delivery: InvitationDelivery;
  allowed_actions: ("revoke" | "resend")[];
  action_reasons?:Partial<Record<"accept"|"resend",EmailInvitationActionReason>>;
}
export type EmailInvitationPage = Page<EmailInvitation>;
export interface InvitationReview {
  id: string;
  tenant_id: string;
  organization_name: string;
  workspace_id: string | null;
  workspace_name: string | null;
  role: CommunicationRole;
  expires_at: string;
  status: EmailInvitationStatus;
  can_accept: boolean;
  can_decline: boolean;
  binding: "directory_identity";
  action_reasons?:Partial<Record<"accept"|"resend",EmailInvitationActionReason>>;
}
export interface EmailPreview {
  subject: string;
  sender_name: string;
  recipient_display_name: string;
  recipient_email: string;
  heading: string;
  paragraphs: string[];
  action_label: string;
  footer: string;
  product_name: string;
  accent_color: string;
  branding: BrandingValues;
  rendered_html: string;
  rendered_text: string;
  organization_name: string;
  workspace_name: string | null;
  effective_locale: string;
  locale_origin: "user" | "organization" | "installation" | "default";
  powered_by: "Powered by koinon";
  copyright: string;
  usage_summary: CommunicationUsageSummary | null;
  activity_summary?:ActivitySummary|null;
}
export interface NotificationTarget {
  kind: "invitation" | "workspace" | "access" | "none";
  id: string | null;
}
export interface OwnNotification {
  id: string;
  kind: EventKind;
  title: string;
  body: string;
  created_at: string;
  read_at: string | null;
  tenant_id: string;
  organization_name: string;
  target: NotificationTarget;
}
export type OwnNotificationPage = Page<OwnNotification>;
export interface NotificationUnreadCount {
  unread: number;
}
export interface NotificationPreferenceRule {
  kind: EventKind;
  required: boolean;
  inbox: boolean;
  email: boolean;
  email_available: boolean;
}
export interface NotificationPreferenceRuleInput {
  kind: EventKind;
  inbox: boolean;
  email: boolean;
}
export interface DigestSchedule {
  local_time: string;
  weekday: number;
  day_of_month: number;
}
export interface DigestSchedulePreview {
  digest: DigestFrequency;
  schedule: DigestSchedule;
  time_zone: string;
  next_run_at: string | null;
  next_run_local: string | null;
  window_start: string | null;
  window_end: string | null;
  dst_policy: "first_valid_minute_earlier_fold";
}
export type CommunicationLocaleOrigin =
  "user" | "organization" | "installation" | "default";
export interface NotificationPreferences {
  admin_summaries_available:boolean;
  admin_summaries_enabled:boolean;
  admin_summaries:boolean|null;
  notification_locale: string | null;
  effective_locale: string;
  locale_origin: CommunicationLocaleOrigin;
  revision: number;
  rules: NotificationPreferenceRule[];
  digest: DigestFrequency;
  allowed_digests: DigestFrequency[];
  locale: string;
  time_zone: string;
  schedule: DigestSchedule;
  next_run_at: string | null;
  next_run_local: string | null;
}
export interface NotificationPreferencesInput {
  admin_summaries?:boolean|null;
  notification_locale?: string | null;
  expected_revision: number;
  rules: NotificationPreferenceRuleInput[];
  digest: DigestFrequency;
  schedule: DigestSchedule;
}
export interface CommunicationPolicy {
  admin_summaries:AdministrativeSummarySchedule[];
  default_locale: string | null;
  revision: number;
  sender_id: string | null;
  rules: NotificationPreferenceRule[];
  digest_enabled: boolean;
  can_update: boolean;
  allowed_digests: DigestFrequency[];
  default_digest: DigestFrequency;
  default_schedule: DigestSchedule;
}
export interface CommunicationPolicyInput {
  admin_summaries?:AdministrativeSummarySchedule[];
  default_locale?: string | null;
  expected_revision: number;
  sender_id: string | null;
  rules: NotificationPreferenceRuleInput[];
  digest_enabled: boolean;
  allowed_digests: DigestFrequency[];
  default_digest: DigestFrequency;
  default_schedule: DigestSchedule;
}
export interface VerifiedSenderOption {
  id: string;
  display_name: string;
  address: string;
}
export interface CommunicationIssue {
  code: string;
  explanation: string;
}
export interface CommunicationCapabilities {
  effective_locale: string;
  locale_origin: CommunicationLocaleOrigin;
  state: "disabled" | "not_configured" | "ready" | "degraded";
  provider_label: string;
  sender_name: string;
  sender_address: string;
  reply_to: string | null;
  sender_options: VerifiedSenderOption[];
  public_address_configured: boolean;
  public_url: string | null;
  acceptance_base: string | null;
  issues: CommunicationIssue[];
}
export interface DeliveryRecord {
  id: string;
  kind: EventKind;
  channel: "email";
  invitation_id: string | null;
  membership_id: string | null;
  recipient_display: string;
  scope_name: string;
  status: DeliveryStatus;
  created_at: string;
  last_attempt_at: string | null;
  next_attempt_at: string | null;
  attempt_count: number;
  failure_code: string | null;
  safe_explanation: string | null;
  can_retry: boolean;
}
export type DeliveryPage = Page<DeliveryRecord>;

export interface RecipientProvider {
  id: string;
  display_name: string;
}
export type RecipientProviderPage = Page<RecipientProvider>;

export interface CommunicationUsageSummary {
  scope: "own";
  window_start: string;
  window_end: string;
  time_zone: string;
  assistant_runs: number;
  completed_runs: number;
  failed_runs: number;
  mcp_requests: number | null;
  mcp_request_status: "available" | "unavailable";
}

export interface AdministrativeSummarySchedule {cadence:'daily'|'weekly'|'monthly';schedule:DigestSchedule}
export interface ActivityEmailPreviewInput {tenant_id:string;preferences:NotificationPreferencesInput;window:ActivityWindow}
