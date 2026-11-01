# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Provision separate configured roles; never invent or print a deployment credential."""

import argparse
import os

import psycopg
from psycopg import sql
from sqlalchemy.engine import make_url

ROLES = (
    ("KOINON_DATABASE_URL", False, ("lattice_", "koinon_", "pyfly_", "firefly_")),
    ("KOINON_CANON_DATABASE_URL", False, ("canon_",)),
    ("KOINON_CANON_ADMIN_DATABASE_URL", True, ("canon_",)),
    ("KOINON_STRUCTURED_DATABASE_URL", False, ("flyquery_",)),
    ("KOINON_STRUCTURED_ADMIN_DATABASE_URL", True, ("flyquery_",)),
)


def grant_table(connection, table, role, *, document_control=False):
    if table == "koinon_operator_delivery_contacts":
        from koinon.communications.contact_guards import (
            BINDING_COLUMNS,
            IMMUTABLE_COLUMNS,
            OBSERVATION_COLUMNS,
        )

        connection.execute(
            sql.SQL("REVOKE ALL ON TABLE public.{} FROM {}").format(
                sql.Identifier(table), sql.Identifier(role)
            )
        )
        columns = sql.SQL(", ").join(
            sql.Identifier(name)
            for name in (
                *IMMUTABLE_COLUMNS,
                *OBSERVATION_COLUMNS,
                *BINDING_COLUMNS,
                "revision",
            )
        )
        for privilege in ("INSERT", "UPDATE"):
            connection.execute(
                sql.SQL("REVOKE {} ({}) ON TABLE public.{} FROM {}").format(
                    sql.SQL(privilege),
                    columns,
                    sql.Identifier(table),
                    sql.Identifier(role),
                )
            )
        connection.execute(
            sql.SQL("GRANT SELECT, UPDATE ({}) ON TABLE public.{} TO {}").format(
                sql.SQL(", ").join(sql.Identifier(name) for name in BINDING_COLUMNS),
                sql.Identifier(table),
                sql.Identifier(role),
            )
        )
        return
    if table == "koinon_installation_runs":
        connection.execute(
            sql.SQL("REVOKE ALL ON TABLE public.{} FROM {}").format(
                sql.Identifier(table), sql.Identifier(role)
            )
        )
        return
    if table == "koinon_bootstrap_contacts":
        from koinon.communications.bootstrap_guards import IMMUTABLE_CONTACT_COLUMNS

        connection.execute(
            sql.SQL("REVOKE ALL ON TABLE public.{} FROM {}").format(
                sql.Identifier(table), sql.Identifier(role)
            )
        )
        columns = sql.SQL(", ").join(
            sql.Identifier(name)
            for name in (*IMMUTABLE_CONTACT_COLUMNS, "canonical_subject")
        )
        for privilege in ("INSERT", "UPDATE"):
            connection.execute(
                sql.SQL("REVOKE {} ({}) ON TABLE public.{} FROM {}").format(
                    sql.SQL(privilege),
                    columns,
                    sql.Identifier(table),
                    sql.Identifier(role),
                )
            )
        connection.execute(
            sql.SQL(
                "GRANT SELECT, UPDATE (canonical_subject) ON TABLE public.{} TO {}"
            ).format(sql.Identifier(table), sql.Identifier(role))
        )
        return
    if table == "koinon_bootstrap_identity_grants":
        from koinon.bootstrap.entities import ACTIVATION_COLUMNS, IMMUTABLE_COLUMNS

        connection.execute(
            sql.SQL("REVOKE ALL ON TABLE public.{} FROM {}").format(
                sql.Identifier(table), sql.Identifier(role)
            )
        )
        columns = sql.SQL(", ").join(
            sql.Identifier(name) for name in (*IMMUTABLE_COLUMNS, *ACTIVATION_COLUMNS)
        )
        for privilege in ("INSERT", "UPDATE"):
            connection.execute(
                sql.SQL("REVOKE {} ({}) ON TABLE public.{} FROM {}").format(
                    sql.SQL(privilege),
                    columns,
                    sql.Identifier(table),
                    sql.Identifier(role),
                )
            )
        connection.execute(
            sql.SQL("GRANT SELECT ON TABLE public.{} TO {}").format(
                sql.Identifier(table), sql.Identifier(role)
            )
        )
        connection.execute(
            sql.SQL("GRANT UPDATE ({}) ON TABLE public.{} TO {}").format(
                sql.SQL(", ").join(sql.Identifier(name) for name in ACTIVATION_COLUMNS),
                sql.Identifier(table),
                sql.Identifier(role),
            )
        )
        return
    if table in {"pyfly_mcp_sessions", "pyfly_mcp_session_admission"}:
        connection.execute(
            sql.SQL("REVOKE ALL ON TABLE public.{} FROM {}").format(
                sql.Identifier(table), sql.Identifier(role)
            )
        )
        privileges = (
            "SELECT,INSERT,UPDATE,DELETE"
            if table == "pyfly_mcp_sessions"
            else "SELECT,INSERT,UPDATE"
        )
        connection.execute(
            sql.SQL("GRANT {} ON TABLE public.{} TO {}").format(
                sql.SQL(privileges), sql.Identifier(table), sql.Identifier(role)
            )
        )
        return
    immutable = (
        table.startswith(("flyquery_lineage_", "flyquery_coordinate_"))
        or table == "flyquery_snapshot_lineage"
        or table
        in {
            "canon_knowledge_version_evidence",
            "canon_knowledge_version_chunks",
            "canon_source_artifacts",
            "canon_source_versions",
            "canon_source_extractions",
            "canon_source_parts",
            "canon_source_transform_steps",
            "canon_source_lineage_events",
            "koinon_mcp_read_receipts",
            "koinon_chat_memory_manifests",
            "koinon_installation_identity",
            "koinon_activity_events",
            "koinon_activity_coverage",
            "koinon_bulk_table_reservations",
            "koinon_query_batch_references",
        }
    )
    receipt = table in {
        "koinon_bulk_batches",
        "koinon_bulk_items",
        "koinon_bulk_uploads",
        "koinon_bulk_quotas",
        "canon_curated_heads",
        "canon_knowledge_commits",
        "canon_source_heads",
        "koinon_organization_chat_settings",
        "koinon_organization_branding",
        "koinon_organization_people",
        "koinon_corporate_profile_snapshots",
        "koinon_organization_presentation_preferences",
        "koinon_organization_directory_settings",
        "koinon_organization_profile_mappings",
        "koinon_external_knowledge_reviews",
        "koinon_external_file_reviews",
        "koinon_bulk_upload_states",
        "koinon_bulk_recoveries",
        "flyquery_bulk_operations",
        "koinon_query_batches",
        "koinon_query_batch_items",
        "flyquery_bulk_query_operations",
        "koinon_mcp_oauth_clients",
        "koinon_email_invitations",
        "koinon_communication_identities",
        "koinon_communication_outbox",
        "koinon_notifications",
        "koinon_notification_preferences",
        "koinon_communication_policies",
        "koinon_welcome_admissions",
        "koinon_digest_subscriptions",
    }
    outbox = table.startswith("canon_knowledge_outbox_")
    if immutable or receipt or outbox:
        connection.execute(
            sql.SQL("REVOKE ALL ON TABLE public.{} FROM {}").format(
                sql.Identifier(table), sql.Identifier(role)
            )
        )
        privileges = (
            "SELECT,INSERT"
            if immutable
            else "SELECT,INSERT,UPDATE"
            if receipt
            else "SELECT,INSERT"
            if table.endswith(("_events", "_deliveries"))
            else "SELECT"
            if table.endswith("_consumers")
            else None
        )
        if privileges:
            connection.execute(
                sql.SQL("GRANT {} ON TABLE public.{} TO {}").format(
                    sql.SQL(privileges), sql.Identifier(table), sql.Identifier(role)
                )
            )
        if table == "koinon_installation_identity":
            # Row locks require one UPDATE column; database guards reject every actual mutation.
            connection.execute(
                sql.SQL(
                    "REVOKE UPDATE (singleton, installation_id, created_at) ON TABLE public.{} FROM {}"
                ).format(sql.Identifier(table), sql.Identifier(role))
            )
            connection.execute(
                sql.SQL("GRANT UPDATE (singleton) ON TABLE public.{} TO {}").format(
                    sql.Identifier(table), sql.Identifier(role)
                )
            )
        return
    if table == "canon_index_provisions":
        connection.execute(
            sql.SQL("REVOKE ALL ON TABLE public.{} FROM {}").format(
                sql.Identifier(table), sql.Identifier(role)
            )
        )
        connection.execute(
            sql.SQL(
                "REVOKE ALL ON FUNCTION public.koinon_provision_document_index(text,text,text) FROM {}"
            ).format(sql.Identifier(role))
        )
        if document_control:
            connection.execute(
                sql.SQL("GRANT SELECT,INSERT ON TABLE public.{} TO {}").format(
                    sql.Identifier(table), sql.Identifier(role)
                )
            )
            connection.execute(
                sql.SQL(
                    "GRANT EXECUTE ON FUNCTION public.koinon_provision_document_index(text,text,text) TO {}"
                ).format(sql.Identifier(role))
            )
        return
    connection.execute(
        sql.SQL("GRANT SELECT,INSERT,UPDATE,DELETE ON TABLE public.{} TO {}").format(
            sql.Identifier(table), sql.Identifier(role)
        )
    )


def grant_sequence(connection, name, role):
    publisher = name.startswith("canon_knowledge_outbox_")
    if publisher:
        connection.execute(
            sql.SQL("REVOKE ALL ON SEQUENCE public.{} FROM {}").format(
                sql.Identifier(name), sql.Identifier(role)
            )
        )
    connection.execute(
        sql.SQL("GRANT {} ON SEQUENCE public.{} TO {}").format(
            sql.SQL("USAGE" if publisher else "USAGE,SELECT"),
            sql.Identifier(name),
            sql.Identifier(role),
        )
    )


CONTACT_OPERATOR_READ_TABLES = (
    "lattice_tenants",
    "lattice_memberships",
    "koinon_identity_providers",
    "koinon_identity_mappings",
    "koinon_identity_grants",
    "koinon_bootstrap_identity_grants",
    "koinon_communication_policies",
)
CONTACT_OPERATOR_APPEND_TABLES = ("lattice_audit", "koinon_communication_outbox")


def _contact_operator_role(connection, role):
    flags = connection.execute(
        "SELECT rolsuper,rolbypassrls,rolcreaterole,rolcreatedb,rolreplication,rolinherit "
        "FROM pg_roles WHERE rolname=%s",
        (role,),
    ).fetchone()
    memberships = connection.execute(
        "SELECT 1 FROM pg_auth_members m JOIN pg_roles r ON r.oid=m.member "
        "WHERE r.rolname=%s LIMIT 1",
        (role,),
    ).fetchone()
    creates = connection.execute(
        "SELECT has_schema_privilege(%s,'public','CREATE'),"
        "has_database_privilege(%s,current_database(),'CREATE')",
        (role, role),
    ).fetchone()
    if flags != (False,) * 6 or memberships is not None or creates != (False, False):
        raise ValueError(
            "Contact operator requires a distinct NOINHERIT role without elevated flags, parents or DDL"
        )


def check_contact_operator(connection, role, *, dependencies=True):
    from koinon.communications.contact_guards import (
        OBSERVATION_COLUMNS,
    )

    _contact_operator_role(connection, role)
    allowed_updates = {
        "koinon_operator_delivery_contacts": {*OBSERVATION_COLUMNS, "revision"},
        "lattice_tenants": {"id"},
    }
    append = {"koinon_operator_delivery_contacts", *CONTACT_OPERATOR_APPEND_TABLES}
    required = [
        "koinon_operator_delivery_contacts",
        *(
            CONTACT_OPERATOR_READ_TABLES + CONTACT_OPERATOR_APPEND_TABLES
            if dependencies
            else ()
        ),
    ]
    for table in required:
        result = connection.execute(
            "SELECT has_table_privilege(%s,%s,'SELECT'),has_table_privilege(%s,%s,'INSERT'),"
            "has_table_privilege(%s,%s,'DELETE'),has_table_privilege(%s,%s,'TRUNCATE')",
            (role, "public." + table) * 4,
        ).fetchone()
        if result != (True, table in append, False, False):
            raise RuntimeError("Contact operator table privileges require review")
        columns = connection.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=%s",
            (table,),
        ).fetchall()
        for (name,) in columns:
            permitted = name in allowed_updates.get(table, set())
            actual = connection.execute(
                "SELECT has_column_privilege(%s,%s,%s,'UPDATE')",
                (role, "public." + table, name),
            ).fetchone()[0]
            if actual != permitted:
                raise RuntimeError("Contact operator column privileges require review")
    if dependencies:
        tables = connection.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname='public'"
        ).fetchall()
        for (table,) in tables:
            if table in required or not table.startswith(
                ("lattice_", "koinon_", "pyfly_", "firefly_", "canon_", "flyquery_")
            ):
                continue
            privileges = connection.execute(
                "SELECT has_table_privilege(%s,%s,'INSERT'),has_any_column_privilege(%s,%s,'UPDATE'),"
                "has_table_privilege(%s,%s,'DELETE'),has_table_privilege(%s,%s,'TRUNCATE')",
                (role, "public." + table) * 4,
            ).fetchone()
            if any(privileges):
                raise RuntimeError(
                    "Contact operator has unrelated runtime mutation privileges"
                )


def grant_contact_operator(connection, role, *, dependencies=True):
    from koinon.communications.contact_guards import (
        BINDING_COLUMNS,
        IMMUTABLE_COLUMNS,
        OBSERVATION_COLUMNS,
    )

    _contact_operator_role(connection, role)
    table, target = (
        sql.Identifier("koinon_operator_delivery_contacts"),
        sql.Identifier(role),
    )
    connection.execute(
        sql.SQL("REVOKE ALL ON TABLE public.{} FROM {}").format(table, target)
    )
    columns = sql.SQL(", ").join(
        sql.Identifier(name)
        for name in (
            *IMMUTABLE_COLUMNS,
            *OBSERVATION_COLUMNS,
            *BINDING_COLUMNS,
            "revision",
        )
    )
    for privilege in ("INSERT", "UPDATE"):
        connection.execute(
            sql.SQL("REVOKE {} ({}) ON TABLE public.{} FROM {}").format(
                sql.SQL(privilege), columns, table, target
            )
        )
    permitted = sql.SQL(", ").join(
        sql.Identifier(name) for name in (*OBSERVATION_COLUMNS, "revision")
    )
    connection.execute(
        sql.SQL("GRANT SELECT, INSERT, UPDATE ({}) ON TABLE public.{} TO {}").format(
            permitted, table, target
        )
    )
    if dependencies:
        for name in CONTACT_OPERATOR_READ_TABLES + CONTACT_OPERATOR_APPEND_TABLES:
            connection.execute(
                sql.SQL("GRANT SELECT ON TABLE public.{} TO {}").format(
                    sql.Identifier(name), target
                )
            )
        connection.execute(
            sql.SQL("GRANT UPDATE (id) ON TABLE public.lattice_tenants TO {}").format(
                target
            )
        )
        for name in CONTACT_OPERATOR_APPEND_TABLES:
            connection.execute(
                sql.SQL("GRANT INSERT ON TABLE public.{} TO {}").format(
                    sql.Identifier(name), target
                )
            )
    check_contact_operator(connection, role, dependencies=dependencies)


def provision(*, grants=False, check=False, contacts_operator_role=None):
    admin = make_url(os.environ["KOINON_MIGRATION_DATABASE_URL"])
    urls = [
        (make_url(os.environ[key]), bypass, prefixes) for key, bypass, prefixes in ROLES
    ]
    if len({url.username for url, _, _ in urls}) != len(urls):
        raise ValueError("Each runtime/control datasource requires a distinct role")
    if contacts_operator_role and contacts_operator_role in {
        url.username for url, _, _ in urls
    }:
        raise ValueError(
            "The contact operator must be distinct from every runtime/control role"
        )
    for url, _, _ in urls:
        if not url.username or not url.password or url.username == admin.username:
            raise ValueError(
                "Configure distinct runtime credentials separately from migration credentials"
            )
        if (url.host, url.port, url.database) != (
            admin.host,
            admin.port,
            admin.database,
        ):
            raise ValueError("This bootstrap targets one explicit application database")
    with psycopg.connect(
        admin.set(drivername="postgresql").render_as_string(hide_password=False)
    ) as connection:
        for url, bypass, prefixes in urls:
            row = connection.execute(
                "SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=%s",
                (url.username,),
            ).fetchone()
            if row is None and check:
                raise RuntimeError("Configured runtime role does not exist")
            if row is None:
                connection.execute(
                    sql.SQL(
                        "CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOCREATEDB "
                        "NOCREATEROLE NOREPLICATION {} PASSWORD {}"
                    ).format(
                        sql.Identifier(url.username),
                        sql.SQL("BYPASSRLS" if bypass else "NOBYPASSRLS"),
                        sql.Literal(url.password),
                    )
                )
            elif row != (False, bypass):
                raise RuntimeError(
                    "Existing role privileges differ; review explicitly rather than altering them"
                )
            if not check:
                connection.execute(
                    sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                        sql.Identifier(admin.database), sql.Identifier(url.username)
                    )
                )
                connection.execute(
                    sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(
                        sql.Identifier(url.username)
                    )
                )
            if grants and not check:
                for (name,) in connection.execute(
                    "SELECT tablename FROM pg_tables WHERE schemaname='public'"
                ):
                    if name.startswith(prefixes) and name not in {
                        "koinon_native_version",
                        "koinon_canon_version",
                        "koinon_structured_version",
                    }:
                        grant_table(
                            connection,
                            name,
                            url.username,
                            document_control=bypass and prefixes == ("canon_",),
                        )
                for (name,) in connection.execute(
                    "SELECT sequence_name FROM information_schema.sequences WHERE sequence_schema='public'"
                ):
                    if name.startswith(prefixes) and name not in {
                        "koinon_native_version",
                        "koinon_canon_version",
                        "koinon_structured_version",
                    }:
                        grant_sequence(connection, name, url.username)
            print(f"{url.username}: configured privilege boundary verified")
        if contacts_operator_role:
            if check:
                check_contact_operator(connection, contacts_operator_role)
            elif grants:
                grant_contact_operator(connection, contacts_operator_role)
            else:
                raise ValueError("Use --grant or --check with --contacts-operator-role")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--grant", action="store_true", help="Grant scoped DML after migrations"
    )
    parser.add_argument(
        "--check", action="store_true", help="Read privileges without changes"
    )
    parser.add_argument(
        "--contacts-operator-role",
        help="Existing distinct operator role for reviewed delivery contact changes",
    )
    args = parser.parse_args()
    provision(
        grants=args.grant,
        check=args.check,
        contacts_operator_role=args.contacts_operator_role,
    )
