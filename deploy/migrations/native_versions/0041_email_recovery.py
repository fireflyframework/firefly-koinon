# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Append-only explicit welcome recovery and provider operation observations."""
import sqlalchemy as sa
from alembic import op
from pyfly.data.relational.sqlalchemy import UtcDateTime

revision = "koinon_0041_email_recovery"
down_revision = "koinon_0040_bulk_pinned"
branch_labels = None
depends_on = None

def immutable_guards(table, dialect):
    if dialect not in {"sqlite", "postgresql"}:
        raise RuntimeError("Email recovery requires PostgreSQL or SQLite")
    if dialect == "sqlite":
        return tuple(
            f"CREATE TRIGGER {table}_no_{kind} BEFORE {kind.upper()} ON {table} "
            "BEGIN SELECT RAISE(ABORT,'Communication recovery evidence is immutable'); END"
            for kind in ("update", "delete")
        )
    return (
        f"CREATE FUNCTION public.{table}_guard() RETURNS trigger LANGUAGE plpgsql "
        "SECURITY INVOKER SET search_path=pg_catalog AS $$ BEGIN "
        "RAISE EXCEPTION 'Communication recovery evidence is immutable' USING ERRCODE='23000'; END; $$",
        f"CREATE TRIGGER {table}_rows BEFORE UPDATE OR DELETE ON public.{table} "
        f"FOR EACH ROW EXECUTE FUNCTION public.{table}_guard()",
        f"CREATE TRIGGER {table}_truncate BEFORE TRUNCATE ON public.{table} "
        f"FOR EACH STATEMENT EXECUTE FUNCTION public.{table}_guard()",
    )


def operator_insert_guard(table, predicate, dialect):
    if dialect != "postgresql":
        return ()
    return (
        f"CREATE FUNCTION public.{table}_operator_insert() RETURNS trigger LANGUAGE plpgsql "
        "SECURITY INVOKER SET search_path=pg_catalog AS $$ BEGIN "
        f"IF ({predicate}) AND NOT (has_table_privilege(current_user,"
        "'public.koinon_operator_delivery_contacts','INSERT') AND "
        "has_column_privilege(current_user,'public.koinon_operator_delivery_contacts','revision','UPDATE')) "
        "THEN RAISE EXCEPTION 'An operator delivery action requires the operator database capability' "
        "USING ERRCODE='42501'; END IF; RETURN NEW; END; $$",
        f"CREATE TRIGGER {table}_operator_admission BEFORE INSERT ON public.{table} "
        f"FOR EACH ROW EXECUTE FUNCTION public.{table}_operator_insert()",
    )


def upgrade():
    op.create_table('koinon_welcome_recoveries',
        sa.Column('id', sa.String(64), primary_key=True, nullable=False),
        sa.Column('tenant_id', sa.String(64), sa.ForeignKey('lattice_tenants.id'), nullable=False),
        sa.Column('original_delivery_id', sa.String(64), sa.ForeignKey('koinon_communication_outbox.id'), nullable=False),
        sa.Column('original_generation', sa.Integer(), nullable=False),
        sa.Column('delivery_id', sa.String(64), sa.ForeignKey('koinon_communication_outbox.id'), nullable=False),
        sa.Column('contact_id', sa.String(64), sa.ForeignKey('koinon_operator_delivery_contacts.id'), nullable=False),
        sa.Column('contact_revision', sa.Integer(), nullable=False),
        sa.Column('request_key', sa.String(64), nullable=False),
        sa.Column('request_hash', sa.String(64), nullable=False),
        sa.Column('authority_kind', sa.String(32), nullable=False),
        sa.Column('requested_by', sa.String(512), nullable=False),
        sa.Column('origin_token_id', sa.String(64), nullable=True),
        sa.Column('reason', sa.String(64), nullable=False),
        sa.Column('created_at', UtcDateTime(), nullable=False),
        sa.CheckConstraint("authority_kind IN ('administrator','operator')", name='ck_welcome_recovery_authority'),
        sa.CheckConstraint("reason='recipient_reported_not_received'", name='ck_welcome_recovery_reason'),
        sa.CheckConstraint('contact_revision>=1 AND original_generation>=0', name='ck_welcome_recovery_versions'),
        sa.UniqueConstraint('delivery_id', name='uq_welcome_recovery_delivery'),
        sa.UniqueConstraint('tenant_id', 'request_key', name='uq_welcome_recovery_request'),
    )
    op.create_index('ix_koinon_welcome_recoveries_original_delivery_id', 'koinon_welcome_recoveries', ['original_delivery_id'])
    op.create_index('ix_koinon_welcome_recoveries_tenant_id', 'koinon_welcome_recoveries', ['tenant_id'])
    op.create_table('koinon_email_provider_bindings',
        sa.Column('id', sa.String(64), sa.ForeignKey('koinon_communication_outbox.id'), primary_key=True, nullable=False),
        sa.Column('tenant_id', sa.String(64), sa.ForeignKey('lattice_tenants.id'), nullable=False),
        sa.Column('provider', sa.String(64), nullable=False),
        sa.Column('instance_sha256', sa.String(64), nullable=False),
        sa.Column('operation_id', sa.String(64), nullable=False),
        sa.Column('source', sa.String(32), nullable=False),
        sa.Column('evidence_sha256', sa.String(64), nullable=True),
        sa.Column('created_at', UtcDateTime(), nullable=False),
        sa.CheckConstraint("(source='dispatch' AND evidence_sha256 IS NULL) OR (source='operator_historical' AND evidence_sha256 IS NOT NULL AND length(evidence_sha256)=64)", name='ck_email_binding_source'),
    )
    op.create_index('ix_koinon_email_provider_bindings_tenant_id', 'koinon_email_provider_bindings', ['tenant_id'])
    op.create_table('koinon_email_operation_inspections',
        sa.Column('id', sa.String(64), primary_key=True, nullable=False),
        sa.Column('tenant_id', sa.String(64), sa.ForeignKey('lattice_tenants.id'), nullable=False),
        sa.Column('delivery_id', sa.String(64), sa.ForeignKey('koinon_email_provider_bindings.id'), nullable=False),
        sa.Column('generation', sa.Integer(), nullable=False),
        sa.Column('request_key', sa.String(64), nullable=False),
        sa.Column('request_hash', sa.String(64), nullable=False),
        sa.Column('requested_by', sa.String(512), nullable=False),
        sa.Column('authority_kind', sa.String(32), nullable=False),
        sa.Column('origin_token_id', sa.String(64), nullable=True),
        sa.Column('created_at', UtcDateTime(), nullable=False),
        sa.Column('lease_until', UtcDateTime(), nullable=False),
        sa.CheckConstraint("authority_kind IN ('administrator','operator')", name='ck_email_inspection_authority'),
        sa.CheckConstraint('generation>=0 AND lease_until>created_at', name='ck_email_inspection_lease'),
        sa.UniqueConstraint('tenant_id', 'request_key', name='uq_email_inspection_request'),
    )
    op.create_index('ix_koinon_email_operation_inspections_delivery_id', 'koinon_email_operation_inspections', ['delivery_id'])
    op.create_index('ix_koinon_email_operation_inspections_tenant_id', 'koinon_email_operation_inspections', ['tenant_id'])
    op.create_table('koinon_email_operation_observations',
        sa.Column('id', sa.String(64), sa.ForeignKey('koinon_email_operation_inspections.id'), primary_key=True, nullable=False),
        sa.Column('tenant_id', sa.String(64), sa.ForeignKey('lattice_tenants.id'), nullable=False),
        sa.Column('delivery_id', sa.String(64), sa.ForeignKey('koinon_communication_outbox.id'), nullable=False),
        sa.Column('operation_state', sa.String(32), nullable=False),
        sa.Column('reason_code', sa.String(64), nullable=True),
        sa.Column('checked_at', UtcDateTime(), nullable=False),
        sa.CheckConstraint("operation_state IN ('pending','accepted','rejected','unknown','unavailable')", name='ck_email_operation_state'),
    )
    op.create_index('ix_koinon_email_operation_observations_delivery_id', 'koinon_email_operation_observations', ['delivery_id'])
    op.create_index('ix_koinon_email_operation_observations_tenant_id', 'koinon_email_operation_observations', ['tenant_id'])
    dialect = op.get_bind().dialect.name
    for table, predicate in (
        ("koinon_welcome_recoveries", "NEW.authority_kind='operator'"),
        ("koinon_email_provider_bindings", "NEW.source='operator_historical'"),
        ("koinon_email_operation_inspections", "NEW.authority_kind='operator'"),
        ("koinon_email_operation_observations", None),
    ):
        statements = (*immutable_guards(table,dialect), *(operator_insert_guard(table,predicate,dialect) if predicate else ()))
        for statement in statements:
            op.execute(sa.text(statement))


def downgrade():
    raise RuntimeError("Email recovery evidence is retained; restore a verified backup instead")
