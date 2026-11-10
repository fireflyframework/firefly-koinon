# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Database-owned readiness changes; ordinary observations never advance a generation."""

from sqlalchemy import inspect
from sqlalchemy.types import UserDefinedType


class TransactionId(UserDefinedType):
    cache_ok = True

    def get_col_spec(self, **_kwargs):
        return "xid8"


GENERATIONS = "koinon_knowledge_readiness_generations"
CHANGES = "koinon_knowledge_readiness_changes"
PENDING = "koinon_knowledge_readiness_pending"
# A missing workspace means a change can affect every workspace in this tenant.
WATCHED = {
    "lattice_jobs": (None, ("tenant_id", "kind", "payload")),
    "lattice_catalog": (
        "workspace_id",
        ("tenant_id", "workspace_id", "project_id", "parent_id", "kind", "status", "metadata_json"),
    ),
    "lattice_memberships": ("workspace_id", ("tenant_id", "workspace_id", "subject", "role", "active")),
    "lattice_domain_bindings": (
        "workspace_id",
        (
            "tenant_id",
            "catalog_id",
            "workspace_id",
            "domain",
            "entity_kind",
            "native_id",
            "native_workspace_id",
            "details_json",
        ),
    ),
    "koinon_providers": (
        None,
        ("tenant_id", "kind", "api", "base_url", "model_ids", "secret_ciphertext", "enabled", "revision"),
    ),
    "koinon_knowledge_connections": (
        "workspace_id",
        (
            "tenant_id",
            "workspace_id",
            "domain",
            "role",
            "mode",
            "provider_id",
            "model_id",
            "model_options",
            "dimensions",
            "storage_dimensions",
            "space_id",
            "embedding_fingerprint",
            "enabled",
            "revision",
        ),
    ),
    "koinon_personal_tokens": (
        None,
        (
            "tenant_id",
            "subject",
            "purpose",
            "authorized_application_id",
            "scopes",
            "workspace_ids",
            "asset_ids",
            "resource_ids",
            "expires_at",
            "revoked_at",
            "token_hash",
        ),
    ),
    "koinon_authorized_applications": (
        None,
        (
            "tenant_id",
            "subject",
            "client_id",
            "resource",
            "workspace_id",
            "scopes",
            "client_registration",
            "expires_at",
            "revoked_at",
        ),
    ),
    "koinon_knowledge_indexes": (
        "workspace_id",
        (
            "tenant_id",
            "workspace_id",
            "native_workspace_id",
            "domain",
            "native_id",
            "provider_id",
            "provider_kind",
            "provider_revision",
            "model_id",
            "dimensions",
            "storage_dimensions",
            "embedding_fingerprint",
            "status",
            "active_slot",
            "transition",
            "job_id",
            "indexed",
            "qualification",
            "chunk_count",
            "vector_count",
        ),
    ),
}


def sqlite_bump(alias, workspace, condition="1"):
    scope = f"coalesce({alias}.{workspace}, '')" if workspace else "''"
    return (
        f"INSERT INTO {GENERATIONS}(tenant_id,generation,fence) "
        f"SELECT {alias}.tenant_id,1,0 WHERE {condition} "
        "ON CONFLICT(tenant_id) DO UPDATE SET generation=generation+1; "
        f"INSERT INTO {CHANGES}(tenant_id,workspace_id,generation) "
        f"SELECT {alias}.tenant_id,{scope},generation FROM {GENERATIONS} "
        f"WHERE tenant_id={alias}.tenant_id AND ({condition}) "
        "ON CONFLICT(tenant_id,workspace_id) DO UPDATE SET generation=excluded.generation; "
    )


def sqlite_triggers(table, workspace, fields):
    prefix = "koinon_readiness_" + table
    changed = " OR ".join(f"NEW.{field} IS NOT OLD.{field}" for field in fields)
    moved = "NEW.tenant_id IS NOT OLD.tenant_id"
    if workspace:
        moved += f" OR NEW.{workspace} IS NOT OLD.{workspace}"
    insert, delete = "1", "1"
    if table == "lattice_jobs":
        insert, delete = "NEW.kind='knowledge.index'", "OLD.kind='knowledge.index'"
        moved = f"({moved}) OR NEW.kind IS NOT OLD.kind"
    return (
        f"CREATE TRIGGER IF NOT EXISTS {prefix}_insert AFTER INSERT ON {table} "
        f"BEGIN {sqlite_bump('NEW', workspace, insert)} END",
        f"CREATE TRIGGER IF NOT EXISTS {prefix}_delete AFTER DELETE ON {table} "
        f"BEGIN {sqlite_bump('OLD', workspace, delete)} END",
        f"CREATE TRIGGER IF NOT EXISTS {prefix}_update AFTER UPDATE ON {table} WHEN {changed} BEGIN "
        f"{sqlite_bump('OLD', workspace, f'({moved}) AND ({delete})')} "
        f"{sqlite_bump('NEW', workspace, insert)} END",
    )


def postgres_triggers(table, workspace, fields):
    result = [
        f"CREATE OR REPLACE TRIGGER a_koinon_readiness_guard_{table} "
        f"BEFORE INSERT OR UPDATE OR DELETE OR TRUNCATE ON public.{table} "
        "FOR EACH STATEMENT EXECUTE FUNCTION public.koinon_guard_knowledge_readiness()",
    ]
    for operation in ("insert", "update", "delete"):
        name = "koinon_readiness_" + table + "_" + operation
        if operation == "update":
            before = "jsonb_build_array(" + ",".join("o." + field for field in fields) + ")"
            after = "jsonb_build_array(" + ",".join("n." + field for field in fields) + ")"
            condition = before + " IS DISTINCT FROM " + after
            origin = f"new_rows n FULL JOIN old_rows o USING(id) WHERE ({condition})"
            impact = " UNION ".join(
                f"SELECT {alias}.tenant_id, "
                + (f"coalesce({alias}.{workspace},'')" if workspace else "''")
                + f" AS workspace_id FROM {origin} AND {alias}.tenant_id IS NOT NULL"
                + (f" AND {alias}.kind='knowledge.index'" if table == "lattice_jobs" else "")
                for alias in ("o", "n")
            )
            reference = "OLD TABLE AS old_rows NEW TABLE AS new_rows"
        else:
            alias = "new_rows" if operation == "insert" else "old_rows"
            impact = "SELECT tenant_id, " + (f"coalesce({workspace},'')" if workspace else "''")
            impact += f" AS workspace_id FROM {alias} WHERE tenant_id IS NOT NULL"
            if table == "lattice_jobs":
                impact += " AND kind='knowledge.index'"
            reference = "NEW TABLE AS new_rows" if operation == "insert" else "OLD TABLE AS old_rows"
        result.extend(
            (
                f"CREATE OR REPLACE FUNCTION public.{name}() RETURNS trigger LANGUAGE plpgsql "
                "SECURITY DEFINER SET search_path=pg_catalog,public AS $$ BEGIN "
                f"INSERT INTO public.{PENDING}(transaction_id,tenant_id,workspace_id) "
                f"SELECT DISTINCT pg_current_xact_id(),tenant_id,workspace_id FROM ({impact}) affected "
                "ORDER BY tenant_id,workspace_id ON CONFLICT DO NOTHING; "
                "RETURN NULL; END $$",
                f"REVOKE ALL ON FUNCTION public.{name}() FROM PUBLIC",
                f"CREATE OR REPLACE TRIGGER {name} AFTER {operation.upper()} ON public.{table} "
                f"REFERENCING {reference} FOR EACH STATEMENT EXECUTE FUNCTION public.{name}()",
            )
        )
    truncate = "koinon_readiness_" + table + "_truncate"
    result.extend(
        (
            f"CREATE OR REPLACE FUNCTION public.{truncate}() RETURNS trigger LANGUAGE plpgsql "
            "SECURITY DEFINER SET search_path=pg_catalog AS $$ BEGIN "
            "RAISE EXCEPTION 'Use scoped DELETE to preserve readiness invalidation' USING ERRCODE='0A000'; "
            "END $$",
            f"REVOKE ALL ON FUNCTION public.{truncate}() FROM PUBLIC",
            f"CREATE OR REPLACE TRIGGER z_{truncate} BEFORE TRUNCATE ON public.{table} "
            f"FOR EACH STATEMENT EXECUTE FUNCTION public.{truncate}()",
        )
    )
    return result


def postgres_deferred(connection):
    statements = (
        f"CREATE TABLE IF NOT EXISTS public.{PENDING} (transaction_id xid8 NOT NULL, "
        "tenant_id varchar(64) NOT NULL,workspace_id varchar(64) NOT NULL, "
        "PRIMARY KEY(transaction_id,tenant_id,workspace_id))",
        f"REVOKE ALL ON TABLE public.{PENDING} FROM PUBLIC",
        f"CREATE INDEX IF NOT EXISTS ix_knowledge_readiness_transaction "
        f"ON public.{GENERATIONS}(last_transaction)",
        "CREATE OR REPLACE FUNCTION public.koinon_guard_knowledge_readiness() RETURNS trigger "
        "LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$ BEGIN "
        f"IF EXISTS(SELECT 1 FROM public.{GENERATIONS} WHERE last_transaction=pg_current_xact_id()) THEN "
        "RAISE EXCEPTION 'Readiness is sealed; start a new content transaction' USING ERRCODE='25000'; "
        "END IF; RETURN NULL; END $$",
        "REVOKE ALL ON FUNCTION public.koinon_guard_knowledge_readiness() FROM PUBLIC",
        "CREATE OR REPLACE FUNCTION public.koinon_commit_knowledge_readiness() RETURNS trigger "
        "LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$ BEGIN "
        f"WITH affected AS MATERIALIZED(SELECT p.tenant_id,p.workspace_id FROM public.{PENDING} p "
        "JOIN public.lattice_tenants t ON t.id=p.tenant_id WHERE p.transaction_id=pg_current_xact_id()), "
        f"advanced AS (INSERT INTO public.{GENERATIONS}(tenant_id,generation,fence,last_transaction) "
        "SELECT DISTINCT tenant_id,1,0,pg_current_xact_id() FROM affected ORDER BY tenant_id "
        f"ON CONFLICT(tenant_id) DO UPDATE SET generation={GENERATIONS}.generation+1, "
        "last_transaction=pg_current_xact_id() RETURNING tenant_id,generation) "
        f"INSERT INTO public.{CHANGES}(tenant_id,workspace_id,generation) "
        "SELECT a.tenant_id,a.workspace_id,g.generation FROM affected a JOIN advanced g USING(tenant_id) "
        "ORDER BY a.tenant_id,a.workspace_id ON CONFLICT(tenant_id,workspace_id) "
        "DO UPDATE SET generation=excluded.generation; "
        f"DELETE FROM public.{PENDING} WHERE transaction_id=pg_current_xact_id(); RETURN NULL; END $$",
        "REVOKE ALL ON FUNCTION public.koinon_commit_knowledge_readiness() FROM PUBLIC",
        "DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM pg_trigger WHERE tgname='koinon_readiness_commit' "
        f"AND tgrelid='public.{PENDING}'::regclass) THEN CREATE CONSTRAINT TRIGGER koinon_readiness_commit "
        f"AFTER INSERT ON public.{PENDING} DEFERRABLE INITIALLY DEFERRED FOR EACH ROW "
        "EXECUTE FUNCTION public.koinon_commit_knowledge_readiness(); END IF; END $$",
        "CREATE OR REPLACE FUNCTION public.koinon_lock_knowledge_readiness(p_tenant text,p_expected bigint) "
        "RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$ "
        "DECLARE actual bigint; BEGIN "
        f"IF EXISTS(SELECT 1 FROM public.{PENDING} WHERE transaction_id=pg_current_xact_id() "
        "AND tenant_id=p_tenant) THEN RETURN false; END IF; "
        f"SELECT generation INTO actual FROM public.{GENERATIONS} WHERE tenant_id=p_tenant FOR SHARE; "
        "RETURN actual IS NOT NULL AND actual=p_expected; END $$",
        "REVOKE ALL ON FUNCTION public.koinon_lock_knowledge_readiness(text,bigint) FROM PUBLIC",
    )
    for statement in statements:
        connection.exec_driver_sql(statement)


def install(connection, *, require_complete=False):
    dialect = connection.dialect.name
    if dialect not in {"sqlite", "postgresql"}:
        raise RuntimeError("Readiness generations require the qualified SQLite or PostgreSQL dialect")
    available = set(inspect(connection).get_table_names())
    if GENERATIONS not in available:
        return
    if require_complete and dialect == "postgresql" and set(WATCHED) - available:
        raise RuntimeError("Readiness generation migration requires the complete primary schema")
    connection.exec_driver_sql(
        f"INSERT INTO {GENERATIONS}(tenant_id,generation,fence) SELECT id,0,0 FROM lattice_tenants WHERE 1=1 "
        "ON CONFLICT(tenant_id) DO NOTHING"
    )
    if dialect == "sqlite":
        seed = (
            "CREATE TRIGGER IF NOT EXISTS koinon_readiness_tenant_seed "
            "AFTER INSERT ON lattice_tenants BEGIN "
            f"INSERT INTO {GENERATIONS}(tenant_id,generation,fence) VALUES(NEW.id,0,0) "
            "ON CONFLICT(tenant_id) DO NOTHING; END"
        )
        connection.exec_driver_sql(seed)
    else:
        postgres_deferred(connection)
        for statement in (
            "CREATE OR REPLACE FUNCTION public.koinon_readiness_tenant_seed() RETURNS trigger "
            "LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$ BEGIN "
            f"INSERT INTO public.{GENERATIONS}(tenant_id,generation,fence) SELECT id,0,0 FROM new_rows "
            "ON CONFLICT(tenant_id) DO NOTHING; RETURN NULL; END $$",
            "REVOKE ALL ON FUNCTION public.koinon_readiness_tenant_seed() FROM PUBLIC",
            "CREATE OR REPLACE TRIGGER koinon_readiness_tenant_seed AFTER INSERT ON public.lattice_tenants "
            "REFERENCING NEW TABLE AS new_rows FOR EACH STATEMENT "
            "EXECUTE FUNCTION public.koinon_readiness_tenant_seed()",
        ):
            connection.exec_driver_sql(statement)
    for table, (workspace, fields) in WATCHED.items():
        if table in available:
            for statement in (
                sqlite_triggers(table, workspace, fields)
                if dialect == "sqlite"
                else postgres_triggers(table, workspace, fields)
            ):
                connection.exec_driver_sql(statement)
