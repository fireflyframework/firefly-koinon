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
        }
    )
    receipt = table in {
        "canon_curated_heads",
        "canon_knowledge_commits",
        "canon_source_heads",
        "koinon_organization_chat_settings",
        "koinon_organization_branding",
        "koinon_organization_people",
        "koinon_organization_directory_settings",
        "koinon_organization_profile_mappings",
        "koinon_external_knowledge_reviews",
        "koinon_external_file_reviews",
        "koinon_mcp_oauth_clients",
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


def provision(*, grants=False, check=False):
    admin = make_url(os.environ["KOINON_MIGRATION_DATABASE_URL"])
    urls = [
        (make_url(os.environ[key]), bypass, prefixes) for key, bypass, prefixes in ROLES
    ]
    if len({url.username for url, _, _ in urls}) != len(urls):
        raise ValueError("Each runtime/control datasource requires a distinct role")
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--grant", action="store_true", help="Grant scoped DML after migrations"
    )
    parser.add_argument(
        "--check", action="store_true", help="Read privileges without changes"
    )
    args = parser.parse_args()
    provision(grants=args.grant, check=args.check)
