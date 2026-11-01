# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect

from koinon.knowledge.external_reviews.entities import ExternalFileReviewRow, ExternalReviewRow
from koinon.knowledge.external_reviews.read_receipt_entities import ExternalReadReceiptRow


def test_0020_matches_private_review_entity_without_modifying_retained_rows(tmp_path):
    path = (
        Path(__file__).resolve().parents[4]
        / "deploy/migrations/native_versions/0020_external_knowledge_reviews.py"
    )
    spec = importlib.util.spec_from_file_location("external_review_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.revision == "koinon_0020_external_reviews"
    assert module.down_revision == "koinon_0019_org_branding"
    engine = create_engine("sqlite:///" + str(tmp_path / "migration.db"))
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE lattice_tenants (id TEXT PRIMARY KEY)")
        connection.exec_driver_sql("CREATE TABLE koinon_knowledge_intents (id TEXT PRIMARY KEY)")
        connection.exec_driver_sql("INSERT INTO koinon_knowledge_intents VALUES ('retained')")
        with Operations.context(MigrationContext.configure(connection)):
            module.upgrade()
        for entity in (ExternalReviewRow, ExternalFileReviewRow, ExternalReadReceiptRow):
            table = entity.__table__
            columns = {value["name"]: value for value in inspect(connection).get_columns(table.name)}
            introduced_later = (
                {"bulk_batch_id", "blob_reference_json"} if entity is ExternalFileReviewRow else set()
            )
            assert set(columns) == set(table.columns.keys()) - introduced_later
            assert all(
                columns[value.name]["nullable"] == value.nullable
                for value in table.columns
                if value.name not in introduced_later
            )
            assert {value["name"] for value in inspect(connection).get_indexes(table.name)} == {
                value.name for value in table.indexes
            }
        assert connection.exec_driver_sql("SELECT id FROM koinon_knowledge_intents").all() == [("retained",)]
    engine.dispose()
