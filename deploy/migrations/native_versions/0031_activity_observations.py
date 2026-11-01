# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Append-only, payload-free MCP observations and installation coverage start."""

import sqlalchemy as sa
from alembic import op
from pyfly.data.relational.sqlalchemy import UtcDateTime

revision = "koinon_0031_activity"
down_revision = "koinon_0030_comms"
branch_labels = None
depends_on = None


def _append_only(name: str) -> None:
    if op.get_bind().dialect.name == "sqlite":
        for operation in ("UPDATE", "DELETE"):
            op.execute(
                sa.text(
                    f"CREATE TRIGGER {name}_immutable_{operation.lower()} BEFORE {operation} ON {name} "
                    "BEGIN SELECT RAISE(ABORT, 'Activity observations are append-only'); END"
                )
            )
    elif op.get_bind().dialect.name == "postgresql":
        function = f"{name}_immutable"
        for statement in (
            (
                f"CREATE FUNCTION {function}() RETURNS trigger LANGUAGE plpgsql AS $$ "
                "BEGIN RAISE EXCEPTION 'Activity observations are append-only' USING ERRCODE = '23000'; END; $$"
            ),
            (
                f"CREATE TRIGGER {function}_rows BEFORE UPDATE OR DELETE ON {name} "
                f"FOR EACH ROW EXECUTE FUNCTION {function}()"
            ),
            (
                f"CREATE TRIGGER {function}_truncate BEFORE TRUNCATE ON {name} "
                f"FOR EACH STATEMENT EXECUTE FUNCTION {function}()"
            ),
        ):
            op.execute(sa.text(statement))
    else:
        raise RuntimeError("Activity observations require PostgreSQL or SQLite")


def upgrade():
    op.create_table(
        "koinon_activity_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(64),
            sa.ForeignKey("lattice_tenants.id"),
            nullable=False,
        ),
        sa.Column("subject", sa.String(512), nullable=False),
        sa.Column("workspace_id", sa.String(64), nullable=True),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("operation", sa.String(80), nullable=False),
        sa.Column("outcome", sa.String(16), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            UtcDateTime(),
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.CheckConstraint("kind IN ('request', 'tool')", name="ck_activity_kind"),
        sa.CheckConstraint(
            "outcome IN ('succeeded', 'failed', 'rejected', 'cancelled')",
            name="ck_activity_outcome",
        ),
        sa.CheckConstraint(
            "duration_ms >= 0 AND duration_ms <= 86400000", name="ck_activity_duration"
        ),
    )
    op.create_index(
        "ix_activity_tenant_subject_time_kind",
        "koinon_activity_events",
        ["tenant_id", "subject", "created_at", "kind"],
    )
    op.create_index(
        "ix_activity_tenant_time_kind",
        "koinon_activity_events",
        ["tenant_id", "created_at", "kind"],
    )
    op.create_table(
        "koinon_activity_coverage",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "coverage_started_at",
            UtcDateTime(),
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.CheckConstraint(
            "id = 'installation'", name="ck_activity_coverage_singleton"
        ),
    )
    for name in ("koinon_activity_events", "koinon_activity_coverage"):
        _append_only(name)
    op.execute(
        sa.text("INSERT INTO koinon_activity_coverage (id) VALUES ('installation')")
    )


def downgrade():
    raise RuntimeError(
        "Use a reviewed restore plan to preserve activity observations and their coverage start"
    )
