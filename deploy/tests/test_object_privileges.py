# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Provisioning must preserve the same immutable boundaries as migrations."""

import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "object_privileges", Path(__file__).resolve().parents[1] / "provision_roles.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class Statements:
    def __init__(self):
        self.items = []

    def execute(self, statement):
        self.items.append(statement.as_string())


@pytest.mark.parametrize(
    "table,privileges",
    [
        ("pyfly_mcp_sessions", "SELECT,INSERT,UPDATE,DELETE"),
        ("pyfly_mcp_session_admission", "SELECT,INSERT,UPDATE"),
    ],
)
def test_mcp_metadata_roles_cannot_keep_ddl_or_admission_delete(table, privileges):
    connection = Statements()
    module.grant_table(connection, table, "example_runtime")
    assert connection.items == [
        f'REVOKE ALL ON TABLE public."{table}" FROM "example_runtime"',
        f'GRANT {privileges} ON TABLE public."{table}" TO "example_runtime"',
    ]


@pytest.mark.parametrize(
    "table",
    [
        "canon_source_artifacts",
        "canon_source_versions",
        "canon_source_extractions",
        "canon_source_parts",
        "canon_source_transform_steps",
        "canon_source_lineage_events",
        "koinon_chat_memory_manifests",
    ],
)
def test_source_receipts_cannot_gain_mutation_privileges_during_reprovisioning(table):
    connection = Statements()
    module.grant_table(connection, table, "example_runtime")
    assert connection.items == [
        f'REVOKE ALL ON TABLE public."{table}" FROM "example_runtime"',
        f'GRANT SELECT,INSERT ON TABLE public."{table}" TO "example_runtime"',
    ]


def test_source_head_allows_pointer_updates_but_cannot_be_deleted():
    connection = Statements()
    module.grant_table(connection, "canon_source_heads", "example_runtime")
    assert connection.items == [
        'REVOKE ALL ON TABLE public."canon_source_heads" FROM "example_runtime"',
        'GRANT SELECT,INSERT,UPDATE ON TABLE public."canon_source_heads" TO "example_runtime"',
    ]


@pytest.mark.parametrize(
    "table",
    [
        "koinon_bulk_batches",
        "koinon_bulk_items",
        "koinon_bulk_uploads",
        "koinon_bulk_quotas",
    ],
)
def test_bulk_prerequisite_tables_cannot_gain_delete_on_reprovisioning(table):
    connection = Statements()
    module.grant_table(connection, table, "example_runtime")
    assert connection.items == [
        f'REVOKE ALL ON TABLE public."{table}" FROM "example_runtime"',
        f'GRANT SELECT,INSERT,UPDATE ON TABLE public."{table}" TO "example_runtime"',
    ]


def test_organization_chat_setting_preserves_revision_history_on_reprovisioning():
    connection = Statements()
    module.grant_table(
        connection, "koinon_organization_chat_settings", "example_runtime"
    )
    assert connection.items == [
        'REVOKE ALL ON TABLE public."koinon_organization_chat_settings" FROM "example_runtime"',
        'GRANT SELECT,INSERT,UPDATE ON TABLE public."koinon_organization_chat_settings" TO "example_runtime"',
    ]


def test_organization_branding_reset_preserves_monotonic_revision_history():
    connection = Statements()
    module.grant_table(connection, "koinon_organization_branding", "example_runtime")
    assert connection.items == [
        'REVOKE ALL ON TABLE public."koinon_organization_branding" FROM "example_runtime"',
        'GRANT SELECT,INSERT,UPDATE ON TABLE public."koinon_organization_branding" TO "example_runtime"',
    ]


def test_outbox_publisher_cannot_read_or_reseed_delivery_sequence():
    connection = Statements()
    module.grant_sequence(
        connection, "canon_knowledge_outbox_deliveries_id_seq", "example_runtime"
    )
    assert connection.items == [
        'REVOKE ALL ON SEQUENCE public."canon_knowledge_outbox_deliveries_id_seq" FROM "example_runtime"',
        'GRANT USAGE ON SEQUENCE public."canon_knowledge_outbox_deliveries_id_seq" TO "example_runtime"',
    ]


@pytest.mark.parametrize(
    "table",
    [
        "koinon_organization_people",
        "koinon_organization_directory_settings",
        "koinon_organization_profile_mappings",
    ],
)
def test_organization_metadata_cannot_be_deleted_by_runtime_reprovisioning(table):
    connection = Statements()
    module.grant_table(connection, table, "example_runtime")
    assert connection.items == [
        f'REVOKE ALL ON TABLE public."{table}" FROM "example_runtime"',
        f'GRANT SELECT,INSERT,UPDATE ON TABLE public."{table}" TO "example_runtime"',
    ]


def test_bootstrap_runtime_can_only_select_and_activate_not_seed_or_rewrite_identity():
    from koinon.bootstrap.entities import ACTIVATION_COLUMNS, IMMUTABLE_COLUMNS

    connection = Statements()
    module.grant_table(
        connection, "koinon_bootstrap_identity_grants", "example_runtime"
    )
    assert len(connection.items) == 5
    assert connection.items[0].startswith("REVOKE ALL ON TABLE")
    for privilege, statement in zip(
        ("INSERT", "UPDATE"), connection.items[1:3], strict=True
    ):
        assert statement.startswith(f"REVOKE {privilege} (")
        assert all(
            f'"{name}"' in statement
            for name in (*IMMUTABLE_COLUMNS, *ACTIVATION_COLUMNS)
        )
    assert connection.items[3].startswith("GRANT SELECT ON TABLE")
    assert (
        connection.items[4]
        == 'GRANT UPDATE ("consumed_at", "consumed_subject", "membership_id") '
        'ON TABLE public."koinon_bootstrap_identity_grants" TO "example_runtime"'
    )
