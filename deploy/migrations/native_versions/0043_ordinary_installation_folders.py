# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Retire bootstrap-folder protection without changing content or installation receipts."""

import sqlalchemy as sa
from alembic import op

revision = "koinon_0043_ordinary_folders"
down_revision = "koinon_0042_profile_preferences"
branch_labels = None
depends_on = None


def system_space_guards(dialect: str) -> tuple[str, ...]:
    if dialect not in {"sqlite", "postgresql"}:
        raise RuntimeError("System spaces require PostgreSQL or SQLite")
    comparison = "IS NOT" if dialect == "sqlite" else "IS DISTINCT FROM"
    identity = ("id", "tenant_id", "kind")
    changed = " OR ".join(f"NEW.{key} {comparison} OLD.{key}" for key in identity)
    invalid = (
        f"NEW.system_key {comparison} OLD.system_key OR "
        f"NEW.installation_run_id {comparison} OLD.installation_run_id OR "
        f"(OLD.installation_run_id IS NOT NULL AND ({changed}))"
    )
    if dialect == "sqlite":
        return (
            "CREATE TRIGGER koinon_system_space_update BEFORE UPDATE ON lattice_catalog "
            f"WHEN {invalid} BEGIN SELECT RAISE(ABORT,'Installation provenance is immutable'); END",
        )
    return (
        "CREATE FUNCTION public.koinon_system_space_guard() RETURNS trigger LANGUAGE plpgsql "
        "SECURITY INVOKER SET search_path=pg_catalog AS $$ BEGIN "
        "IF TG_OP='TRUNCATE' THEN RAISE EXCEPTION 'Catalog truncation is prohibited' "
        "USING ERRCODE='23000'; END IF; "
        f"IF {invalid} THEN RAISE EXCEPTION 'Installation provenance is immutable' "
        "USING ERRCODE='23000'; END IF; RETURN NEW; END; $$",
        "CREATE TRIGGER koinon_system_space_rows BEFORE UPDATE ON public.lattice_catalog "
        "FOR EACH ROW EXECUTE FUNCTION public.koinon_system_space_guard()",
        "CREATE TRIGGER koinon_system_space_truncate BEFORE TRUNCATE ON public.lattice_catalog "
        "FOR EACH STATEMENT EXECUTE FUNCTION public.koinon_system_space_guard()",
    )


def upgrade():
    dialect = op.get_bind().dialect.name
    if dialect == "sqlite":
        op.execute(sa.text("DROP TRIGGER IF EXISTS koinon_system_space_update"))
        op.execute(sa.text("DROP TRIGGER IF EXISTS koinon_system_space_delete"))
    elif dialect == "postgresql":
        op.execute(sa.text("DROP TRIGGER IF EXISTS koinon_system_space_rows ON public.lattice_catalog"))
        op.execute(sa.text("DROP TRIGGER IF EXISTS koinon_system_space_truncate ON public.lattice_catalog"))
        op.execute(sa.text("DROP FUNCTION IF EXISTS public.koinon_system_space_guard()"))
    else:
        raise RuntimeError("Installation provenance requires PostgreSQL or SQLite")
    for statement in system_space_guards(dialect):
        op.execute(sa.text(statement))


def downgrade():
    raise RuntimeError("Use a reviewed restore; existing folders may have been reorganized")
