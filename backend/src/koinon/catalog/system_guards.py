# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Database protection for installed knowledge-space identities."""


def system_space_guards(dialect: str) -> tuple[str, ...]:
    if dialect not in {"sqlite", "postgresql"}:
        raise RuntimeError("System spaces require PostgreSQL or SQLite")
    comparison = "IS NOT" if dialect == "sqlite" else "IS DISTINCT FROM"
    identity = ("id", "tenant_id", "workspace_id", "project_id", "parent_id", "kind")
    changed = " OR ".join(f"NEW.{key} {comparison} OLD.{key}" for key in identity)
    invalid = (
        f"NEW.system_key {comparison} OLD.system_key OR "
        f"NEW.installation_run_id {comparison} OLD.installation_run_id OR "
        f"(OLD.system_key IS NOT NULL AND (({changed}) OR NEW.status IN ('archived','disabled')))"
    )
    if dialect == "sqlite":
        return (
            "CREATE TRIGGER koinon_system_space_update BEFORE UPDATE ON lattice_catalog "
            f"WHEN {invalid} BEGIN SELECT RAISE(ABORT,'System knowledge space is protected'); END",
            "CREATE TRIGGER koinon_system_space_delete BEFORE DELETE ON lattice_catalog "
            "WHEN OLD.system_key IS NOT NULL "
            "BEGIN SELECT RAISE(ABORT,'System knowledge space is protected'); END",
        )
    return (
        "CREATE FUNCTION public.koinon_system_space_guard() RETURNS trigger LANGUAGE plpgsql "
        "SECURITY INVOKER SET search_path=pg_catalog AS $$ BEGIN "
        "IF TG_OP='TRUNCATE' THEN RAISE EXCEPTION 'Catalog truncation is prohibited' "
        "USING ERRCODE='23000'; END IF; "
        "IF TG_OP='DELETE' THEN IF OLD.system_key IS NOT NULL THEN "
        "RAISE EXCEPTION 'System knowledge space is protected' USING ERRCODE='23000'; "
        "END IF; RETURN OLD; END IF; "
        f"IF {invalid} THEN RAISE EXCEPTION 'System knowledge space is protected' "
        "USING ERRCODE='23000'; END IF; RETURN NEW; END; $$",
        "CREATE TRIGGER koinon_system_space_rows BEFORE UPDATE OR DELETE ON public.lattice_catalog "
        "FOR EACH ROW EXECUTE FUNCTION public.koinon_system_space_guard()",
        "CREATE TRIGGER koinon_system_space_truncate BEFORE TRUNCATE ON public.lattice_catalog "
        "FOR EACH STATEMENT EXECUTE FUNCTION public.koinon_system_space_guard()",
    )
