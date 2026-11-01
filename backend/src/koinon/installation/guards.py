# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""An installation receipt never becomes a new installation by deleting its history."""

IMMUTABLE = ("id", "installation_id", "tenant_id", "plan_key", "plan_sha256", "created_at")


def ledger_guards(dialect: str) -> tuple[str, ...]:
    if dialect not in {"sqlite", "postgresql"}:
        raise RuntimeError("Installation journals require PostgreSQL or SQLite")
    comparison = "IS NOT" if dialect == "sqlite" else "IS DISTINCT FROM"
    changed = " OR ".join(f"NEW.{column} {comparison} OLD.{column}" for column in IMMUTABLE)
    if dialect == "sqlite":
        update = (
            "CREATE TRIGGER koinon_installation_runs_update BEFORE UPDATE ON koinon_installation_runs "
            f"WHEN ({changed}) OR OLD.status='completed' OR NEW.generation<OLD.generation "
            "BEGIN SELECT RAISE(ABORT,'Installation receipt is immutable'); END"
        )
        delete = (
            "CREATE TRIGGER koinon_installation_runs_delete BEFORE DELETE ON koinon_installation_runs "
            "BEGIN SELECT RAISE(ABORT,'Installation receipt cannot be deleted'); END"
        )
        return update, delete
    function = (
        "CREATE FUNCTION public.koinon_installation_runs_guard() RETURNS trigger LANGUAGE plpgsql "
        "SECURITY INVOKER SET search_path=pg_catalog AS $$ BEGIN "
        "IF TG_OP IN ('DELETE','TRUNCATE') THEN RAISE EXCEPTION 'Installation receipt cannot be deleted' "
        "USING ERRCODE='23000'; END IF; "
        f"IF ({changed}) OR OLD.status='completed' OR NEW.generation<OLD.generation "
        "OR NEW.generation>OLD.generation+1 OR NOT NEW.checkpoints::jsonb @> OLD.checkpoints::jsonb THEN "
        "RAISE EXCEPTION 'Installation receipt is immutable' USING ERRCODE='23000'; END IF; "
        "IF NEW.owner_sha256 IS DISTINCT FROM OLD.owner_sha256 AND NEW.status<>'completed' "
        "AND NEW.generation<>OLD.generation+1 THEN RAISE EXCEPTION 'Installation owner is fenced' "
        "USING ERRCODE='23000'; END IF; RETURN NEW; END; $$"
    )
    rows = (
        "CREATE TRIGGER koinon_installation_runs_rows BEFORE UPDATE OR DELETE "
        "ON public.koinon_installation_runs "
        "FOR EACH ROW EXECUTE FUNCTION public.koinon_installation_runs_guard()"
    )
    truncate = (
        "CREATE TRIGGER koinon_installation_runs_truncate BEFORE TRUNCATE ON public.koinon_installation_runs "
        "FOR EACH STATEMENT EXECUTE FUNCTION public.koinon_installation_runs_guard()"
    )
    return function, rows, truncate
