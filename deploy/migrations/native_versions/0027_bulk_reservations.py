# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Reserve immutable native dataset/file and catalog table identities."""

import sqlalchemy as sa
from alembic import op

revision = "koinon_0027_bulk_reservations"
down_revision = "koinon_0026_mcp_sessions"
branch_labels = None
depends_on = None


def upgrade():
    dialect = op.get_bind().dialect.name
    if dialect not in {"sqlite", "postgresql"}:
        raise RuntimeError("Bulk reservations require PostgreSQL or SQLite")
    op.add_column(
        "koinon_bulk_items", sa.Column("reservation_json", sa.JSON(none_as_null=True), nullable=True)
    )
    op.create_table(
        "koinon_bulk_table_reservations",
        sa.Column("item_id", sa.String(64), sa.ForeignKey("koinon_bulk_items.id"), primary_key=True),
        sa.Column("ordinal", sa.Integer(), primary_key=True),
        sa.Column("table_id", sa.String(64), unique=True, nullable=False),
        sa.Column("snapshot_id", sa.String(64), unique=True, nullable=False),
        sa.Column(
            "catalog_table_id",
            sa.String(64),
            sa.ForeignKey("lattice_catalog.id"),
            unique=True,
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.CheckConstraint("ordinal BETWEEN 0 AND 15", name="ck_bulk_table_ordinal"),
    )
    if dialect == "sqlite":
        op.execute(
            "CREATE TRIGGER koinon_bulk_reservation_identity BEFORE UPDATE ON koinon_bulk_items "
            "WHEN NEW.reservation_json IS NOT OLD.reservation_json "
            "BEGIN SELECT RAISE(ABORT,'Immutable bulk reservation'); END"
        )
        for action in ("UPDATE", "DELETE"):
            op.execute(
                f"CREATE TRIGGER koinon_bulk_tables_{action.lower()} BEFORE {action} "
                "ON koinon_bulk_table_reservations BEGIN SELECT RAISE(ABORT,'Immutable bulk tables'); END"
            )
    else:
        op.execute("REVOKE ALL ON TABLE public.koinon_bulk_table_reservations FROM PUBLIC")
        op.execute(
            "CREATE FUNCTION public.koinon_bulk_tables_immutable() RETURNS trigger "
            "LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$ "
            "BEGIN RAISE EXCEPTION 'Immutable bulk tables'; END $$"
        )
        op.execute(
            "CREATE TRIGGER koinon_bulk_tables_immutable BEFORE UPDATE OR DELETE "
            "ON public.koinon_bulk_table_reservations FOR EACH ROW "
            "EXECUTE FUNCTION public.koinon_bulk_tables_immutable()"
        )
    # The 0024 PostgreSQL guard freezes every item column except its explicit mutable allowlist.


def downgrade():
    raise RuntimeError("Use a reviewed backup/restore recovery plan for bulk reservations")
