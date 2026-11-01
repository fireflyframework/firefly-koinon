// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import type { KoinonTransport, RequestOptions } from "./transport.js";
import type { Membership } from "./types.js";
import type * as C from "./communications-models.js";
type Options = Pick<RequestOptions, "signal" | "headers">;
export interface CommunicationPageFilter {
  page?: number;
  page_size?: number;
}
export interface RecipientFilter {
  q?: string;
  provider_id?: string;
  workspace_id?: string;
  after?: string;
  limit?: number;
}
export interface EmailInvitationFilter extends CommunicationPageFilter {
  status?: C.EmailInvitationStatus;
  workspace_id?: string;
}
export interface DeliveryFilter extends CommunicationPageFilter {
  workspace_id?:string;
  status?: C.DeliveryStatus;
  event_kind?: C.EventKind;
  channel?: "email";
  created_from?: string;
  created_to?: string;
}
export interface NotificationFilter extends CommunicationPageFilter {
  tenant_id?: string;
  event_kind?: C.EventKind;
  read?: "all" | "unread" | "read";
}
const id = encodeURIComponent;
const tenant = (value: string) => `/tenants/${id(value)}`;
function invitationId(value: string) {
  if (
    !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(
      value,
    )
  )
    throw new TypeError("Email invitation requires a noncredential UUID");
  return value;
}
const emailBody = (input: C.EmailInvitationInput): C.EmailInvitationInput => ({
  recipient_ref: input.recipient_ref,
  role: input.role,
  workspace_id: input.workspace_id ?? null,
  expires_in_hours: input.expires_in_hours ?? 24,
  message: input.message ?? "",
});
const schedule = (input: C.DigestSchedule): C.DigestSchedule => ({
  local_time: input.local_time,
  weekday: input.weekday,
  day_of_month: input.day_of_month,
});
const rules = (input: readonly C.NotificationPreferenceRuleInput[]) =>
  input.map(({ kind, inbox, email }) => ({ kind, inbox, email }));
const preferences = (
  input: C.NotificationPreferencesInput,
): C.NotificationPreferencesInput => ({
  expected_revision: input.expected_revision,
  notification_locale: input.notification_locale ?? null,
  admin_summaries:input.admin_summaries??null,
  rules: rules(input.rules),
  digest: input.digest,
  schedule: schedule(input.schedule),
});
/** Optional API factory: applications can import it only when communications are opened. */
export function createCommunicationsApi(transport: KoinonTransport) {
  const email = (tenantId: string) => tenant(tenantId) + "/invitations/email";
  const own = (value: string) => "/invitations/email/" + invitationId(value);
  const admin = (tenantId: string) => tenant(tenantId) + "/communications";
  return {
    recipients: {
      providers: (
        tenantId: string,
        filter: CommunicationPageFilter & { workspace_id?: string } = {},
        options: Options = {},
      ) =>
        transport.request<C.RecipientProviderPage>(
          "GET",
          admin(tenantId) + "/recipient-providers",
          { ...options, query: { ...filter } },
        ),
      list: (
        tenantId: string,
        filter: RecipientFilter = {},
        options: Options = {},
      ) =>
        transport.request<C.DirectoryRecipientPage>(
          "GET",
          admin(tenantId) + "/recipients",
          { ...options, query: { ...filter } },
        ),
    },
    emailInvitations: {
      list: (
        tenantId: string,
        filter: EmailInvitationFilter = {},
        options: Options = {},
      ) =>
        transport.request<C.EmailInvitationPage>("GET", email(tenantId), {
          ...options,
          query: { ...filter },
        }),
      preview: (
        tenantId: string,
        input: C.EmailInvitationInput,
        options: Options = {},
      ) =>
        transport.request<C.EmailPreview>(
          "POST",
          email(tenantId) + "/preview",
          { ...options, body: emailBody(input) },
        ),
      create: (
        tenantId: string,
        input: C.EmailInvitationInput,
        options: Options = {},
      ) =>
        transport.request<C.EmailInvitation>("POST", email(tenantId), {
          ...options,
          body: emailBody(input),
        }),
      revoke: (tenantId: string, value: string, options: Options = {}) =>
        transport.request<void>(
          "DELETE",
          email(tenantId) + "/" + invitationId(value),
          options,
        ),
      resend: (tenantId: string, value: string, options: Options = {}) =>
        transport.request<C.EmailInvitation>(
          "POST",
          email(tenantId) + "/" + invitationId(value) + "/resend",
          options,
        ),
      review: (value: string, options: Options = {}) =>
        transport.request<C.InvitationReview>("GET", own(value), options),
      accept: (value: string, options: Options = {}) =>
        transport.request<Membership>("POST", own(value) + "/accept", options),
      decline: (value: string, options: Options = {}) =>
        transport.request<C.InvitationReview>(
          "POST",
          own(value) + "/decline",
          options,
        ),
    },
    administration: {
      capabilities: (tenantId: string, options: Options = {}) =>
        transport.request<C.CommunicationCapabilities>(
          "GET",
          admin(tenantId) + "/capabilities",
          options,
        ),
      policy: (tenantId: string, options: Options = {}) =>
        transport.request<C.CommunicationPolicy>(
          "GET",
          admin(tenantId) + "/policy",
          options,
        ),
      updatePolicy: (
        tenantId: string,
        input: C.CommunicationPolicyInput,
        options: Options = {},
      ) =>
        transport.request<C.CommunicationPolicy>(
          "PATCH",
          admin(tenantId) + "/policy",
          {
            ...options,
            body: {
              expected_revision: input.expected_revision,
              sender_id: input.sender_id,
              default_locale: input.default_locale ?? null,
            admin_summaries:(input.admin_summaries??[]).map(value=>({cadence:value.cadence,schedule:schedule(value.schedule)})),
              rules: rules(input.rules),
              digest_enabled: input.digest_enabled,
              allowed_digests: [...input.allowed_digests],
              default_digest: input.default_digest,
              default_schedule: schedule(input.default_schedule),
            } satisfies C.CommunicationPolicyInput,
          },
        ),
      deliveries: (
        tenantId: string,
        filter: DeliveryFilter = {},
        options: Options = {},
      ) =>
        transport.request<C.DeliveryPage>(
          "GET",
          admin(tenantId) + "/deliveries",
          { ...options, query: {workspace_id:filter.workspace_id,status:filter.status,kind:filter.event_kind,channel:filter.channel,created_from:filter.created_from,created_to:filter.created_to,page:filter.page,page_size:filter.page_size} },
        ),
      delivery: (tenantId: string, value: string, options: Options = {}) =>
        transport.request<C.DeliveryRecord>(
          "GET",
          admin(tenantId) + "/deliveries/" + id(value),
          options,
        ),
      retry: (tenantId: string, value: string, options: Options = {}) =>
        transport.request<C.DeliveryRecord>(
          "POST",
          admin(tenantId) + "/deliveries/" + id(value) + "/retry",
          options,
        ),
    },
    notifications: {
      previewEmail:(input:C.ActivityEmailPreviewInput,options:Options={})=>transport.request<C.EmailPreview>('POST','/notifications/preferences/email-preview',{...options,body:{tenant_id:input.tenant_id,preferences:preferences(input.preferences),window:{start_at:input.window.start_at,end_at:input.window.end_at,time_zone:input.window.time_zone}} satisfies C.ActivityEmailPreviewInput}),
      list: (filter: NotificationFilter = {}, options: Options = {}) =>
        transport.request<C.OwnNotificationPage>("GET", "/notifications", {
          ...options,
          query: {tenant_id:filter.tenant_id,kind:filter.event_kind,read:filter.read,page:filter.page,page_size:filter.page_size},
        }),
      unreadCount: (options: Options = {}) =>
        transport.request<C.NotificationUnreadCount>(
          "GET",
          "/notifications/unread-count",
          options,
        ),
      markRead: (value: string, options: Options = {}) =>
        transport.request<C.OwnNotification>(
          "POST",
          "/notifications/" + id(value) + "/read",
          options,
        ),
      preferences: (options: Options = {}) =>
        transport.request<C.NotificationPreferences>(
          "GET",
          "/notifications/preferences",
          options,
        ),
      updatePreferences: (
        input: C.NotificationPreferencesInput,
        options: Options = {},
      ) =>
        transport.request<C.NotificationPreferences>(
          "PATCH",
          "/notifications/preferences",
          { ...options, body: preferences(input) },
        ),
      previewPreferences: (
        input: C.NotificationPreferencesInput,
        options: Options = {},
      ) =>
        transport.request<C.DigestSchedulePreview>(
          "POST",
          "/notifications/preferences/preview",
          { ...options, body: preferences(input) },
        ),
    },
  };
}
export type CommunicationsApi = ReturnType<typeof createCommunicationsApi>;
