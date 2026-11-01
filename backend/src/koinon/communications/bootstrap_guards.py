# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Operator observations are immutable; only a consumed signed-login grant can bind their subject."""

IMMUTABLE_CONTACT_COLUMNS = (
    "id",
    "installation_id",
    "grant_id",
    "identity_sha256",
    "event_id",
    "contact_ciphertext",
    "observed_at",
    "expires_at",
)


def contact_guards(dialect: str) -> tuple[str, ...]:
    if dialect not in {"sqlite", "postgresql"}:
        raise RuntimeError("Bootstrap contacts require PostgreSQL or SQLite")
    prefix = "main" if dialect == "sqlite" else "public"
    comparison = "IS NOT" if dialect == "sqlite" else "IS DISTINCT FROM"
    changed = " OR ".join(f"NEW.{key} {comparison} OLD.{key}" for key in IMMUTABLE_CONTACT_COLUMNS)
    binding = (
        f"EXISTS (SELECT 1 FROM {prefix}.koinon_bootstrap_identity_grants g "
        f"JOIN {prefix}.lattice_memberships m ON m.id=g.membership_id "
        "WHERE g.id=OLD.grant_id AND g.consumed_at IS NOT NULL "
        "AND g.consumed_subject=NEW.canonical_subject AND m.subject=NEW.canonical_subject "
        "AND m.tenant_id=g.tenant_id AND m.workspace_id IS NULL AND m.role='admin' AND m.active)"
    )
    invalid = (
        f"({changed}) OR OLD.canonical_subject IS NOT NULL OR NEW.canonical_subject IS NULL OR NOT {binding}"
    )
    if dialect == "sqlite":
        update = (
            "CREATE TRIGGER koinon_bootstrap_contacts_update BEFORE UPDATE ON koinon_bootstrap_contacts "
            f"WHEN {invalid} BEGIN SELECT RAISE(ABORT,'Bootstrap contact is immutable'); END"
        )
        delete = (
            "CREATE TRIGGER koinon_bootstrap_contacts_delete BEFORE DELETE ON koinon_bootstrap_contacts "
            "BEGIN SELECT RAISE(ABORT,'Bootstrap contacts cannot be deleted'); END"
        )
        return update, delete
    function = (
        "CREATE FUNCTION public.koinon_bootstrap_contacts_guard() RETURNS trigger LANGUAGE plpgsql "
        "SECURITY INVOKER SET search_path=pg_catalog AS $$ BEGIN "
        "IF TG_OP IN ('DELETE','TRUNCATE') THEN RAISE EXCEPTION 'Bootstrap contacts cannot be deleted' "
        "USING ERRCODE='23000'; END IF; "
        f"IF {invalid} THEN RAISE EXCEPTION 'Bootstrap contact is immutable' USING ERRCODE='23000'; "
        "END IF; RETURN NEW; END; $$"
    )
    rows = (
        "CREATE TRIGGER koinon_bootstrap_contacts_rows BEFORE UPDATE OR DELETE ON "
        "public.koinon_bootstrap_contacts FOR EACH ROW "
        "EXECUTE FUNCTION public.koinon_bootstrap_contacts_guard()"
    )
    truncate = (
        "CREATE TRIGGER koinon_bootstrap_contacts_truncate BEFORE TRUNCATE ON "
        "public.koinon_bootstrap_contacts FOR EACH STATEMENT "
        "EXECUTE FUNCTION public.koinon_bootstrap_contacts_guard()"
    )
    return function, rows, truncate
