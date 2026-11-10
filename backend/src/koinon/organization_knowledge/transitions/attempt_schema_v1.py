# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Immutable activation evidence and terminal CAS resolution guards, schema version one."""

from sqlalchemy import inspect

ATTEMPTS = "koinon_knowledge_mode_index_attempts"
RESOLUTIONS = "koinon_knowledge_mode_index_resolutions"


def install(connection):
    if not inspect(connection).has_table(ATTEMPTS):
        return
    if connection.dialect.name == "sqlite":
        for table in (ATTEMPTS, RESOLUTIONS):
            connection.exec_driver_sql(
                f"CREATE TRIGGER IF NOT EXISTS {table}_delete BEFORE DELETE ON {table} "
                "BEGIN SELECT RAISE(ABORT, 'Activation history cannot be deleted'); END"
            )
        connection.exec_driver_sql(
            f"CREATE TRIGGER IF NOT EXISTS {ATTEMPTS}_immutable BEFORE UPDATE ON {ATTEMPTS} "
            "BEGIN SELECT RAISE(ABORT, 'Activation identity is immutable'); END"
        )
        connection.exec_driver_sql(
            f"CREATE TRIGGER IF NOT EXISTS {RESOLUTIONS}_initial BEFORE INSERT ON {RESOLUTIONS} "
            "WHEN NEW.status != 'pending' OR NEW.revision != 1 "
            "BEGIN SELECT RAISE(ABORT, 'Activation resolution must start pending'); END"
        )
        connection.exec_driver_sql(
            f"CREATE TRIGGER IF NOT EXISTS {RESOLUTIONS}_cas BEFORE UPDATE ON {RESOLUTIONS} "
            "WHEN NEW.id IS NOT OLD.id OR NEW.tenant_id IS NOT OLD.tenant_id OR OLD.status != 'pending' "
            "OR NEW.status NOT IN ('finished','restored','aborted') OR NEW.revision != OLD.revision + 1 "
            "BEGIN SELECT RAISE(ABORT, 'Activation resolution requires terminal CAS'); END"
        )
        return
    if connection.dialect.name != "postgresql":
        raise RuntimeError("Activation evidence supports PostgreSQL and test SQLite")
    connection.exec_driver_sql("""
        CREATE OR REPLACE FUNCTION koinon_guard_mode_index_evidence() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public AS $$
        BEGIN
            IF TG_OP = 'INSERT' THEN
                IF NEW.status <> 'pending' OR NEW.revision <> 1 THEN
                    RAISE EXCEPTION 'Activation resolution must start pending' USING ERRCODE='23514';
                END IF;
                RETURN NEW;
            END IF;
            IF TG_OP IN ('DELETE','TRUNCATE') OR TG_TABLE_NAME = 'koinon_knowledge_mode_index_attempts' THEN
                RAISE EXCEPTION 'Activation identity and history are immutable' USING ERRCODE='23514';
            END IF;
            IF NEW.id IS DISTINCT FROM OLD.id OR NEW.tenant_id IS DISTINCT FROM OLD.tenant_id
                OR OLD.status <> 'pending' OR NEW.status NOT IN ('finished','restored','aborted')
                OR NEW.revision <> OLD.revision + 1 THEN
                RAISE EXCEPTION 'Activation resolution requires terminal CAS' USING ERRCODE='23514';
            END IF;
            RETURN NEW;
        END $$
    """)
    for table in (ATTEMPTS, RESOLUTIONS):
        for event, suffix, granularity in (
            ("UPDATE OR DELETE", "rows", "ROW"),
            ("TRUNCATE", "truncate", "STATEMENT"),
        ):
            connection.exec_driver_sql(f"DROP TRIGGER IF EXISTS {table}_{suffix} ON {table}")
            connection.exec_driver_sql(
                f"CREATE TRIGGER {table}_{suffix} BEFORE {event} ON {table} FOR EACH {granularity} "
                "EXECUTE FUNCTION koinon_guard_mode_index_evidence()"
            )

    connection.exec_driver_sql(f"DROP TRIGGER IF EXISTS {RESOLUTIONS}_initial ON {RESOLUTIONS}")
    connection.exec_driver_sql(
        f"CREATE TRIGGER {RESOLUTIONS}_initial BEFORE INSERT ON {RESOLUTIONS} FOR EACH ROW "
        "EXECUTE FUNCTION koinon_guard_mode_index_evidence()"
    )
