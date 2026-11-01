# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Durable communication references; delivery bodies use separate encrypted envelopes."""

from datetime import datetime

from pyfly.data.relational.sqlalchemy import Base, UtcDateTime
from sqlalchemy import DDL, JSON, CheckConstraint, ForeignKey, Index, String, Text, UniqueConstraint, event
from sqlalchemy.orm import Mapped, mapped_column

from koinon.catalog.entities import CatalogEntry, Membership, Tenant
from koinon.corporate_identity.entities import CorporateProvider


class EmailInvitationRecord(Base):
    __tablename__ = "koinon_email_invitations"
    __table_args__ = (
        UniqueConstraint("tenant_id", "request_key", name="uq_email_invitation_request"),
        CheckConstraint("send_count >= 1 AND send_count <= 10", name="ck_email_invitation_sends"),
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey(Tenant.id), index=True)
    workspace_id: Mapped[str | None] = mapped_column(ForeignKey(CatalogEntry.id), nullable=True)
    role: Mapped[str] = mapped_column(String(32))
    provider_id: Mapped[str] = mapped_column(ForeignKey(CorporateProvider.id))
    provider_revision: Mapped[int] = mapped_column()
    external_subject: Mapped[str] = mapped_column(String(512))
    recipient_ciphertext: Mapped[str] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(String(512))
    origin_token_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    request_key: Mapped[str] = mapped_column(String(64))
    request_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(UtcDateTime())
    expires_at: Mapped[datetime] = mapped_column(UtcDateTime(), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)
    accepted_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)
    declined_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)
    accepted_by: Mapped[str | None] = mapped_column(String(512), nullable=True)
    membership_id: Mapped[str | None] = mapped_column(ForeignKey(Membership.id), nullable=True)
    send_count: Mapped[int] = mapped_column(default=1)
    last_queued_at: Mapped[datetime] = mapped_column(UtcDateTime())
    delivery_id: Mapped[str] = mapped_column(String(64))


class RecipientIdentityRecord(Base):
    __tablename__ = "koinon_communication_identities"
    __table_args__ = (
        UniqueConstraint("tenant_id", "provider_id", "external_subject", name="uq_communication_external"),
        UniqueConstraint("tenant_id", "provider_id", "subject", name="uq_communication_subject"),
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey(Tenant.id), index=True)
    provider_id: Mapped[str] = mapped_column(ForeignKey(CorporateProvider.id))
    provider_revision: Mapped[int] = mapped_column()
    external_subject: Mapped[str] = mapped_column(String(512))
    subject: Mapped[str] = mapped_column(String(512), index=True)
    verified_at: Mapped[datetime] = mapped_column(UtcDateTime())


class OutboxRecord(Base):
    __tablename__ = "koinon_communication_outbox"
    __table_args__ = (
        UniqueConstraint("dedupe_key", name="uq_communication_delivery_key"),
        CheckConstraint("generation >= 0 AND attempt_count >= 0", name="ck_communication_attempt"),
        CheckConstraint(
            "status IN ('queued','preparing','sending','sent','delivered',"
            "'deferred','failed','suppressed','cancelled','unknown')",
            name="ck_communication_status",
        ),
        Index("ix_communication_ready", "status", "next_attempt_at"),
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    dedupe_key: Mapped[str] = mapped_column(String(128))
    tenant_id: Mapped[str] = mapped_column(ForeignKey(Tenant.id), index=True)
    workspace_id: Mapped[str | None] = mapped_column(ForeignKey(CatalogEntry.id), nullable=True)
    owner_subject: Mapped[str | None] = mapped_column(String(512), nullable=True, index=True)
    kind: Mapped[str] = mapped_column(String(32))
    invitation_id: Mapped[str | None] = mapped_column(ForeignKey(EmailInvitationRecord.id), nullable=True)
    membership_id: Mapped[str | None] = mapped_column(ForeignKey(Membership.id), nullable=True)
    event_json: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(24), default="queued")
    created_at: Mapped[datetime] = mapped_column(UtcDateTime())
    next_attempt_at: Mapped[datetime] = mapped_column(UtcDateTime())
    last_attempt_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)
    attempt_count: Mapped[int] = mapped_column(default=0)
    generation: Mapped[int] = mapped_column(default=0)
    lease_owner: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lease_until: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)
    payload_ciphertext: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    provider_reference: Mapped[str | None] = mapped_column(String(512), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)


class NotificationRecord(Base):
    __tablename__ = "koinon_notifications"
    __table_args__ = (UniqueConstraint("event_id", "owner_subject", name="uq_notification_event_owner"),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    event_id: Mapped[str] = mapped_column(ForeignKey(OutboxRecord.id))
    owner_subject: Mapped[str] = mapped_column(String(512), index=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey(Tenant.id), index=True)
    kind: Mapped[str] = mapped_column(String(32))
    organization_name: Mapped[str] = mapped_column(String(255))
    workspace_id: Mapped[str | None] = mapped_column(ForeignKey(CatalogEntry.id), nullable=True)
    membership_id: Mapped[str | None] = mapped_column(ForeignKey(Membership.id), nullable=True)
    invitation_id: Mapped[str | None] = mapped_column(ForeignKey(EmailInvitationRecord.id), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime())
    read_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)


class NotificationPreferenceRecord(Base):
    __tablename__ = "koinon_notification_preferences"
    subject: Mapped[str] = mapped_column(String(512), primary_key=True)
    revision: Mapped[int] = mapped_column(default=1)
    rules_json: Mapped[list] = mapped_column(JSON, default=list)
    digest: Mapped[str] = mapped_column(String(16), default="off")
    digest_cursor: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)
    admin_summaries: Mapped[bool | None] = mapped_column(nullable=True)
    notification_locale: Mapped[str | None] = mapped_column(String(64), nullable=True)
    schedule_json: Mapped[dict] = mapped_column(JSON, default=dict)
    next_due_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True, index=True)
    time_zone_snapshot: Mapped[str] = mapped_column(String(64), default="UTC")


class CommunicationPolicyRecord(Base):
    __tablename__ = "koinon_communication_policies"
    tenant_id: Mapped[str] = mapped_column(ForeignKey(Tenant.id), primary_key=True)
    revision: Mapped[int] = mapped_column(default=1)
    sender_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    rules_json: Mapped[list] = mapped_column(JSON, default=list)
    digest_enabled: Mapped[bool] = mapped_column(default=False)
    allowed_digests_json: Mapped[list] = mapped_column(JSON, default=lambda: ["off"])
    default_digest: Mapped[str] = mapped_column(String(16), default="off")
    default_schedule_json: Mapped[dict] = mapped_column(JSON, default=dict)
    admin_summaries_json: Mapped[list] = mapped_column(JSON, default=list)
    default_locale: Mapped[str | None] = mapped_column(String(64), nullable=True)


class InstallationRecord(Base):
    __tablename__ = "koinon_installation_identity"
    __table_args__ = (CheckConstraint("singleton = 'installation'", name="ck_installation_singleton"),)
    singleton: Mapped[str] = mapped_column(String(16), primary_key=True)
    installation_id: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime())


def _installation_identity_guards() -> None:
    table = InstallationRecord.__table__
    for operation in ("UPDATE", "DELETE"):
        event.listen(
            table,
            "after_create",
            DDL(
                f"CREATE TRIGGER koinon_installation_identity_{operation.lower()} "
                f"BEFORE {operation} ON koinon_installation_identity "
                "BEGIN SELECT RAISE(ABORT, 'Installation identity is immutable'); END"
            ).execute_if(dialect="sqlite"),
        )
    for statement in (
        "CREATE FUNCTION public.koinon_installation_identity_immutable() RETURNS trigger "
        "LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$ "
        "BEGIN RAISE EXCEPTION 'Installation identity is immutable' USING ERRCODE='23000'; END; $$",
        "CREATE TRIGGER koinon_installation_identity_rows BEFORE UPDATE OR DELETE "
        "ON public.koinon_installation_identity FOR EACH ROW "
        "EXECUTE FUNCTION public.koinon_installation_identity_immutable()",
        "CREATE TRIGGER koinon_installation_identity_truncate BEFORE TRUNCATE "
        "ON public.koinon_installation_identity FOR EACH STATEMENT "
        "EXECUTE FUNCTION public.koinon_installation_identity_immutable()",
    ):
        event.listen(table, "after_create", DDL(statement).execute_if(dialect="postgresql"))


_installation_identity_guards()


class WelcomeAdmissionRecord(Base):
    __tablename__ = "koinon_welcome_admissions"
    __table_args__ = (
        UniqueConstraint("installation_id", "owner_subject", name="uq_welcome_installation_subject"),
        UniqueConstraint(
            "installation_id", "immutable_identity_sha256", name="uq_welcome_installation_identity"
        ),
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    installation_id: Mapped[str] = mapped_column(ForeignKey(InstallationRecord.installation_id))
    owner_subject: Mapped[str] = mapped_column(String(512))
    tenant_id: Mapped[str] = mapped_column(ForeignKey(Tenant.id))
    immutable_identity_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    event_id: Mapped[str] = mapped_column(ForeignKey(OutboxRecord.id))
    created_at: Mapped[datetime] = mapped_column(UtcDateTime())


class BootstrapContactRecord(Base):
    __tablename__ = "koinon_bootstrap_contacts"
    __table_args__ = (
        UniqueConstraint("installation_id", "identity_sha256", name="uq_bootstrap_contact_identity"),
        UniqueConstraint("grant_id", name="uq_bootstrap_contact_grant"),
        UniqueConstraint("event_id", name="uq_bootstrap_contact_event"),
        CheckConstraint("expires_at > observed_at", name="ck_bootstrap_contact_expiry"),
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    installation_id: Mapped[str] = mapped_column(ForeignKey(InstallationRecord.installation_id))
    grant_id: Mapped[str] = mapped_column(ForeignKey("koinon_bootstrap_identity_grants.id"))
    identity_sha256: Mapped[str] = mapped_column(String(64))
    event_id: Mapped[str] = mapped_column(ForeignKey(OutboxRecord.id))
    contact_ciphertext: Mapped[str] = mapped_column(Text)
    observed_at: Mapped[datetime] = mapped_column(UtcDateTime())
    expires_at: Mapped[datetime] = mapped_column(UtcDateTime())
    canonical_subject: Mapped[str | None] = mapped_column(String(512), nullable=True, index=True)


def _bootstrap_contact_guards():
    from koinon.communications.bootstrap_guards import contact_guards

    for dialect in ("sqlite", "postgresql"):
        for statement in contact_guards(dialect):
            event.listen(
                BootstrapContactRecord.__table__, "after_create", DDL(statement).execute_if(dialect=dialect)
            )


_bootstrap_contact_guards()


class DigestSubscriptionRecord(Base):
    __tablename__ = "koinon_digest_subscriptions"
    __table_args__ = (
        UniqueConstraint("owner_subject", "tenant_id", "audience", "cadence", name="uq_digest_subscription"),
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    owner_subject: Mapped[str] = mapped_column(String(512), index=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey(Tenant.id))
    audience: Mapped[str] = mapped_column(String(32))
    cadence: Mapped[str] = mapped_column(String(16))
    schedule_json: Mapped[dict] = mapped_column(JSON)
    time_zone: Mapped[str] = mapped_column(String(64))
    revision: Mapped[int] = mapped_column(default=1)
    source_revision: Mapped[str] = mapped_column(String(128))
    enabled: Mapped[bool] = mapped_column(default=True)
    cursor_at: Mapped[datetime] = mapped_column(UtcDateTime())
    next_due_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True, index=True)
