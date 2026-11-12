# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Frozen PostgreSQL capture contract for native migration 0051.

Changes to installed capture semantics require a new forward migration. There is
no application-callable function accepting an asserted identity or dependency.
"""

from sqlalchemy import inspect, text

IDENTITIES = "koinon_catalog_history_identities"
EDGES = "koinon_catalog_history_edges"

FUNCTIONS = (
    """CREATE FUNCTION public.koinon_history_append_only() RETURNS trigger
    LANGUAGE plpgsql SET search_path=pg_catalog AS $$
    BEGIN
      IF TG_OP='INSERT' AND TG_TABLE_NAME IN
          ('koinon_catalog_history_identities','koinon_catalog_history_edges')
          AND pg_trigger_depth()>1
          AND current_user=pg_get_userbyid((SELECT relowner FROM pg_class WHERE oid=TG_RELID)) THEN
        RETURN NEW;
      END IF;
      RAISE EXCEPTION 'retained audit history is database-owned and append-only' USING ERRCODE='23514';
    END $$""",
    """CREATE FUNCTION public.koinon_history_catalog_identity() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
    BEGIN
      IF TG_OP='INSERT' THEN
        INSERT INTO public.koinon_catalog_history_identities(tenant_id,resource_id,coverage)
          VALUES(NEW.tenant_id,NEW.id,'complete');
        IF EXISTS(SELECT 1 FROM public.lattice_audit WHERE resource_id=NEW.id) THEN
          RAISE EXCEPTION 'catalog identity is already retained in audit' USING ERRCODE='23514';
        END IF;
      ELSIF NEW.id IS DISTINCT FROM OLD.id OR NEW.tenant_id IS DISTINCT FROM OLD.tenant_id THEN
        RAISE EXCEPTION 'catalog history identity is immutable' USING ERRCODE='23514';
      END IF;
      RETURN NEW;
    END $$""",
    """CREATE FUNCTION public.koinon_history_catalog_capture() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
    DECLARE snapshot record; endpoint text;
    BEGIN
      FOR snapshot IN
        SELECT OLD.tenant_id,OLD.id,OLD.parent_id WHERE TG_OP IN ('UPDATE','DELETE')
        UNION SELECT NEW.tenant_id,NEW.id,NEW.parent_id WHERE TG_OP IN ('INSERT','UPDATE')
      LOOP
        FOREACH endpoint IN ARRAY ARRAY[snapshot.id,snapshot.parent_id] LOOP
          IF endpoint IS NULL THEN CONTINUE; END IF;
          IF EXISTS(SELECT 1 FROM public.lattice_catalog WHERE id=endpoint AND tenant_id<>snapshot.tenant_id)
             OR EXISTS(SELECT 1 FROM public.koinon_catalog_history_identities
                       WHERE resource_id=endpoint AND tenant_id<>snapshot.tenant_id) THEN
            RAISE EXCEPTION 'cross-tenant catalog history endpoint' USING ERRCODE='23514';
          END IF;
          INSERT INTO public.koinon_catalog_history_identities(tenant_id,resource_id,coverage)
            VALUES(snapshot.tenant_id,endpoint,'legacy_unknown') ON CONFLICT(resource_id) DO NOTHING;
          IF NOT EXISTS(SELECT 1 FROM public.koinon_catalog_history_identities
                        WHERE resource_id=endpoint AND tenant_id=snapshot.tenant_id) THEN
            RAISE EXCEPTION 'cross-tenant catalog history endpoint' USING ERRCODE='23514';
          END IF;
        END LOOP;
        IF snapshot.parent_id IS NOT NULL THEN
          INSERT INTO public.koinon_catalog_history_edges(tenant_id,dependent_id,origin_id,kind)
            VALUES(snapshot.tenant_id,snapshot.id,snapshot.parent_id,'parent') ON CONFLICT DO NOTHING;
        END IF;
      END LOOP;
      RETURN NULL;
    END $$""",
    """CREATE FUNCTION public.koinon_history_curated_capture() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
    DECLARE snapshot record; endpoint text;
    BEGIN
      FOR snapshot IN
        SELECT OLD.tenant_id,OLD.item_id,OLD.source_asset_id WHERE TG_OP IN ('UPDATE','DELETE')
        UNION SELECT NEW.tenant_id,NEW.item_id,NEW.source_asset_id WHERE TG_OP IN ('INSERT','UPDATE')
      LOOP
        FOREACH endpoint IN ARRAY ARRAY[snapshot.item_id,snapshot.source_asset_id] LOOP
          IF EXISTS(SELECT 1 FROM public.lattice_catalog WHERE id=endpoint AND tenant_id<>snapshot.tenant_id)
             OR EXISTS(SELECT 1 FROM public.koinon_catalog_history_identities
                       WHERE resource_id=endpoint AND tenant_id<>snapshot.tenant_id) THEN
            RAISE EXCEPTION 'cross-tenant curated history endpoint' USING ERRCODE='23514';
          END IF;
          INSERT INTO public.koinon_catalog_history_identities(tenant_id,resource_id,coverage)
            VALUES(snapshot.tenant_id,endpoint,'legacy_unknown') ON CONFLICT(resource_id) DO NOTHING;
          IF NOT EXISTS(SELECT 1 FROM public.koinon_catalog_history_identities
                        WHERE resource_id=endpoint AND tenant_id=snapshot.tenant_id) THEN
            RAISE EXCEPTION 'cross-tenant curated history endpoint' USING ERRCODE='23514';
          END IF;
        END LOOP;
        INSERT INTO public.koinon_catalog_history_edges(tenant_id,dependent_id,origin_id,kind)
          VALUES(snapshot.tenant_id,snapshot.item_id,snapshot.source_asset_id,'curated_source')
          ON CONFLICT DO NOTHING;
      END LOOP;
      RETURN NULL;
    END $$""",
)


def statements():
    yield from FUNCTIONS
    for function in (
        "koinon_history_append_only",
        "koinon_history_catalog_identity",
        "koinon_history_catalog_capture",
        "koinon_history_curated_capture",
    ):
        yield f"REVOKE ALL ON FUNCTION public.{function}() FROM PUBLIC"
    for table in (IDENTITIES, EDGES):
        yield f"REVOKE ALL ON TABLE public.{table} FROM PUBLIC"
        yield (
            f"CREATE TRIGGER {table}_rows BEFORE INSERT OR UPDATE OR DELETE ON public.{table} "
            "FOR EACH ROW EXECUTE FUNCTION public.koinon_history_append_only()"
        )
        yield (
            f"CREATE TRIGGER {table}_truncate BEFORE TRUNCATE ON public.{table} "
            "FOR EACH STATEMENT EXECUTE FUNCTION public.koinon_history_append_only()"
        )
    yield (
        "CREATE TRIGGER koinon_history_catalog_identity BEFORE INSERT OR UPDATE ON public.lattice_catalog "
        "FOR EACH ROW EXECUTE FUNCTION public.koinon_history_catalog_identity()"
    )
    yield (
        "CREATE TRIGGER koinon_history_catalog_capture AFTER INSERT OR DELETE OR UPDATE OF parent_id "
        "ON public.lattice_catalog FOR EACH ROW EXECUTE FUNCTION public.koinon_history_catalog_capture()"
    )
    yield (
        "CREATE TRIGGER koinon_history_audit_rows BEFORE UPDATE OR DELETE ON public.lattice_audit "
        "FOR EACH ROW EXECUTE FUNCTION public.koinon_history_append_only()"
    )
    yield (
        "CREATE TRIGGER koinon_history_audit_truncate BEFORE TRUNCATE ON public.lattice_audit "
        "FOR EACH STATEMENT EXECUTE FUNCTION public.koinon_history_append_only()"
    )
    yield (
        "CREATE TRIGGER koinon_history_curated_capture AFTER INSERT OR UPDATE OR DELETE "
        "ON public.koinon_curated_source_roots FOR EACH ROW "
        "EXECUTE FUNCTION public.koinon_history_curated_capture()"
    )
    yield (
        "CREATE TRIGGER koinon_history_curated_truncate BEFORE TRUNCATE "
        "ON public.koinon_curated_source_roots FOR EACH STATEMENT "
        "EXECUTE FUNCTION public.koinon_history_append_only()"
    )


def install_on_create(_metadata, connection, **_kwargs):
    """Mirror the migration only for fresh PostgreSQL metadata fixtures."""
    if connection.dialect.name != "postgresql":
        return
    required = {IDENTITIES, EDGES, "lattice_catalog", "lattice_audit", "koinon_curated_source_roots"}
    if not required <= set(inspect(connection).get_table_names()):
        return
    if connection.scalar(text("SELECT to_regprocedure('public.koinon_history_catalog_capture()')")):
        return
    for statement in statements():
        connection.exec_driver_sql(statement)
