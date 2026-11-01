# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Credential-free communications contracts; directory identity stays server-owned."""

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from koinon.activity.dtos import ActivitySummary, ActivityWindow
from koinon.catalog.dtos import Role
from koinon.communications.locales import normalize_locale
from koinon.organization_branding.dtos import BrandingValues

DeliveryAddressStatus = Literal["verified_directory", "missing", "unverified", "unavailable"]
DeliveryStatus = Literal[
    "queued", "sending", "sent", "delivered", "deferred", "failed", "suppressed", "cancelled", "unknown"
]
EventKind = Literal[
    "invitation", "access_granted", "role_changed", "access_removed", "security", "welcome", "digest"
]
DigestFrequency = Literal["off", "daily", "weekly", "monthly"]
EmailInvitationActionReason = Literal[
    "closed",
    "cooldown",
    "send_limit",
    "delivery_outcome_unknown",
    "inviter_authority_lost",
    "origin_token_revoked",
    "origin_token_expired",
    "origin_scope_changed",
    "recipient_connection_changed",
]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Output(BaseModel):
    model_config = ConfigDict(frozen=True)


class DirectoryRecipient(Output):
    recipient_ref: str | None
    display_name: str
    email: str | None
    provider_label: str
    delivery_address_status: DeliveryAddressStatus
    eligibility: Literal["eligible", "already_has_access", "unavailable"]
    eligibility_reason: str | None = None


class DirectoryRecipientPage(Output):
    items: list[DirectoryRecipient]
    next_cursor: str | None = None


class RecipientProvider(Output):
    id: str
    display_name: str


class RecipientProviderPage(Output):
    items: list[RecipientProvider]
    total: int
    page: int
    page_size: int
    pages: int


class EmailInvitationInput(Input):
    recipient_ref: str = Field(min_length=8, max_length=4096, repr=False)
    role: Role
    workspace_id: str | None = Field(default=None, max_length=64)
    expires_in_hours: int = Field(default=24, ge=1, le=168)
    message: str = Field(default="", max_length=1000)

    @field_validator("message")
    @classmethod
    def plain_message(cls, value):
        if any(ord(char) < 32 and char not in "\n\t" for char in value):
            raise ValueError("Use plain readable invitation text")
        return value.strip()


class InvitationDelivery(Output):
    id: str
    status: DeliveryStatus
    queued_at: datetime
    last_attempt_at: datetime | None = None
    next_attempt_at: datetime | None = None
    next_resend_at: datetime | None = None
    failure_code: str | None = None


class EmailInvitation(Output):
    action_reasons: dict[Literal["accept", "resend"], EmailInvitationActionReason] = Field(
        default_factory=dict
    )
    id: str
    tenant_id: str
    workspace_id: str | None
    organization_name: str
    workspace_name: str | None
    role: Role
    recipient_display_name: str
    recipient_email: str
    provider_label: str
    created_at: datetime
    expires_at: datetime
    status: Literal["pending", "accepted", "declined", "revoked", "expired"]
    accepted_at: datetime | None = None
    declined_at: datetime | None = None
    revoked_at: datetime | None = None
    delivery: InvitationDelivery
    allowed_actions: list[Literal["revoke", "resend"]]


class EmailInvitationPage(Output):
    items: list[EmailInvitation]
    total: int
    page: int
    page_size: int
    pages: int


class InvitationReview(Output):
    action_reasons: dict[Literal["accept", "resend"], EmailInvitationActionReason] = Field(
        default_factory=dict
    )
    id: str
    tenant_id: str
    organization_name: str
    workspace_id: str | None
    workspace_name: str | None
    role: Role
    expires_at: datetime
    status: Literal["pending", "accepted", "declined", "revoked", "expired"]
    can_accept: bool
    can_decline: bool
    binding: Literal["directory_identity"] = "directory_identity"


class CommunicationUsageSummary(Output):
    scope: Literal["own"] = "own"
    window_start: datetime
    window_end: datetime
    time_zone: str
    assistant_runs: int = Field(ge=0)
    completed_runs: int = Field(ge=0)
    failed_runs: int = Field(ge=0)
    mcp_requests: int | None = Field(default=None, ge=0)
    mcp_request_status: Literal["available", "unavailable"] = "unavailable"


class EmailPreview(Output):
    subject: str
    sender_name: str
    recipient_display_name: str
    recipient_email: str
    heading: str
    paragraphs: list[str]
    action_label: str
    footer: str
    product_name: str
    accent_color: str
    branding: BrandingValues
    rendered_html: str = ""
    rendered_text: str = ""
    usage_summary: CommunicationUsageSummary | None = None
    activity_summary: ActivitySummary | None = None
    organization_name: str = ""
    workspace_name: str | None = None
    effective_locale: str = "en-US"
    locale_origin: Literal["user", "organization", "installation", "default"] = "default"
    powered_by: Literal["Powered by koinon"] = "Powered by koinon"
    copyright: str = Field(default_factory=lambda: f"© {datetime.now(UTC).year} Firefly Software Foundation")


class NotificationTarget(Output):
    kind: Literal["invitation", "workspace", "access", "none"]
    id: str | None = None


class NotificationDetails(Output):
    label: str | None = None
    scopes: list[str] = Field(default_factory=list)
    expires_at: datetime | None = None


class OwnNotification(Output):
    workspace_name: str | None = None
    actor_name: str | None = None
    details: NotificationDetails | None = None
    id: str
    kind: EventKind
    title: str
    body: str
    created_at: datetime
    read_at: datetime | None
    tenant_id: str
    organization_name: str
    target: NotificationTarget
    effective_locale: str = "en-US"
    locale_origin: Literal["user", "organization", "installation", "default"] = "default"
    powered_by: Literal["Powered by koinon"] = "Powered by koinon"
    copyright: str = Field(default_factory=lambda: f"© {datetime.now(UTC).year} Firefly Software Foundation")


class OwnNotificationPage(Output):
    items: list[OwnNotification]
    total: int
    page: int
    page_size: int
    pages: int


class NotificationUnreadCount(Output):
    unread: int


class NotificationPreferenceRule(Output):
    kind: EventKind
    required: bool
    inbox: bool
    email: bool
    email_available: bool


class NotificationPreferenceRuleInput(Input):
    kind: EventKind
    inbox: bool
    email: bool


class DigestSchedule(Input):
    local_time: str = Field(default="09:00", pattern=r"^(?:[01][0-9]|2[0-3]):[0-5][0-9]$", strict=True)
    weekday: int = Field(default=0, ge=0, le=6, strict=True)
    day_of_month: int = Field(default=1, ge=1, le=31, strict=True)


class AdministrativeSummarySchedule(Input):
    cadence: Literal["daily", "weekly", "monthly"]
    schedule: DigestSchedule = Field(default_factory=DigestSchedule)


class DigestSchedulePreview(Output):
    digest: DigestFrequency
    schedule: DigestSchedule
    time_zone: str
    next_run_at: datetime | None
    next_run_local: str | None
    window_start: datetime | None
    window_end: datetime | None
    dst_policy: Literal["first_valid_minute_earlier_fold"] = "first_valid_minute_earlier_fold"
    effective_locale: str = "en-US"
    locale_origin: Literal["user", "organization", "installation", "default"] = "default"


class NotificationPreferences(Output):
    admin_summaries_available: bool = False
    admin_summaries_enabled: bool = False
    revision: int
    rules: list[NotificationPreferenceRule]
    digest: DigestFrequency
    allowed_digests: list[DigestFrequency]
    locale: str
    time_zone: str
    schedule: DigestSchedule = Field(default_factory=DigestSchedule)
    next_run_at: datetime | None = None
    next_run_local: str | None = None
    admin_summaries: bool | None = None
    notification_locale: str | None = None
    effective_locale: str = "en-US"
    locale_origin: Literal["user", "organization", "installation", "default"] = "default"


class NotificationPreferencesInput(Input):
    expected_revision: int = Field(ge=0)
    rules: list[NotificationPreferenceRuleInput] = Field(max_length=7)
    digest: DigestFrequency
    schedule: DigestSchedule = Field(default_factory=DigestSchedule)
    admin_summaries: bool | None = None
    notification_locale: str | None = None

    @field_validator("notification_locale")
    @classmethod
    def valid_locale(cls, value):
        return normalize_locale(value) if value is not None else None


class CommunicationPolicy(Output):
    revision: int
    sender_id: str | None
    rules: list[NotificationPreferenceRule]
    digest_enabled: bool
    can_update: bool
    allowed_digests: list[DigestFrequency] = Field(default_factory=lambda: ["off"])
    default_digest: DigestFrequency = "off"
    default_schedule: DigestSchedule = Field(default_factory=DigestSchedule)
    admin_summaries: list[AdministrativeSummarySchedule] = Field(default_factory=list, max_length=3)
    default_locale: str | None = None


class CommunicationPolicyInput(Input):
    expected_revision: int = Field(ge=0)
    sender_id: str | None = Field(default=None, max_length=64)
    rules: list[NotificationPreferenceRuleInput] = Field(max_length=7)
    digest_enabled: bool = False
    allowed_digests: list[DigestFrequency] = Field(default_factory=lambda: ["off"])
    default_digest: DigestFrequency = "off"
    default_schedule: DigestSchedule = Field(default_factory=DigestSchedule)
    admin_summaries: list[AdministrativeSummarySchedule] = Field(default_factory=list, max_length=3)
    default_locale: str | None = None

    @field_validator("default_locale")
    @classmethod
    def valid_locale(cls, value):
        return normalize_locale(value) if value is not None else None


class VerifiedSenderOption(Output):
    id: str
    display_name: str
    address: str


class CommunicationIssue(Output):
    code: str
    explanation: str


class CommunicationCapabilities(Output):
    state: Literal["disabled", "not_configured", "ready", "degraded"]
    provider_label: str
    sender_name: str
    sender_address: str
    reply_to: str | None = None
    sender_options: list[VerifiedSenderOption]
    public_address_configured: bool
    public_url: str | None
    acceptance_base: str | None
    issues: list[CommunicationIssue]
    effective_locale: str = "en-US"
    locale_origin: Literal["user", "organization", "installation", "default"] = "default"


class DeliveryRecord(Output):
    id: str
    kind: EventKind
    channel: Literal["email"] = "email"
    invitation_id: str | None
    membership_id: str | None
    recipient_display: str
    scope_name: str
    status: DeliveryStatus
    created_at: datetime
    last_attempt_at: datetime | None
    next_attempt_at: datetime | None
    attempt_count: int
    failure_code: str | None
    safe_explanation: str | None
    can_retry: bool


class DeliveryPage(Output):
    items: list[DeliveryRecord]
    total: int
    page: int
    page_size: int
    pages: int


class ActivityEmailPreviewInput(Input):
    tenant_id: str = Field(min_length=1, max_length=64)
    preferences: NotificationPreferencesInput
    window: ActivityWindow
