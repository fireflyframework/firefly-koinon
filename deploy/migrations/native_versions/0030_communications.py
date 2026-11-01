# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Recipient-bound invitations, native notification outbox and durable calendar admissions."""

import sqlalchemy as sa
from alembic import op
from pyfly.data.relational.sqlalchemy import UtcDateTime

revision = "koinon_0030_comms"
down_revision = "koinon_0029_bulk_staging"
branch_labels = None
depends_on = None


def install_installation_guards():
    if op.get_bind().dialect.name == "sqlite":
        for operation in ("UPDATE", "DELETE"):
            op.execute(
                sa.text(
                    f"CREATE TRIGGER koinon_installation_identity_{operation.lower()} "
                    f"BEFORE {operation} ON koinon_installation_identity "
                    "BEGIN SELECT RAISE(ABORT, 'Installation identity is immutable'); END"
                )
            )
    elif op.get_bind().dialect.name == "postgresql":
        for statement in (
            (
                "CREATE FUNCTION public.koinon_installation_identity_immutable() RETURNS trigger "
                "LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$ "
                "BEGIN RAISE EXCEPTION 'Installation identity is immutable' USING ERRCODE='23000'; END; $$"
            ),
            (
                "CREATE TRIGGER koinon_installation_identity_rows BEFORE UPDATE OR DELETE "
                "ON public.koinon_installation_identity FOR EACH ROW "
                "EXECUTE FUNCTION public.koinon_installation_identity_immutable()"
            ),
            (
                "CREATE TRIGGER koinon_installation_identity_truncate BEFORE TRUNCATE "
                "ON public.koinon_installation_identity FOR EACH STATEMENT "
                "EXECUTE FUNCTION public.koinon_installation_identity_immutable()"
            ),
        ):
            op.execute(sa.text(statement))
    else:
        raise RuntimeError("Installation identity guards require PostgreSQL or SQLite")


def upgrade():
    op.create_table(
        "koinon_email_invitations",
        sa.Column("id", sa.String(64), nullable=False, primary_key=True),
        sa.Column("tenant_id", sa.String(64), sa.ForeignKey("lattice_tenants.id"), nullable=False),
        sa.Column("workspace_id", sa.String(64), sa.ForeignKey("lattice_catalog.id"), nullable=True),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column(
            "provider_id", sa.String(64), sa.ForeignKey("koinon_identity_providers.id"), nullable=False
        ),
        sa.Column("provider_revision", sa.Integer(), nullable=False),
        sa.Column("external_subject", sa.String(512), nullable=False),
        sa.Column("recipient_ciphertext", sa.Text(), nullable=False),
        sa.Column("created_by", sa.String(512), nullable=False),
        sa.Column("origin_token_id", sa.String(64), nullable=True),
        sa.Column("request_key", sa.String(64), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("created_at", UtcDateTime(), nullable=False),
        sa.Column("expires_at", UtcDateTime(), nullable=False),
        sa.Column("revoked_at", UtcDateTime(), nullable=True),
        sa.Column("accepted_at", UtcDateTime(), nullable=True),
        sa.Column("declined_at", UtcDateTime(), nullable=True),
        sa.Column("accepted_by", sa.String(512), nullable=True),
        sa.Column("membership_id", sa.String(64), sa.ForeignKey("lattice_memberships.id"), nullable=True),
        sa.Column("send_count", sa.Integer(), nullable=False),
        sa.Column("last_queued_at", UtcDateTime(), nullable=False),
        sa.Column("delivery_id", sa.String(64), nullable=False),
        sa.CheckConstraint("send_count >= 1 AND send_count <= 10", name="ck_email_invitation_sends"),
        sa.UniqueConstraint("tenant_id", "request_key", name="uq_email_invitation_request"),
    )
    op.create_index(
        "ix_koinon_email_invitations_expires_at", "koinon_email_invitations", ["expires_at"], unique=False
    )
    op.create_index(
        "ix_koinon_email_invitations_tenant_id", "koinon_email_invitations", ["tenant_id"], unique=False
    )
    op.create_table(
        "koinon_communication_identities",
        sa.Column("id", sa.String(64), nullable=False, primary_key=True),
        sa.Column("tenant_id", sa.String(64), sa.ForeignKey("lattice_tenants.id"), nullable=False),
        sa.Column(
            "provider_id", sa.String(64), sa.ForeignKey("koinon_identity_providers.id"), nullable=False
        ),
        sa.Column("provider_revision", sa.Integer(), nullable=False),
        sa.Column("external_subject", sa.String(512), nullable=False),
        sa.Column("subject", sa.String(512), nullable=False),
        sa.Column("verified_at", UtcDateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", "provider_id", "external_subject", name="uq_communication_external"),
        sa.UniqueConstraint("tenant_id", "provider_id", "subject", name="uq_communication_subject"),
    )
    op.create_index(
        "ix_koinon_communication_identities_subject",
        "koinon_communication_identities",
        ["subject"],
        unique=False,
    )
    op.create_index(
        "ix_koinon_communication_identities_tenant_id",
        "koinon_communication_identities",
        ["tenant_id"],
        unique=False,
    )
    op.create_table(
        "koinon_communication_outbox",
        sa.Column("id", sa.String(64), nullable=False, primary_key=True),
        sa.Column("dedupe_key", sa.String(128), nullable=False),
        sa.Column("tenant_id", sa.String(64), sa.ForeignKey("lattice_tenants.id"), nullable=False),
        sa.Column("workspace_id", sa.String(64), sa.ForeignKey("lattice_catalog.id"), nullable=True),
        sa.Column("owner_subject", sa.String(512), nullable=True),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column(
            "invitation_id", sa.String(64), sa.ForeignKey("koinon_email_invitations.id"), nullable=True
        ),
        sa.Column("membership_id", sa.String(64), sa.ForeignKey("lattice_memberships.id"), nullable=True),
        sa.Column("event_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("created_at", UtcDateTime(), nullable=False),
        sa.Column("next_attempt_at", UtcDateTime(), nullable=False),
        sa.Column("last_attempt_at", UtcDateTime(), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("lease_owner", sa.String(64), nullable=True),
        sa.Column("lease_until", UtcDateTime(), nullable=True),
        sa.Column("payload_ciphertext", sa.Text(), nullable=True),
        sa.Column("payload_hash", sa.String(64), nullable=True),
        sa.Column("failure_code", sa.String(64), nullable=True),
        sa.Column("provider_reference", sa.String(512), nullable=True),
        sa.Column("completed_at", UtcDateTime(), nullable=True),
        sa.CheckConstraint("generation >= 0 AND attempt_count >= 0", name="ck_communication_attempt"),
        sa.CheckConstraint(
            "status IN ('queued','preparing','sending','sent','delivered',"
            "'deferred','failed','suppressed','cancelled','unknown')",
            name="ck_communication_status",
        ),
        sa.UniqueConstraint("dedupe_key", name="uq_communication_delivery_key"),
    )
    op.create_index(
        "ix_communication_ready", "koinon_communication_outbox", ["status", "next_attempt_at"], unique=False
    )
    op.create_index(
        "ix_koinon_communication_outbox_owner_subject",
        "koinon_communication_outbox",
        ["owner_subject"],
        unique=False,
    )
    op.create_index(
        "ix_koinon_communication_outbox_tenant_id", "koinon_communication_outbox", ["tenant_id"], unique=False
    )
    op.create_table(
        "koinon_notifications",
        sa.Column("id", sa.String(64), nullable=False, primary_key=True),
        sa.Column("event_id", sa.String(64), sa.ForeignKey("koinon_communication_outbox.id"), nullable=False),
        sa.Column("owner_subject", sa.String(512), nullable=False),
        sa.Column("tenant_id", sa.String(64), sa.ForeignKey("lattice_tenants.id"), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("organization_name", sa.String(255), nullable=False),
        sa.Column("workspace_id", sa.String(64), sa.ForeignKey("lattice_catalog.id"), nullable=True),
        sa.Column("membership_id", sa.String(64), sa.ForeignKey("lattice_memberships.id"), nullable=True),
        sa.Column(
            "invitation_id", sa.String(64), sa.ForeignKey("koinon_email_invitations.id"), nullable=True
        ),
        sa.Column("created_at", UtcDateTime(), nullable=False),
        sa.Column("read_at", UtcDateTime(), nullable=True),
        sa.UniqueConstraint("event_id", "owner_subject", name="uq_notification_event_owner"),
    )
    op.create_index(
        "ix_koinon_notifications_owner_subject", "koinon_notifications", ["owner_subject"], unique=False
    )
    op.create_index("ix_koinon_notifications_tenant_id", "koinon_notifications", ["tenant_id"], unique=False)
    op.create_table(
        "koinon_notification_preferences",
        sa.Column("subject", sa.String(512), nullable=False, primary_key=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("rules_json", sa.JSON(), nullable=False),
        sa.Column("digest", sa.String(16), nullable=False),
        sa.Column("digest_cursor", UtcDateTime(), nullable=True),
        sa.Column("admin_summaries", sa.Boolean(), nullable=True),
        sa.Column("notification_locale", sa.String(64), nullable=True),
        sa.Column("schedule_json", sa.JSON(), nullable=False),
        sa.Column("next_due_at", UtcDateTime(), nullable=True),
        sa.Column("time_zone_snapshot", sa.String(64), nullable=False),
    )
    op.create_index(
        "ix_koinon_notification_preferences_next_due_at",
        "koinon_notification_preferences",
        ["next_due_at"],
        unique=False,
    )
    op.create_table(
        "koinon_communication_policies",
        sa.Column(
            "tenant_id", sa.String(64), sa.ForeignKey("lattice_tenants.id"), nullable=False, primary_key=True
        ),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("sender_id", sa.String(64), nullable=True),
        sa.Column("rules_json", sa.JSON(), nullable=False),
        sa.Column("digest_enabled", sa.Boolean(), nullable=False),
        sa.Column("allowed_digests_json", sa.JSON(), nullable=False),
        sa.Column("default_digest", sa.String(16), nullable=False),
        sa.Column("default_schedule_json", sa.JSON(), nullable=False),
        sa.Column("admin_summaries_json", sa.JSON(), nullable=False),
        sa.Column("default_locale", sa.String(64), nullable=True),
    )
    op.create_table(
        "koinon_installation_identity",
        sa.Column("singleton", sa.String(16), nullable=False, primary_key=True),
        sa.CheckConstraint("singleton = 'installation'", name="ck_installation_singleton"),
        sa.Column("installation_id", sa.String(64), nullable=False),
        sa.Column("created_at", UtcDateTime(), nullable=False),
        sa.UniqueConstraint("installation_id", name="uq_koinon_installation_identity_installation_id"),
    )
    install_installation_guards()
    op.create_table(
        "koinon_welcome_admissions",
        sa.Column("id", sa.String(64), nullable=False, primary_key=True),
        sa.Column(
            "installation_id",
            sa.String(64),
            sa.ForeignKey("koinon_installation_identity.installation_id"),
            nullable=False,
        ),
        sa.Column("owner_subject", sa.String(512), nullable=False),
        sa.Column("tenant_id", sa.String(64), sa.ForeignKey("lattice_tenants.id"), nullable=False),
        sa.Column("immutable_identity_sha256", sa.String(64), nullable=True),
        sa.Column("event_id", sa.String(64), sa.ForeignKey("koinon_communication_outbox.id"), nullable=False),
        sa.Column("created_at", UtcDateTime(), nullable=False),
        sa.UniqueConstraint(
            "installation_id", "immutable_identity_sha256", name="uq_welcome_installation_identity"
        ),
        sa.UniqueConstraint("installation_id", "owner_subject", name="uq_welcome_installation_subject"),
    )
    op.create_table(
        "koinon_digest_subscriptions",
        sa.Column("id", sa.String(64), nullable=False, primary_key=True),
        sa.Column("owner_subject", sa.String(512), nullable=False),
        sa.Column("tenant_id", sa.String(64), sa.ForeignKey("lattice_tenants.id"), nullable=False),
        sa.Column("audience", sa.String(32), nullable=False),
        sa.Column("cadence", sa.String(16), nullable=False),
        sa.Column("schedule_json", sa.JSON(), nullable=False),
        sa.Column("time_zone", sa.String(64), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("source_revision", sa.String(128), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("cursor_at", UtcDateTime(), nullable=False),
        sa.Column("next_due_at", UtcDateTime(), nullable=True),
        sa.UniqueConstraint(
            "owner_subject", "tenant_id", "audience", "cadence", name="uq_digest_subscription"
        ),
    )
    op.create_index(
        "ix_koinon_digest_subscriptions_next_due_at",
        "koinon_digest_subscriptions",
        ["next_due_at"],
        unique=False,
    )
    op.create_index(
        "ix_koinon_digest_subscriptions_owner_subject",
        "koinon_digest_subscriptions",
        ["owner_subject"],
        unique=False,
    )


def downgrade():
    raise RuntimeError("Use a reviewed backup/restore plan to retain invitations and delivery history")
