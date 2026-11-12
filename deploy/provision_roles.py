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


EMAIL_RECOVERY_TABLES = (
    "koinon_welcome_recoveries",
    "koinon_email_provider_bindings",
    "koinon_email_operation_inspections",
    "koinon_email_operation_observations",
)


def grant_table(connection, table, role, *, document_control=False):
    if table == "koinon_content_structure_publications":
        from koinon.integrations.content_sources.structure_publication_guards import (
            READ_ENTRYPOINTS,
        )

        target, relation = sql.Identifier(role), sql.Identifier(table)
        connection.execute(
            sql.SQL("REVOKE ALL ON TABLE public.{} FROM {}").format(relation, target)
        )
        columns = connection.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name=%s",
            (table,),
        ).fetchall()
        connection.execute(
            sql.SQL("REVOKE ALL ({}) ON TABLE public.{} FROM {}").format(
                sql.SQL(",").join(sql.Identifier(column) for (column,) in columns),
                relation,
                target,
            )
        )
        connection.execute(
            sql.SQL("GRANT SELECT ON TABLE public.{} TO {}").format(relation, target)
        )
        for signature in READ_ENTRYPOINTS:
            connection.execute(
                sql.SQL("GRANT EXECUTE ON FUNCTION public.{} TO {}").format(
                    sql.SQL(signature), target
                )
            )
        return
    if table in {"koinon_source_account_operations", "koinon_source_account_waiters"}:
        target, relation = sql.Identifier(role), sql.Identifier(table)
        connection.execute(
            sql.SQL("REVOKE ALL ON TABLE public.{} FROM {}").format(relation, target)
        )
        connection.execute(
            sql.SQL(
                "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.{} TO {}"
            ).format(relation, target)
        )
        return
    if table in RELEASE_PROOF_TABLES:
        target, relation = sql.Identifier(role), sql.Identifier(table)
        connection.execute(
            sql.SQL("REVOKE ALL ON TABLE public.{} FROM {}").format(relation, target)
        )
        columns = connection.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND "
            "table_name=%s",
            (table,),
        ).fetchall()
        connection.execute(
            sql.SQL("REVOKE ALL ({}) ON TABLE public.{} FROM {}").format(
                sql.SQL(",").join(sql.Identifier(column) for (column,) in columns),
                relation,
                target,
            )
        )
        connection.execute(
            sql.SQL("GRANT SELECT ON TABLE public.{} TO {}").format(relation, target)
        )
        if table == "koinon_answer_release_proofs":
            connection.execute(
                sql.SQL(
                    "GRANT EXECUTE ON FUNCTION public.koinon_compare_release_proofs(jsonb) TO {}"
                ).format(target)
            )
        return
    if table in {
        "koinon_content_mapping_validations",
        "koinon_content_mapping_validation_entries",
    }:
        target, relation = sql.Identifier(role), sql.Identifier(table)
        connection.execute(
            sql.SQL("REVOKE ALL ON TABLE public.{} FROM {}").format(relation, target)
        )
        connection.execute(
            sql.SQL(
                "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.{} TO {}"
            ).format(relation, target)
        )
        # Row guards retain live recovery identities and require fenced payload cleanup.
        # TRUNCATE and schema ownership are deliberately not granted.
        return
    if table == "koinon_content_publication_transactions":
        connection.execute(
            sql.SQL("REVOKE ALL ON TABLE public.{} FROM {}").format(
                sql.Identifier(table), sql.Identifier(role)
            )
        )
        connection.execute(
            sql.SQL(
                "GRANT EXECUTE ON FUNCTION public.koinon_open_source_publication(text,jsonb) TO {}"
            ).format(sql.Identifier(role))
        )
        return
    if table in {
        "koinon_catalog_history_identities",
        "koinon_catalog_history_edges",
        "lattice_audit",
    }:
        target, relation = sql.Identifier(role), sql.Identifier(table)
        connection.execute(
            sql.SQL("REVOKE ALL ON TABLE public.{} FROM {}").format(relation, target)
        )
        columns = connection.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name=%s",
            (table,),
        ).fetchall()
        connection.execute(
            sql.SQL("REVOKE ALL ({}) ON TABLE public.{} FROM {}").format(
                sql.SQL(",").join(sql.Identifier(column) for (column,) in columns),
                relation,
                target,
            )
        )
        privileges = "SELECT, INSERT" if table == "lattice_audit" else "SELECT"
        connection.execute(
            sql.SQL("GRANT {} ON TABLE public.{} TO {}").format(
                sql.SQL(privileges), relation, target
            )
        )
        return
    if table in {
        "koinon_content_connections",
        "koinon_content_authorizations",
        "koinon_content_mappings",
        "koinon_content_objects",
        "koinon_content_imports",
        "koinon_content_publication_baselines",
        "koinon_content_publication_targets",
        "koinon_content_policies",
        "koinon_content_sync_states",
        "koinon_content_sync_runs",
        "koinon_content_sync_work",
        "koinon_content_sync_observations",
        "koinon_content_folder_bindings",
        "koinon_content_folder_publications",
        "koinon_content_imported_assets",
        "koinon_content_imported_versions",
        "koinon_content_reader_sets",
        "koinon_content_reader_selections",
        "koinon_content_reader_operations",
        "koinon_content_control_operations",
        "koinon_content_policy_operations",
        "flyquery_metadata_provenance",
    }:
        target, relation = sql.Identifier(role), sql.Identifier(table)
        connection.execute(
            sql.SQL("REVOKE ALL ON TABLE public.{} FROM {}").format(relation, target)
        )
        columns = connection.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name=%s",
            (table,),
        ).fetchall()
        connection.execute(
            sql.SQL("REVOKE ALL ({}) ON TABLE public.{} FROM {}").format(
                sql.SQL(",").join(sql.Identifier(column) for (column,) in columns),
                relation,
                target,
            )
        )
        connection.execute(
            sql.SQL("GRANT SELECT, INSERT ON TABLE public.{} TO {}").format(
                relation, target
            )
        )
        if table in {
            "koinon_content_publication_targets",
            "koinon_content_sync_observations",
            "koinon_content_imported_assets",
            "koinon_content_imported_versions",
            "koinon_content_folder_publications",
            "koinon_content_reader_selections",
            "koinon_content_reader_operations",
            "koinon_content_control_operations",
            "koinon_content_policy_operations",
            "flyquery_metadata_provenance",
        }:
            return
        update = (
            "UPDATE(receipt_json,committed_at)"
            if table == "koinon_content_imports"
            else "UPDATE"
        )
        if table == "koinon_content_publication_baselines":
            update = "UPDATE(descriptor_json,acknowledgement_json)"
            connection.execute(
                sql.SQL(
                    "GRANT EXECUTE ON FUNCTION public.koinon_open_source_publication(text,jsonb),"
                    " public.koinon_publication_current(text,text) TO {}"
                ).format(target)
            )
        if table == "koinon_content_policies":
            update = "UPDATE(accepted_by,accepted_session_hash,accepted_operation_id,accepted_at)"
        connection.execute(
            sql.SQL("GRANT {} ON TABLE public.{} TO {}").format(
                sql.SQL(update), relation, target
            )
        )
        return
    if table in {
        "canon_readiness_generations",
        "canon_readiness_changes",
        "canon_readiness_pending",
        "koinon_knowledge_readiness_generations",
        "koinon_knowledge_readiness_changes",
        "koinon_knowledge_readiness_pending",
    }:
        target, relation = sql.Identifier(role), sql.Identifier(table)
        connection.execute(
            sql.SQL("REVOKE ALL ON TABLE public.{} FROM {}").format(relation, target)
        )
        columns = connection.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name=%s",
            (table,),
        ).fetchall()
        connection.execute(
            sql.SQL("REVOKE ALL ({}) ON TABLE public.{} FROM {}").format(
                sql.SQL(",").join(sql.Identifier(column) for (column,) in columns),
                relation,
                target,
            )
        )
        if table.endswith("_pending"):
            return
        connection.execute(
            sql.SQL("GRANT SELECT ON TABLE public.{} TO {}").format(relation, target)
        )
        if table.endswith("_generations"):
            connection.execute(
                sql.SQL("GRANT UPDATE(fence) ON TABLE public.{} TO {}").format(
                    relation, target
                )
            )
        if table == "canon_readiness_generations":
            connection.execute(
                sql.SQL(
                    "GRANT EXECUTE ON FUNCTION public.koinon_ensure_canon_readiness(text) TO {}"
                ).format(target)
            )
        if table == "koinon_knowledge_readiness_generations":
            connection.execute(
                sql.SQL(
                    "GRANT EXECUTE ON FUNCTION public.koinon_lock_knowledge_readiness(text,bigint) TO {}"
                ).format(target)
            )
        return
    if table in {
        "koinon_knowledge_mode_index_attempts",
        "koinon_knowledge_mode_index_resolutions",
    }:
        target, relation = sql.Identifier(role), sql.Identifier(table)
        connection.execute(
            sql.SQL("REVOKE ALL ON TABLE public.{} FROM {}").format(relation, target)
        )
        columns = connection.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name=%s",
            (table,),
        ).fetchall()
        connection.execute(
            sql.SQL("REVOKE ALL ({}) ON TABLE public.{} FROM {}").format(
                sql.SQL(",").join(sql.Identifier(column) for (column,) in columns),
                relation,
                target,
            )
        )
        connection.execute(
            sql.SQL("GRANT SELECT, INSERT ON TABLE public.{} TO {}").format(
                relation, target
            )
        )
        if table.endswith("_resolutions"):
            connection.execute(
                sql.SQL(
                    "GRANT UPDATE(status,revision,updated_at) ON TABLE public.{} TO {}"
                ).format(relation, target)
            )
        return
    if table in EMAIL_RECOVERY_TABLES:
        target = sql.Identifier(role)
        relation = sql.Identifier(table)
        connection.execute(
            sql.SQL("REVOKE ALL ON TABLE public.{} FROM {}").format(relation, target)
        )
        names = connection.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name=%s ORDER BY ordinal_position",
            (table,),
        ).fetchall()
        if not names:
            raise RuntimeError(
                "Apply the email recovery migration before provisioning its privileges"
            )
        columns = sql.SQL(", ").join(sql.Identifier(name) for (name,) in names)
        connection.execute(
            sql.SQL("REVOKE UPDATE ({}) ON TABLE public.{} FROM {}").format(
                columns, relation, target
            )
        )
        connection.execute(
            sql.SQL("GRANT SELECT, INSERT ON TABLE public.{} TO {}").format(
                relation, target
            )
        )
        return
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
            "koinon_welcome_recoveries",
            "koinon_email_provider_bindings",
            "koinon_email_operation_inspections",
            "koinon_email_operation_observations",
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
    publisher = name.startswith("canon_knowledge_outbox_") or name in {
        "koinon_source_account_fence_seq",
        "koinon_source_account_ticket_seq",
    }
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
    "koinon_bootstrap_contacts",
    "koinon_communication_policies",
)
CONTACT_OPERATOR_APPEND_TABLES = (
    "lattice_audit",
    "koinon_communication_outbox",
    "koinon_welcome_recoveries",
    "koinon_email_provider_bindings",
    "koinon_email_operation_inspections",
    "koinon_email_operation_observations",
)


def _contact_operator_role(connection, role):
    flags = connection.execute(
        "SELECT rolsuper,rolbypassrls,rolcreaterole,rolcreatedb,rolreplication,rolinherit "
        "FROM pg_roles WHERE rolname=%s",
        (role,),
    ).fetchone()
    memberships = connection.execute(
        "SELECT 1 FROM pg_auth_members m JOIN pg_roles r ON r.oid=m.member WHERE r.rolname=%s LIMIT 1",
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
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name=%s",
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


RELEASE_PROOF_TABLES = (
    "koinon_answer_release_proofs",
    "koinon_answer_release_proof_pins",
    "koinon_answer_release_proof_sources",
    "koinon_answer_release_projection_jobs",
)
RELEASE_PROOF_ENTRYPOINTS = {
    "publisher": (
        "koinon_capture_release_proof(text)",
        "koinon_publish_release_proof(text,text,text,integer)",
    ),
    "maintenance": (
        "koinon_capture_release_proof(text)",
        "koinon_prepare_release_backfill(text,text,text,integer)",
        "koinon_backfill_release_proof(text,text,text,text,integer)",
        "koinon_claim_release_projection(text,text,text)",
        "koinon_release_projection_candidates(text,text,integer,integer)",
        "koinon_checkpoint_release_projection(text,text,integer,text,timestamptz,text)",
    ),
    "api": (),
}


def grant_release_proof_role(connection, role, *, kind, check=False):
    """Grant explicit existing process identities, never create credentials here."""
    if kind not in RELEASE_PROOF_ENTRYPOINTS:
        raise ValueError("Unknown answer proof process kind")
    row = connection.execute(
        "SELECT "
        "rolcanlogin,rolsuper,rolinherit,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls FROM "
        "pg_roles WHERE rolname=%s",
        (role,),
    ).fetchone()
    if row != (True, False, False, False, False, False, False):
        raise RuntimeError(
            "Proof process requires an existing ordinary LOGIN NOINHERIT role"
        )
    if connection.execute(
        "SELECT EXISTS(SELECT FROM pg_auth_members WHERE roleid=(SELECT oid FROM pg_roles WHERE "
        "rolname=%s) OR member=(SELECT oid FROM pg_roles WHERE rolname=%s))",
        (role, role),
    ).fetchone()[0]:
        raise RuntimeError(
            "Proof process roles must be isolated from SET ROLE and inherited privileges"
        )
    target = sql.Identifier(role)
    allowed = set(RELEASE_PROOF_ENTRYPOINTS[kind]) | {
        "koinon_compare_release_proofs(jsonb)"
    }
    from koinon.answers.release_proof_guards import FUNCTIONS

    if not check:
        for table in RELEASE_PROOF_TABLES:
            grant_table(connection, table, role)
        connection.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(target))
        for signature, _ in FUNCTIONS:
            connection.execute(
                sql.SQL("REVOKE ALL ON FUNCTION public.{} FROM {}").format(
                    sql.SQL(signature), target
                )
            )
            if signature in allowed:
                connection.execute(
                    sql.SQL("GRANT EXECUTE ON FUNCTION public.{} TO {}").format(
                        sql.SQL(signature), target
                    )
                )
        if kind == "maintenance":
            for table in (
                "koinon_chat_threads",
                "koinon_chat_runs",
                "koinon_chat_messages",
                "koinon_chat_tool_results",
                "koinon_chat_events",
            ):
                connection.execute(
                    sql.SQL("GRANT SELECT ON TABLE public.{} TO {}").format(
                        sql.Identifier(table), target
                    )
                )
    for signature, _ in FUNCTIONS:
        actual = connection.execute(
            "SELECT has_function_privilege(%s,%s,'EXECUTE')",
            (role, "public." + signature),
        ).fetchone()[0]
        if actual != (signature in allowed):
            raise RuntimeError(
                "Proof entrypoint privileges do not match the configured process"
            )
    for table in RELEASE_PROOF_TABLES:
        for privilege in ("INSERT", "UPDATE", "DELETE", "TRUNCATE", "TRIGGER"):
            if connection.execute(
                "SELECT has_table_privilege(%s,%s,%s)",
                (role, "public." + table, privilege),
            ).fetchone()[0]:
                raise RuntimeError("Proof process has direct table mutation privileges")
        if connection.execute(
            "SELECT EXISTS(SELECT FROM information_schema.columns WHERE table_schema='public' AND "
            "table_name=%s AND "
            "(has_column_privilege(%s,table_schema||'.'||table_name,column_name,'INSERT') OR "
            "has_column_privilege(%s,table_schema||'.'||table_name,column_name,'UPDATE')))",
            (table, role, role),
        ).fetchone()[0]:
            raise RuntimeError("Proof process has direct column mutation privileges")


def grant_source_structure_role(connection, role, *, worker=False, check=False):
    """Apply the exact structural interface to an existing isolated process role."""
    from koinon.integrations.content_sources.structure_publication_guards import (
        ALL_SIGNATURES,
        ENTRYPOINTS,
        READ_ENTRYPOINTS,
        TABLE,
    )

    flags = connection.execute(
        "SELECT rolcanlogin,rolsuper,rolinherit,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls "
        "FROM pg_roles WHERE rolname=%s",
        (role,),
    ).fetchone()
    membership = connection.execute(
        "SELECT EXISTS(SELECT FROM pg_auth_members WHERE roleid=(SELECT oid FROM pg_roles WHERE rolname=%s) "
        "OR member=(SELECT oid FROM pg_roles WHERE rolname=%s))",
        (role, role),
    ).fetchone()[0]
    if flags != (True, False, False, False, False, False, False) or membership:
        raise ValueError(
            "Structural source process requires an isolated ordinary LOGIN NOINHERIT role"
        )
    allowed = set(READ_ENTRYPOINTS) | (set(ENTRYPOINTS) if worker else set())
    target = sql.Identifier(role)
    if not check:
        grant_table(connection, TABLE, role)
        connection.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(target))
        for signature in ALL_SIGNATURES:
            connection.execute(
                sql.SQL("REVOKE ALL ON FUNCTION public.{} FROM {}").format(
                    sql.SQL(signature), target
                )
            )
            if signature in allowed:
                connection.execute(
                    sql.SQL("GRANT EXECUTE ON FUNCTION public.{} TO {}").format(
                        sql.SQL(signature), target
                    )
                )
    for signature in ALL_SIGNATURES:
        actual = connection.execute(
            "SELECT has_function_privilege(%s,%s,'EXECUTE')",
            (role, "public." + signature),
        ).fetchone()[0]
        if actual != (signature in allowed):
            raise ValueError(
                "Structural source entrypoint privileges do not match the configured process"
            )
    for privilege in (
        "INSERT",
        "UPDATE",
        "DELETE",
        "TRUNCATE",
        "TRIGGER",
        "REFERENCES",
    ):
        if connection.execute(
            "SELECT has_table_privilege(%s,%s,%s)", (role, "public." + TABLE, privilege)
        ).fetchone()[0]:
            raise ValueError("Structural proof table mutation must remain private")
    if connection.execute(
        "SELECT EXISTS(SELECT FROM information_schema.columns WHERE table_schema='public' "
        "AND table_name=%s AND (has_column_privilege(%s,table_schema||'.'||table_name,column_name,'INSERT') "
        "OR has_column_privilege(%s,table_schema||'.'||table_name,column_name,'UPDATE') "
        "OR has_column_privilege(%s,table_schema||'.'||table_name,column_name,'REFERENCES')))",
        (TABLE, role, role, role),
    ).fetchone()[0]:
        raise ValueError("Structural proof column mutation must remain private")


def proof_process_urls(publisher_role, maintenance_role):
    """Use only explicitly supplied private process credentials, never API credentials."""
    publisher = os.environ.get("KOINON_ANSWER_PUBLISHER_DATABASE_URL")
    maintenance = os.environ.get("KOINON_ANSWER_MAINTENANCE_DATABASE_URL")
    if bool(publisher) != bool(maintenance):
        raise ValueError(
            "Configure both answer publisher and maintenance database URLs"
        )
    if not publisher:
        return [], publisher_role, maintenance_role
    try:
        urls = [make_url(publisher), make_url(maintenance)]
    except Exception:
        raise ValueError(
            "Invalid answer proof process connection configuration"
        ) from None
    if (
        publisher_role
        and publisher_role != urls[0].username
        or maintenance_role
        and maintenance_role != urls[1].username
    ):
        raise ValueError("Configured answer proof role identity differs from its URL")
    if any(url.get_backend_name() != "postgresql" for url in urls):
        raise ValueError("Answer proof processes require PostgreSQL")
    return (
        [(urls[0], False, ROLES[0][2]), (urls[1], False, ())],
        urls[0].username,
        urls[1].username,
    )


def provision(
    *,
    grants=False,
    check=False,
    contacts_operator_role=None,
    answer_publisher_role=None,
    answer_maintenance_role=None,
):
    admin = make_url(os.environ["KOINON_MIGRATION_DATABASE_URL"])
    urls = [
        (make_url(os.environ[key]), bypass, prefixes) for key, bypass, prefixes in ROLES
    ]
    process_urls, answer_publisher_role, answer_maintenance_role = proof_process_urls(
        answer_publisher_role, answer_maintenance_role
    )
    if len({url.username for url, _, _ in urls}) != len(urls):
        raise ValueError("Each runtime/control datasource requires a distinct role")
    if contacts_operator_role and contacts_operator_role in {
        url.username for url, _, _ in urls
    }:
        raise ValueError(
            "The contact operator must be distinct from every runtime/control role"
        )
    proof_roles = [
        role for role in (answer_publisher_role, answer_maintenance_role) if role
    ]
    if len(set(proof_roles)) != len(proof_roles) or set(proof_roles) & {
        url.username for url, _, _ in urls
    }:
        raise ValueError(
            "Answer publisher and maintenance must be distinct from API and each other"
        )
    urls.extend(process_urls)
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
        for role, kind in (
            (answer_publisher_role, "publisher"),
            (answer_maintenance_role, "maintenance"),
        ):
            if role:
                if not grants and not check:
                    if process_urls:
                        continue  # Role creation precedes the additive schema migration.
                    raise ValueError("Use --grant or --check with answer proof roles")
                grant_release_proof_role(connection, role, kind=kind, check=check)
        if proof_roles and (grants or check):
            grant_release_proof_role(
                connection, urls[0][0].username, kind="api", check=check
            )
            if connection.execute(
                "SELECT to_regclass('public.koinon_content_structure_publications')"
            ).fetchone()[0]:
                grant_source_structure_role(
                    connection, urls[0][0].username, check=check
                )
                for role, worker in (
                    (answer_publisher_role, True),
                    (answer_maintenance_role, False),
                ):
                    if role:
                        grant_source_structure_role(
                            connection, role, worker=worker, check=check
                        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--grant", action="store_true", help="Grant scoped DML after migrations"
    )
    parser.add_argument(
        "--check", action="store_true", help="Read privileges without changes"
    )
    parser.add_argument(
        "--answer-publisher-role", help="Existing isolated trusted worker role"
    )
    parser.add_argument(
        "--answer-maintenance-role", help="Existing isolated trusted maintenance role"
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
        answer_publisher_role=args.answer_publisher_role,
        answer_maintenance_role=args.answer_maintenance_role,
    )
