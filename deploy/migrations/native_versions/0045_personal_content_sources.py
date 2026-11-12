# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Persist personal source grants and immutable import origins; does not enable sync."""

import sqlalchemy as sa
from alembic import op
from pyfly.data.relational.sqlalchemy import UtcDateTime

revision = "koinon_0045_content_sources"
down_revision = "koinon_0044_knowledge_modes"
branch_labels = None
depends_on = None


def _text(name, size, *, nullable=False):
    return sa.Column(name, sa.String(size), nullable=nullable)


def _time(name, *, nullable=False):
    return sa.Column(name, UtcDateTime(), nullable=nullable)


def upgrade():
    op.create_table(
        "koinon_content_connections",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(64),
            sa.ForeignKey("lattice_tenants.id"),
            nullable=False,
        ),
        _text("owner", 512),
        _text("provider", 32),
        _text("status", 32),
        sa.Column("revision", sa.Integer(), nullable=False),
        _text("config_fingerprint", 64),
        _text("external_subject", 1024, nullable=True),
        _text("external_tenant", 1024, nullable=True),
        _text("issuer", 2048, nullable=True),
        sa.Column("scopes", sa.JSON(), nullable=False),
        sa.Column("secret_ciphertext", sa.LargeBinary(), nullable=True),
        _text("refresh_operation", 64, nullable=True),
        _time("refresh_expires_at", nullable=True),
        _time("created_at"),
        _time("updated_at"),
        sa.CheckConstraint(
            "provider in ('sharepoint','onedrive','google_drive')",
            name="ck_content_provider",
        ),
        sa.CheckConstraint(
            "status in ('pending','connected','reconnect_required','disconnected')",
            name="ck_content_status",
        ),
        sa.UniqueConstraint(
            "tenant_id", "owner", "id", name="uq_content_connection_tenant_owner"
        ),
    )
    op.create_index(
        "ix_content_connection_owner",
        "koinon_content_connections",
        ["tenant_id", "owner"],
    )
    op.create_index(
        "ix_koinon_content_connections_tenant_id",
        "koinon_content_connections",
        ["tenant_id"],
    )
    op.create_table(
        "koinon_content_authorizations",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "connection_id",
            sa.String(64),
            sa.ForeignKey("koinon_content_connections.id"),
            nullable=False,
        ),
        sa.Column(
            "tenant_id",
            sa.String(64),
            sa.ForeignKey("lattice_tenants.id"),
            nullable=False,
        ),
        _text("owner", 512),
        _text("session_hash", 64),
        _text("state_hash", 64),
        _text("config_fingerprint", 64),
        sa.Column("connection_revision", sa.Integer(), nullable=False),
        _text("status", 24),
        sa.Column("secret_ciphertext", sa.LargeBinary(), nullable=True),
        _time("expires_at"),
        _time("created_at"),
        sa.UniqueConstraint("state_hash"),
        sa.CheckConstraint(
            "status in ('pending','exchanging','completed')",
            name="ck_content_authorization_status",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "owner", "connection_id"],
            [
                "koinon_content_connections.tenant_id",
                "koinon_content_connections.owner",
                "koinon_content_connections.id",
            ],
            name="fk_content_authorization_owner",
        ),
    )
    for column in ("connection_id", "tenant_id", "expires_at"):
        op.create_index(
            "ix_koinon_content_authorizations_" + column,
            "koinon_content_authorizations",
            [column],
        )
    op.create_table(
        "koinon_content_mappings",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(64),
            sa.ForeignKey("lattice_tenants.id"),
            nullable=False,
        ),
        _text("owner", 512),
        sa.Column(
            "connection_id",
            sa.String(64),
            sa.ForeignKey("koinon_content_connections.id"),
            nullable=False,
        ),
        _text("provider", 32),
        _text("external_subject", 1024),
        _text("external_tenant", 1024, nullable=True),
        _text("issuer", 2048),
        _text("config_fingerprint", 64),
        _text("drive_id", 1024),
        _text("root_id", 1024),
        _text("workspace_id", 64),
        _text("project_id", 64),
        _text("parent_id", 64),
        sa.Column("request_json", sa.JSON(), nullable=False),
        _text("request_sha256", 64),
        _text("status", 32),
        sa.Column("revision", sa.Integer(), nullable=False),
        _time("reviewed_at"),
        _time("reviewed_expires_at", nullable=True),
        _time("created_at"),
        _time("updated_at"),
        sa.CheckConstraint(
            "revision BETWEEN 1 AND 2147483647", name="ck_content_mapping_revision"
        ),
        sa.CheckConstraint(
            "status in ('reviewed','active','paused','reconnect_required','retired')",
            name="ck_content_mapping_status",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_content_mapping_tenant"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "owner", "connection_id"],
            [
                "koinon_content_connections.tenant_id",
                "koinon_content_connections.owner",
                "koinon_content_connections.id",
            ],
            name="fk_content_mapping_owner",
        ),
    )
    op.create_index(
        "ix_content_mapping_owner",
        "koinon_content_mappings",
        ["tenant_id", "owner", "status"],
    )
    op.create_index(
        "ix_koinon_content_mappings_connection_id",
        "koinon_content_mappings",
        ["connection_id"],
    )
    op.create_index(
        "ix_content_mapping_candidates",
        "koinon_content_mappings",
        ["tenant_id", "provider", "id"],
    )
    op.create_table(
        "koinon_content_objects",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(64),
            sa.ForeignKey("lattice_tenants.id"),
            nullable=False,
        ),
        sa.Column(
            "mapping_id",
            sa.String(64),
            sa.ForeignKey("koinon_content_mappings.id"),
            nullable=False,
        ),
        _text("item_id", 1024),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("mapping_revision", sa.Integer(), nullable=False),
        _text("remote_version", 2048, nullable=True),
        _text("state", 32),
        _time("updated_at"),
        sa.UniqueConstraint(
            "tenant_id", "mapping_id", "item_id", name="uq_content_mapping_object"
        ),
        sa.CheckConstraint(
            "generation BETWEEN 1 AND 2147483647", name="ck_content_object_generation"
        ),
        sa.CheckConstraint(
            "mapping_revision BETWEEN 1 AND 2147483647",
            name="ck_content_object_mapping",
        ),
        sa.CheckConstraint(
            "state in ('pending','imported','failed','deleted','removed','excluded')",
            name="ck_content_object_state",
        ),
        sa.UniqueConstraint(
            "tenant_id", "mapping_id", "id", name="uq_content_object_tenant_mapping"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "mapping_id"],
            ["koinon_content_mappings.tenant_id", "koinon_content_mappings.id"],
            name="fk_content_object_tenant",
        ),
    )
    op.create_index(
        "ix_content_object_mapping", "koinon_content_objects", ["mapping_id"]
    )
    op.create_table(
        "koinon_content_imports",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(64),
            sa.ForeignKey("lattice_tenants.id"),
            nullable=False,
        ),
        sa.Column(
            "mapping_id",
            sa.String(64),
            sa.ForeignKey("koinon_content_mappings.id"),
            nullable=False,
        ),
        sa.Column("mapping_revision", sa.Integer(), nullable=False),
        sa.Column(
            "object_id",
            sa.String(64),
            sa.ForeignKey("koinon_content_objects.id"),
            nullable=False,
        ),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column(
            "intake_item_id",
            sa.String(64),
            sa.ForeignKey("koinon_bulk_items.id"),
            nullable=False,
        ),
        _text("provider", 32),
        _text("external_subject", 1024),
        _text("external_tenant", 1024, nullable=True),
        _text("drive_id", 1024),
        _text("remote_item_id", 1024),
        _text("remote_version", 2048),
        sa.Column(
            "source_id",
            sa.String(64),
            sa.ForeignKey("lattice_catalog.id"),
            nullable=False,
        ),
        sa.Column(
            "asset_id",
            sa.String(64),
            sa.ForeignKey("lattice_catalog.id"),
            nullable=False,
        ),
        _text("sha256", 64),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("receipt_json", sa.JSON(none_as_null=True), nullable=True),
        _time("created_at"),
        _time("committed_at", nullable=True),
        sa.UniqueConstraint(
            "tenant_id", "object_id", "generation", name="uq_content_import_generation"
        ),
        sa.UniqueConstraint("intake_item_id", name="uq_content_import_intake"),
        sa.CheckConstraint(
            "generation BETWEEN 1 AND 2147483647", name="ck_content_import_generation"
        ),
        sa.CheckConstraint(
            "(receipt_json IS NULL) = (committed_at IS NULL)",
            name="ck_content_import_receipt_time",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "mapping_id", "object_id"],
            [
                "koinon_content_objects.tenant_id",
                "koinon_content_objects.mapping_id",
                "koinon_content_objects.id",
            ],
            name="fk_content_import_origin",
        ),
    )
    for column in ("source_id", "asset_id"):
        op.create_index(
            "ix_koinon_content_imports_" + column, "koinon_content_imports", [column]
        )
    for column in ("mapping_id", "object_id"):
        op.create_index(
            "ix_content_import_" + column, "koinon_content_imports", [column]
        )
    if op.get_bind().dialect.name == "postgresql":
        op.execute("""
            CREATE FUNCTION koinon_preserve_content_import() RETURNS trigger
            LANGUAGE plpgsql AS $$
            BEGIN
                IF TG_OP <> 'UPDATE' THEN
                    RAISE EXCEPTION 'Source import origins are retained' USING ERRCODE='23514';
                END IF;
                IF (to_jsonb(NEW) - ARRAY['receipt_json','committed_at']) IS DISTINCT FROM
                   (to_jsonb(OLD) - ARRAY['receipt_json','committed_at']) OR
                   (OLD.receipt_json IS NOT NULL AND
                    (NEW.receipt_json::jsonb IS DISTINCT FROM OLD.receipt_json::jsonb OR
                     NEW.committed_at IS DISTINCT FROM OLD.committed_at)) THEN
                    RAISE EXCEPTION 'Source import origins and recorded receipts are immutable'
                        USING ERRCODE='23514';
                END IF;
                RETURN NEW;
            END $$
        """)
        op.execute("""
            CREATE TRIGGER koinon_content_import_update BEFORE UPDATE OR DELETE
            ON koinon_content_imports FOR EACH ROW EXECUTE FUNCTION koinon_preserve_content_import()
        """)
        op.execute("""
            CREATE TRIGGER koinon_content_import_truncate BEFORE TRUNCATE
            ON koinon_content_imports FOR EACH STATEMENT EXECUTE FUNCTION koinon_preserve_content_import()
        """)


def downgrade():
    raise RuntimeError(
        "Preserve delegated-source history; use a reviewed backup restore or forward migration"
    )
