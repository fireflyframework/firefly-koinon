# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Operator-only installation; runtime and scaler identities cannot install SQL."""

import re

from psycopg import sql

from koinon.workers.scaling import DemandFunction


def validate_role_names(owner: str, reader: str) -> None:
    if owner == reader or any(
        not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", role) or role.startswith("pg_") or role == "postgres"
        for role in (owner, reader)
    ):
        raise ValueError("Use distinct dedicated owner and scaler role names")


def install(connection, contract: DemandFunction, *, owner: str, reader: str) -> None:
    """Apply atomically after migrations, using an operator-owned transaction."""
    validate_role_names(owner, reader)
    with connection.transaction():
        current = connection.execute("SELECT current_user").fetchone()[0]
        if current in (owner, reader):
            raise ValueError("Installation requires a separate operator identity")
        for role, login in ((owner, False), (reader, True)):
            record = connection.execute(
                "SELECT rolcanlogin,rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls "
                "FROM pg_catalog.pg_roles WHERE rolname=%s",
                (role,),
            ).fetchone()
            if record is None:
                if login:
                    raise ValueError("Provision the dedicated scaler login and its credential separately")
                connection.execute(
                    sql.SQL(
                        "CREATE ROLE {} NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS"
                    ).format(sql.Identifier(role))
                )
            elif record != (login, False, False, False, False, False):
                raise ValueError("Existing scaler identities have incompatible authority")
            memberships = connection.execute(
                "SELECT 1 FROM pg_catalog.pg_auth_members m JOIN pg_catalog.pg_roles r ON "
                "r.oid=m.member WHERE r.rolname=%s LIMIT 1",
                (role,),
            ).fetchone()
            if memberships:
                raise ValueError("Dedicated scaler identities cannot inherit other roles")
        incoming = connection.execute(
            "SELECT 1 FROM pg_catalog.pg_auth_members m "
            "JOIN pg_catalog.pg_roles target ON target.oid=m.roleid "
            "JOIN pg_catalog.pg_roles member ON member.oid=m.member "
            "WHERE target.rolname=%s AND member.rolname<>%s LIMIT 1",
            (owner, current),
        ).fetchone()
        if incoming:
            raise ValueError("Function owner is reachable by a non-operator identity")
        schema = connection.execute(
            "SELECT pg_catalog.pg_get_userbyid(nspowner) FROM pg_catalog.pg_namespace WHERE "
            "nspname='koinon_operations'"
        ).fetchone()
        if schema and schema[0] != current:
            raise ValueError("Operations schema must be owned by the installing operator")
        existing = connection.execute(
            "SELECT pg_catalog.pg_get_userbyid(proowner) FROM pg_catalog.pg_proc p JOIN "
            "pg_catalog.pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='koinon_operations' "
            "AND p.proname='worker_demand_v1' AND p.pronargs=0"
        ).fetchone()
        if existing and existing[0] != owner:
            raise ValueError("Refusing to replace a function owned by another identity")
        connection.execute("CREATE SCHEMA IF NOT EXISTS koinon_operations")
        connection.execute("REVOKE ALL ON SCHEMA koinon_operations FROM PUBLIC")
        for role in (owner, reader):
            connection.execute(
                sql.SQL("GRANT USAGE ON SCHEMA public,koinon_operations TO {}").format(sql.Identifier(role))
            )
        for table, columns in contract.columns.items():
            # Reader must have no direct or inherited row access, including PUBLIC grants.
            if connection.execute(
                "SELECT pg_catalog.has_table_privilege(%s,%s,"
                "'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER') OR "
                "pg_catalog.has_any_column_privilege(%s,%s,'SELECT,INSERT,UPDATE,REFERENCES')",
                (reader, "public." + table, reader, "public." + table),
            ).fetchone()[0]:
                raise ValueError("Scaler login already has raw table access")
            connection.execute(
                sql.SQL("REVOKE ALL ON TABLE public.{} FROM {}").format(
                    sql.Identifier(table), sql.Identifier(owner)
                )
            )
            actual_columns = connection.execute(
                "SELECT attname FROM pg_catalog.pg_attribute "
                "WHERE attrelid=%s::regclass AND attnum>0 AND NOT attisdropped",
                ("public." + table,),
            ).fetchall()
            connection.execute(
                sql.SQL("REVOKE ALL ({}) ON TABLE public.{} FROM {}").format(
                    sql.SQL(",").join(sql.Identifier(row[0]) for row in actual_columns),
                    sql.Identifier(table),
                    sql.Identifier(owner),
                )
            )
            connection.execute(
                sql.SQL("GRANT SELECT ({}) ON TABLE public.{} TO {}").format(
                    sql.SQL(",").join(map(sql.Identifier, columns)),
                    sql.Identifier(table),
                    sql.Identifier(owner),
                )
            )
            rls = connection.execute(
                "SELECT relrowsecurity FROM pg_catalog.pg_class WHERE oid=%s::regclass", ("public." + table,)
            ).fetchone()[0]
            if rls:
                policy = connection.execute(
                    "SELECT pg_catalog.pg_get_expr(polqual,polrelid),polcmd,"
                    "ARRAY(SELECT rolname::text FROM pg_catalog.pg_roles WHERE oid=ANY(polroles)) "
                    "FROM pg_catalog.pg_policy WHERE polrelid=%s::regclass "
                    "AND polname='koinon_worker_demand'",
                    ("public." + table,),
                ).fetchone()
                if policy and policy != ("true", "r", [owner]):
                    raise ValueError("Refusing to replace a foreign worker-demand RLS policy")
                # This NOLOGIN role can only be reached through the fixed count function.
                connection.execute(
                    sql.SQL("DROP POLICY IF EXISTS koinon_worker_demand ON public.{}").format(
                        sql.Identifier(table)
                    )
                )
                connection.execute(
                    sql.SQL(
                        "CREATE POLICY koinon_worker_demand ON public.{} FOR SELECT TO {} USING (true)"
                    ).format(sql.Identifier(table), sql.Identifier(owner))
                )
        connection.execute(
            sql.SQL("GRANT CREATE ON SCHEMA koinon_operations TO {}").format(sql.Identifier(owner))
        )
        connection.execute(contract.sql)
        connection.execute("REVOKE ALL ON FUNCTION koinon_operations.worker_demand_v1() FROM PUBLIC")
        connection.execute(
            sql.SQL("ALTER FUNCTION koinon_operations.worker_demand_v1() OWNER TO {}").format(
                sql.Identifier(owner)
            )
        )
        connection.execute(
            sql.SQL("REVOKE CREATE ON SCHEMA koinon_operations FROM {}").format(sql.Identifier(owner))
        )
        connection.execute(
            sql.SQL("GRANT EXECUTE ON FUNCTION koinon_operations.worker_demand_v1() TO {}").format(
                sql.Identifier(reader)
            )
        )
        connection.execute(
            sql.SQL("ALTER ROLE {} SET statement_timeout = '5s'").format(sql.Identifier(reader))
        )
