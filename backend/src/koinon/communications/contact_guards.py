# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Stable identity, monotonic operator revision and one-time signed-login binding."""

IMMUTABLE_COLUMNS = ("id", "tenant_id", "identity_key", "identity_json", "created_at")
OBSERVATION_COLUMNS = ("contact_ciphertext", "observed_at", "expires_at", "revoked_at")
BINDING_COLUMNS = ("canonical_subject", "binding_ciphertext", "bound_at")


def contact_guards(dialect: str) -> tuple[str, ...]:
    if dialect not in {"sqlite", "postgresql"}:
        raise RuntimeError("Operator contacts require PostgreSQL or SQLite")
    comparison = "IS NOT" if dialect == "sqlite" else "IS DISTINCT FROM"

    def changed(columns):
        return " OR ".join(
            f"NEW.{key}::jsonb {comparison} OLD.{key}::jsonb"
            if dialect == "postgresql" and key == "identity_json"
            else f"NEW.{key} {comparison} OLD.{key}"
            for key in columns
        )

    binding = f"({changed(BINDING_COLUMNS)})"
    invalid = (
        f"({changed(IMMUTABLE_COLUMNS)}) OR OLD.revoked_at IS NOT NULL OR "
        f"({binding} AND (OLD.canonical_subject IS NOT NULL OR NEW.canonical_subject IS NULL "
        "OR NEW.binding_ciphertext IS NULL OR NEW.bound_at IS NULL OR NEW.revision<>OLD.revision "
        f"OR ({changed(OBSERVATION_COLUMNS)}))) OR "
        f"(NOT {binding} AND (NEW.revision<>OLD.revision+1 OR NEW.observed_at<OLD.observed_at))"
    )
    table = "koinon_operator_delivery_contacts"
    if dialect == "sqlite":
        return (
            f"CREATE TRIGGER {table}_update BEFORE UPDATE ON {table} WHEN {invalid} "
            "BEGIN SELECT RAISE(ABORT,'Operator contact transition is prohibited'); END",
            f"CREATE TRIGGER {table}_delete BEFORE DELETE ON {table} "
            "BEGIN SELECT RAISE(ABORT,'Operator contacts cannot be deleted'); END",
        )
    return (
        f"CREATE FUNCTION public.{table}_guard() RETURNS trigger LANGUAGE plpgsql "
        "SECURITY INVOKER SET search_path=pg_catalog AS $$ BEGIN "
        "IF TG_OP IN ('DELETE','TRUNCATE') THEN RAISE EXCEPTION 'Operator contacts cannot be deleted' "
        "USING ERRCODE='23000'; END IF; "
        f"IF {invalid} THEN RAISE EXCEPTION 'Operator contact transition is prohibited' "
        "USING ERRCODE='23000'; END IF; RETURN NEW; END; $$",
        f"CREATE TRIGGER {table}_rows BEFORE UPDATE OR DELETE ON public.{table} "
        f"FOR EACH ROW EXECUTE FUNCTION public.{table}_guard()",
        f"CREATE TRIGGER {table}_truncate BEFORE TRUNCATE ON public.{table} "
        f"FOR EACH STATEMENT EXECUTE FUNCTION public.{table}_guard()",
    )
