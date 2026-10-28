# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Initial native control-plane and pyfly framework schema, frozen at pyfly26.10.11."""

import pyfly.data.relational.framework_schema
import pyfly.data.relational.sqlalchemy.types
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mssql, mysql, postgresql

revision = "koinon_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():

    op.create_table(
        "lattice_jobs",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("resource_id", sa.String(length=64), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("error", sa.String(length=2000), nullable=True),
        sa.Column("worker_id", sa.String(length=128), nullable=True),
        sa.Column(
            "available_at",
            pyfly.data.relational.sqlalchemy.types.UtcDateTime(),
            nullable=False,
        ),
        sa.Column(
            "lease_until",
            pyfly.data.relational.sqlalchemy.types.UtcDateTime(),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            pyfly.data.relational.sqlalchemy.types.UtcDateTime(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            pyfly.data.relational.sqlalchemy.types.UtcDateTime(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_lattice_jobs")),
        sa.UniqueConstraint(
            "tenant_id", "idempotency_key", name="uq_lattice_job_idempotency"
        ),
    )
    op.create_index(
        "ix_lattice_claim",
        "lattice_jobs",
        ["status", "available_at", "lease_until"],
        unique=False,
    )
    op.create_index(
        op.f("ix_lattice_jobs_resource_id"),
        "lattice_jobs",
        ["resource_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_lattice_jobs_tenant_id"), "lattice_jobs", ["tenant_id"], unique=False
    )
    op.create_table(
        "lattice_tenants",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column(
            "created_at",
            pyfly.data.relational.sqlalchemy.types.UtcDateTime(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_lattice_tenants")),
    )
    op.create_table(
        "lattice_audit",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("subject", sa.String(length=512), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("resource_id", sa.String(length=64), nullable=True),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            pyfly.data.relational.sqlalchemy.types.UtcDateTime(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["lattice_tenants.id"],
            name=op.f("fk_lattice_audit_tenant_id_lattice_tenants"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_lattice_audit")),
    )
    op.create_index(
        op.f("ix_lattice_audit_tenant_id"), "lattice_audit", ["tenant_id"], unique=False
    )
    op.create_table(
        "lattice_catalog",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("workspace_id", sa.String(length=64), nullable=True),
        sa.Column("project_id", sa.String(length=64), nullable=True),
        sa.Column("parent_id", sa.String(length=64), nullable=True),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=4000), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(length=512), nullable=False),
        sa.Column(
            "created_at",
            pyfly.data.relational.sqlalchemy.types.UtcDateTime(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            pyfly.data.relational.sqlalchemy.types.UtcDateTime(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["parent_id"],
            ["lattice_catalog.id"],
            name=op.f("fk_lattice_catalog_parent_id_lattice_catalog"),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["lattice_tenants.id"],
            name=op.f("fk_lattice_catalog_tenant_id_lattice_tenants"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_lattice_catalog")),
    )
    op.create_index(
        op.f("ix_lattice_catalog_parent_id"),
        "lattice_catalog",
        ["parent_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_lattice_catalog_project_id"),
        "lattice_catalog",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_lattice_catalog_tenant_id"),
        "lattice_catalog",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_lattice_catalog_workspace_id"),
        "lattice_catalog",
        ["workspace_id"],
        unique=False,
    )
    op.create_index(
        "ix_lattice_scope_kind",
        "lattice_catalog",
        ["tenant_id", "workspace_id", "kind"],
        unique=False,
    )
    op.create_table(
        "lattice_memberships",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("subject", sa.String(length=512), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("workspace_id", sa.String(length=64), nullable=True),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            pyfly.data.relational.sqlalchemy.types.UtcDateTime(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["lattice_tenants.id"],
            name=op.f("fk_lattice_memberships_tenant_id_lattice_tenants"),
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["lattice_catalog.id"],
            name=op.f("fk_lattice_memberships_workspace_id_lattice_catalog"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_lattice_memberships")),
        sa.UniqueConstraint(
            "subject", "tenant_id", "workspace_id", name="uq_lattice_membership_scope"
        ),
    )
    op.create_index(
        op.f("ix_lattice_memberships_subject"),
        "lattice_memberships",
        ["subject"],
        unique=False,
    )
    op.create_index(
        op.f("ix_lattice_memberships_tenant_id"),
        "lattice_memberships",
        ["tenant_id"],
        unique=False,
    )
    op.create_table(
        "firefly_feature_flag_changes",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            sa.Identity(always=False),
            nullable=False,
        ),
        sa.Column(
            "flag_key",
            pyfly.data.relational.framework_schema.KeyString(length=128),
            nullable=False,
        ),
        sa.Column(
            "action",
            pyfly.data.relational.framework_schema.KeyString(length=16),
            nullable=False,
        ),
        sa.Column(
            "definition",
            sa.Text()
            .with_variant(mysql.LONGTEXT(), "mariadb")
            .with_variant(sa.NVARCHAR(), "mssql")
            .with_variant(mysql.LONGTEXT(), "mysql"),
            nullable=True,
        ),
        sa.Column(
            "previous",
            sa.Text()
            .with_variant(mysql.LONGTEXT(), "mariadb")
            .with_variant(sa.NVARCHAR(), "mssql")
            .with_variant(mysql.LONGTEXT(), "mysql"),
            nullable=True,
        ),
        sa.Column(
            "actor",
            pyfly.data.relational.framework_schema.KeyString(length=255),
            nullable=True,
        ),
        sa.Column(
            "changed_at",
            pyfly.data.relational.framework_schema.ZonelessUtcTimestamp(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        info={"pyfly_framework_table": "feature_flag_changes"},
    )
    op.create_index(
        "firefly_feature_flag_changes_key",
        "firefly_feature_flag_changes",
        ["flag_key", "id"],
        unique=False,
    )
    op.create_table(
        "firefly_feature_flags",
        sa.Column(
            "flag_key",
            pyfly.data.relational.framework_schema.KeyString(length=128),
            nullable=False,
        ),
        sa.Column(
            "definition",
            sa.Text()
            .with_variant(mysql.LONGTEXT(), "mariadb")
            .with_variant(sa.NVARCHAR(), "mssql")
            .with_variant(mysql.LONGTEXT(), "mysql"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "updated_at",
            pyfly.data.relational.framework_schema.ZonelessUtcTimestamp(),
            nullable=False,
        ),
        sa.Column(
            "updated_by",
            pyfly.data.relational.framework_schema.KeyString(length=255),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("flag_key"),
        info={"pyfly_framework_table": "feature_flags"},
    )
    op.create_table(
        "pyfly_agentic_memory",
        sa.Column(
            "namespace",
            pyfly.data.relational.framework_schema.KeyString(length=255),
            nullable=False,
        ),
        sa.Column(
            "entry_id",
            pyfly.data.relational.framework_schema.KeyString(length=255),
            nullable=False,
        ),
        sa.Column(
            "scope",
            pyfly.data.relational.framework_schema.KeyString(length=32),
            nullable=False,
        ),
        sa.Column(
            "key",
            pyfly.data.relational.framework_schema.KeyString(length=255),
            nullable=True,
        ),
        sa.Column(
            "content",
            sa.JSON().with_variant(
                postgresql.JSONB(astext_type=sa.Text()), "postgresql"
            ),
            nullable=False,
        ),
        sa.Column(
            "metadata",
            sa.JSON().with_variant(
                postgresql.JSONB(astext_type=sa.Text()), "postgresql"
            ),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            pyfly.data.relational.framework_schema.UtcTimestamp(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "expires_at",
            pyfly.data.relational.framework_schema.UtcTimestamp(timezone=True),
            nullable=True,
        ),
        sa.Column("importance", sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint("namespace", "entry_id"),
        info={"pyfly_framework_table": "agentic_memory"},
    )
    op.create_index(
        "pyfly_agentic_memory_expires",
        "pyfly_agentic_memory",
        ["expires_at"],
        unique=False,
    )
    op.create_index(
        "pyfly_agentic_memory_namespace_key",
        "pyfly_agentic_memory",
        ["namespace", "key", "created_at", "entry_id"],
        unique=False,
    )
    op.create_table(
        "pyfly_cache_entries",
        sa.Column(
            "cache_key",
            pyfly.data.relational.framework_schema.KeyString(length=512)
            .with_variant(sa.Text(), "postgresql")
            .with_variant(sa.Text(), "sqlite"),
            nullable=False,
        ),
        sa.Column(
            "value",
            sa.LargeBinary()
            .with_variant(mysql.LONGBLOB(), "mariadb")
            .with_variant(mssql.VARBINARY(), "mssql")
            .with_variant(mysql.LONGBLOB(), "mysql"),
            nullable=False,
        ),
        sa.Column(
            "expires_at",
            pyfly.data.relational.framework_schema.UtcTimestamp(timezone=True),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("cache_key"),
        info={"pyfly_framework_table": "cache_entries"},
    )
    op.create_index(
        op.f("ix_pyfly_cache_entries_expires_at"),
        "pyfly_cache_entries",
        ["expires_at"],
        unique=False,
    )
    op.create_table(
        "pyfly_event_store",
        sa.Column(
            "event_id",
            pyfly.data.relational.framework_schema.KeyString(length=64),
            nullable=False,
        ),
        sa.Column(
            "aggregate_id",
            pyfly.data.relational.framework_schema.KeyString(length=255),
            nullable=False,
        ),
        sa.Column(
            "aggregate_type",
            pyfly.data.relational.framework_schema.KeyString(length=255),
            nullable=False,
        ),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column(
            "event_type",
            pyfly.data.relational.framework_schema.KeyString(length=255),
            nullable=False,
        ),
        sa.Column(
            "payload",
            sa.Text()
            .with_variant(mysql.LONGTEXT(), "mariadb")
            .with_variant(sa.NVARCHAR(), "mssql")
            .with_variant(mysql.LONGTEXT(), "mysql"),
            nullable=False,
        ),
        sa.Column(
            "metadata",
            sa.Text()
            .with_variant(mysql.LONGTEXT(), "mariadb")
            .with_variant(sa.NVARCHAR(), "mssql")
            .with_variant(mysql.LONGTEXT(), "mysql"),
            nullable=False,
        ),
        sa.Column(
            "occurred_at",
            pyfly.data.relational.framework_schema.UtcTimestamp(timezone=True),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "tenant_id",
            pyfly.data.relational.framework_schema.KeyString(length=64),
            nullable=True,
        ),
        sa.Column(
            "recorded_at",
            pyfly.data.relational.framework_schema.UtcTimestamp(timezone=True),
            nullable=True,
        ),
        sa.Column("global_position", sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint("event_id"),
        sa.UniqueConstraint(
            "aggregate_id", "sequence", name=op.f("uq_pyfly_event_store_aggregate_id")
        ),
        info={"pyfly_framework_table": "event_store"},
    )
    op.create_index(
        op.f("ix_pyfly_event_store_global_position"),
        "pyfly_event_store",
        ["global_position"],
        unique=True,
        mssql_where=sa.text("global_position IS NOT NULL"),
    )
    op.create_table(
        "pyfly_event_store_head",
        sa.Column(
            "store",
            pyfly.data.relational.framework_schema.KeyString(length=255),
            nullable=False,
        ),
        sa.Column("position", sa.BigInteger(), nullable=False),
        sa.Column(
            "strategy",
            pyfly.data.relational.framework_schema.KeyString(length=32),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("store"),
        info={"pyfly_framework_table": "event_store_head"},
    )
    op.create_table(
        "pyfly_locks",
        sa.Column(
            "name",
            pyfly.data.relational.framework_schema.KeyString(length=255),
            nullable=False,
        ),
        sa.Column(
            "lock_until",
            pyfly.data.relational.framework_schema.UtcTimestamp(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "locked_at",
            pyfly.data.relational.framework_schema.UtcTimestamp(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "locked_by",
            pyfly.data.relational.framework_schema.KeyString(length=255),
            nullable=False,
        ),
        sa.Column("fence", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("name"),
        info={"pyfly_framework_table": "locks"},
    )
    op.create_table(
        "pyfly_oauth2_grants",
        sa.Column(
            "token_id",
            pyfly.data.relational.framework_schema.KeyString(length=255),
            nullable=False,
        ),
        sa.Column(
            "kind",
            pyfly.data.relational.framework_schema.KeyString(length=32),
            nullable=False,
        ),
        sa.Column(
            "client_id",
            pyfly.data.relational.framework_schema.KeyString(length=255),
            nullable=False,
        ),
        sa.Column(
            "family_id",
            pyfly.data.relational.framework_schema.KeyString(length=255),
            nullable=True,
        ),
        sa.Column("used", sa.Boolean(), nullable=False),
        sa.Column(
            "expires_at",
            pyfly.data.relational.framework_schema.UtcTimestamp(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "data",
            sa.Text()
            .with_variant(mysql.LONGTEXT(), "mariadb")
            .with_variant(sa.NVARCHAR(), "mssql")
            .with_variant(mysql.LONGTEXT(), "mysql"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("token_id"),
        info={"pyfly_framework_table": "oauth2_grants"},
    )
    op.create_index(
        op.f("ix_pyfly_oauth2_grants_expires_at"),
        "pyfly_oauth2_grants",
        ["expires_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_pyfly_oauth2_grants_family_id"),
        "pyfly_oauth2_grants",
        ["family_id", "kind"],
        unique=False,
    )
    op.create_table(
        "pyfly_oauth2_token_families",
        sa.Column(
            "family_id",
            pyfly.data.relational.framework_schema.KeyString(length=255),
            nullable=False,
        ),
        sa.Column(
            "client_id",
            pyfly.data.relational.framework_schema.KeyString(length=255),
            nullable=False,
        ),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column(
            "expires_at",
            pyfly.data.relational.framework_schema.UtcTimestamp(timezone=True),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("family_id"),
        info={"pyfly_framework_table": "oauth2_token_families"},
    )
    op.create_index(
        op.f("ix_pyfly_oauth2_token_families_expires_at"),
        "pyfly_oauth2_token_families",
        ["expires_at"],
        unique=False,
    )
    op.create_table(
        "pyfly_orchestration_state",
        sa.Column(
            "correlation_id",
            pyfly.data.relational.framework_schema.KeyString(length=255),
            nullable=False,
        ),
        sa.Column(
            "execution_name",
            pyfly.data.relational.framework_schema.KeyString(length=255),
            nullable=False,
        ),
        sa.Column(
            "pattern",
            pyfly.data.relational.framework_schema.KeyString(length=32),
            nullable=False,
        ),
        sa.Column(
            "status",
            pyfly.data.relational.framework_schema.KeyString(length=32),
            nullable=False,
        ),
        sa.Column(
            "started_at",
            pyfly.data.relational.framework_schema.UtcTimestamp(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            pyfly.data.relational.framework_schema.UtcTimestamp(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "completed_at",
            pyfly.data.relational.framework_schema.UtcTimestamp(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "payload",
            sa.Text()
            .with_variant(mysql.LONGTEXT(), "mariadb")
            .with_variant(sa.NVARCHAR(), "mssql")
            .with_variant(mysql.LONGTEXT(), "mysql"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("correlation_id"),
        info={"pyfly_framework_table": "orchestration_state"},
    )
    op.create_index(
        op.f("ix_pyfly_orchestration_state_status"),
        "pyfly_orchestration_state",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_pyfly_orchestration_state_updated_at"),
        "pyfly_orchestration_state",
        ["updated_at"],
        unique=False,
    )
    op.create_table(
        "pyfly_outbox_consumers",
        sa.Column(
            "consumer_group",
            pyfly.data.relational.framework_schema.KeyString(length=255),
            nullable=False,
        ),
        sa.Column(
            "destination",
            pyfly.data.relational.framework_schema.KeyString(length=255),
            nullable=False,
        ),
        sa.Column(
            "registered_at",
            pyfly.data.relational.framework_schema.UtcTimestamp(timezone=True),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("consumer_group", "destination"),
        info={"pyfly_framework_table": "outbox_consumers"},
    )
    op.create_table(
        "pyfly_outbox_dead_letters",
        sa.Column(
            "id",
            pyfly.data.relational.framework_schema.KeyString(length=64),
            nullable=False,
        ),
        sa.Column(
            "consumer_group",
            pyfly.data.relational.framework_schema.KeyString(length=255),
            nullable=True,
        ),
        sa.Column(
            "subscription",
            sa.Text()
            .with_variant(mysql.LONGTEXT(), "mariadb")
            .with_variant(sa.NVARCHAR(), "mssql")
            .with_variant(mysql.LONGTEXT(), "mysql"),
            nullable=True,
        ),
        sa.Column(
            "event_id",
            pyfly.data.relational.framework_schema.KeyString(length=64),
            nullable=False,
        ),
        sa.Column(
            "destination",
            pyfly.data.relational.framework_schema.KeyString(length=255),
            nullable=False,
        ),
        sa.Column(
            "event_type",
            pyfly.data.relational.framework_schema.KeyString(length=255),
            nullable=False,
        ),
        sa.Column(
            "payload",
            sa.Text()
            .with_variant(mysql.LONGTEXT(), "mariadb")
            .with_variant(sa.NVARCHAR(), "mssql")
            .with_variant(mysql.LONGTEXT(), "mysql"),
            nullable=False,
        ),
        sa.Column(
            "headers",
            sa.Text()
            .with_variant(mysql.LONGTEXT(), "mariadb")
            .with_variant(sa.NVARCHAR(), "mssql")
            .with_variant(mysql.LONGTEXT(), "mysql"),
            nullable=False,
        ),
        sa.Column(
            "occurred_at",
            pyfly.data.relational.framework_schema.UtcTimestamp(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "error_type",
            pyfly.data.relational.framework_schema.KeyString(length=255),
            nullable=False,
        ),
        sa.Column(
            "error_message",
            sa.Text()
            .with_variant(mysql.LONGTEXT(), "mariadb")
            .with_variant(sa.NVARCHAR(), "mssql")
            .with_variant(mysql.LONGTEXT(), "mysql"),
            nullable=False,
        ),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column(
            "failed_at",
            pyfly.data.relational.framework_schema.UtcTimestamp(timezone=True),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        info={"pyfly_framework_table": "outbox_dead_letters"},
    )
    op.create_index(
        op.f("ix_pyfly_outbox_dead_letters_consumer_group"),
        "pyfly_outbox_dead_letters",
        ["consumer_group"],
        unique=False,
    )
    op.create_index(
        op.f("ix_pyfly_outbox_dead_letters_failed_at"),
        "pyfly_outbox_dead_letters",
        ["failed_at"],
        unique=False,
    )
    op.create_table(
        "pyfly_outbox_deliveries",
        sa.Column(
            "consumer_group",
            pyfly.data.relational.framework_schema.KeyString(length=255),
            nullable=False,
        ),
        sa.Column("outbox_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "available_at",
            pyfly.data.relational.framework_schema.UtcTimestamp(timezone=True),
            nullable=False,
        ),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column(
            "claimed_by",
            pyfly.data.relational.framework_schema.KeyString(length=255),
            nullable=True,
        ),
        sa.Column(
            "done",
            sa.Text()
            .with_variant(mysql.LONGTEXT(), "mariadb")
            .with_variant(sa.NVARCHAR(), "mssql")
            .with_variant(mysql.LONGTEXT(), "mysql"),
            nullable=True,
        ),
        sa.Column(
            "last_error",
            sa.Text()
            .with_variant(mysql.LONGTEXT(), "mariadb")
            .with_variant(sa.NVARCHAR(), "mssql")
            .with_variant(mysql.LONGTEXT(), "mysql"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("consumer_group", "outbox_id"),
        info={"pyfly_framework_table": "outbox_deliveries"},
    )
    op.create_index(
        op.f("ix_pyfly_outbox_deliveries_consumer_group"),
        "pyfly_outbox_deliveries",
        ["consumer_group", "available_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_pyfly_outbox_deliveries_outbox_id"),
        "pyfly_outbox_deliveries",
        ["outbox_id"],
        unique=False,
    )
    op.create_table(
        "pyfly_outbox_events",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            sa.Identity(always=False),
            nullable=False,
        ),
        sa.Column(
            "event_id",
            pyfly.data.relational.framework_schema.KeyString(length=64),
            nullable=False,
        ),
        sa.Column(
            "destination",
            pyfly.data.relational.framework_schema.KeyString(length=255),
            nullable=False,
        ),
        sa.Column(
            "event_type",
            pyfly.data.relational.framework_schema.KeyString(length=255),
            nullable=False,
        ),
        sa.Column(
            "payload",
            sa.Text()
            .with_variant(mysql.LONGTEXT(), "mariadb")
            .with_variant(sa.NVARCHAR(), "mssql")
            .with_variant(mysql.LONGTEXT(), "mysql"),
            nullable=False,
        ),
        sa.Column(
            "headers",
            sa.Text()
            .with_variant(mysql.LONGTEXT(), "mariadb")
            .with_variant(sa.NVARCHAR(), "mssql")
            .with_variant(mysql.LONGTEXT(), "mysql"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            pyfly.data.relational.framework_schema.UtcTimestamp(timezone=True),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        info={"pyfly_framework_table": "outbox_events"},
    )
    op.create_index(
        op.f("ix_pyfly_outbox_events_created_at"),
        "pyfly_outbox_events",
        ["created_at"],
        unique=False,
    )
    op.create_table(
        "pyfly_projection_checkpoints",
        sa.Column(
            "projection",
            pyfly.data.relational.framework_schema.KeyString(length=255),
            nullable=False,
        ),
        sa.Column("position", sa.BigInteger(), nullable=False),
        sa.Column(
            "updated_at",
            pyfly.data.relational.framework_schema.UtcTimestamp(timezone=True),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("projection"),
        info={"pyfly_framework_table": "projection_checkpoints"},
    )
    op.create_table(
        "pyfly_session_principals",
        sa.Column(
            "principal",
            pyfly.data.relational.framework_schema.KeyString(length=255),
            nullable=False,
        ),
        sa.Column("version", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("principal"),
        info={"pyfly_framework_table": "session_principals"},
    )
    op.create_table(
        "pyfly_session_registrations",
        sa.Column(
            "session_id",
            pyfly.data.relational.framework_schema.KeyString(length=255),
            nullable=False,
        ),
        sa.Column(
            "principal",
            pyfly.data.relational.framework_schema.KeyString(length=255),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            pyfly.data.relational.framework_schema.UtcTimestamp(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "expires_at",
            pyfly.data.relational.framework_schema.UtcTimestamp(timezone=True),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("session_id"),
        info={"pyfly_framework_table": "session_registrations"},
    )
    op.create_index(
        op.f("ix_pyfly_session_registrations_expires_at"),
        "pyfly_session_registrations",
        ["expires_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_pyfly_session_registrations_principal"),
        "pyfly_session_registrations",
        ["principal"],
        unique=False,
    )
    op.create_table(
        "pyfly_sessions",
        sa.Column(
            "session_id",
            pyfly.data.relational.framework_schema.KeyString(length=255),
            nullable=False,
        ),
        sa.Column(
            "data",
            sa.Text()
            .with_variant(mysql.LONGTEXT(), "mariadb")
            .with_variant(sa.NVARCHAR(), "mssql")
            .with_variant(mysql.LONGTEXT(), "mysql"),
            nullable=False,
        ),
        sa.Column(
            "expires_at",
            pyfly.data.relational.framework_schema.UtcTimestamp(timezone=True),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("session_id"),
        info={"pyfly_framework_table": "sessions"},
    )
    op.create_index(
        op.f("ix_pyfly_sessions_expires_at"),
        "pyfly_sessions",
        ["expires_at"],
        unique=False,
    )
    op.create_table(
        "pyfly_snapshots",
        sa.Column(
            "aggregate_id",
            pyfly.data.relational.framework_schema.KeyString(length=255),
            nullable=False,
        ),
        sa.Column(
            "aggregate_type",
            pyfly.data.relational.framework_schema.KeyString(length=255),
            nullable=False,
        ),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column(
            "payload",
            sa.Text()
            .with_variant(mysql.LONGTEXT(), "mariadb")
            .with_variant(sa.NVARCHAR(), "mssql")
            .with_variant(mysql.LONGTEXT(), "mysql"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            pyfly.data.relational.framework_schema.UtcTimestamp(timezone=True),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("aggregate_id"),
        info={"pyfly_framework_table": "snapshots"},
    )
    op.create_table(
        "pyfly_users",
        sa.Column(
            "username",
            pyfly.data.relational.framework_schema.KeyString(length=255),
            nullable=False,
        ),
        sa.Column(
            "password_hash",
            sa.Text()
            .with_variant(mysql.LONGTEXT(), "mariadb")
            .with_variant(sa.NVARCHAR(), "mssql")
            .with_variant(mysql.LONGTEXT(), "mysql"),
            nullable=False,
        ),
        sa.Column(
            "roles",
            sa.Text()
            .with_variant(mysql.LONGTEXT(), "mariadb")
            .with_variant(sa.NVARCHAR(), "mssql")
            .with_variant(mysql.LONGTEXT(), "mysql"),
            nullable=False,
        ),
        sa.Column(
            "permissions",
            sa.Text()
            .with_variant(mysql.LONGTEXT(), "mariadb")
            .with_variant(sa.NVARCHAR(), "mssql")
            .with_variant(mysql.LONGTEXT(), "mysql"),
            nullable=False,
        ),
        sa.Column("enabled", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.PrimaryKeyConstraint("username"),
        info={"pyfly_framework_table": "users"},
    )


def downgrade():
    raise RuntimeError("Use a reviewed backup/restore recovery plan for this baseline")
