# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Product migration extensions preserve standalone history identities."""

import importlib.util
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


def test_document_product_extension_preserves_standalone_head():
    root = Path(__file__).resolve().parents[3]
    spec = importlib.util.spec_from_file_location("product_migrate", root / "deploy/migrate.py")
    assert spec is not None and spec.loader is not None
    deploy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(deploy)
    versions = root / "packages/canon/migrations/versions"
    standalone = Config()
    standalone.set_main_option("script_location", str(versions.parent))
    standalone.set_main_option("version_locations", str(versions))
    standalone.set_main_option("path_separator", "os")
    assert ScriptDirectory.from_config(standalone).get_heads() == ["0017_embedding_sets"]
    product = ScriptDirectory.from_config(deploy.history_config("canon", versions, None))
    assert product.get_heads() == ["0020_source_lineage"]
    assert product.get_revision("0018_index_provisioning").down_revision == "0017_embedding_sets"
    assert product.get_revision("0019_curated_knowledge").down_revision == "0018_index_provisioning"
    assert product.get_revision("0020_source_lineage").down_revision == "0019_curated_knowledge"


def test_structured_product_extension_preserves_standalone_head():
    root = Path(__file__).resolve().parents[3]
    spec = importlib.util.spec_from_file_location("product_migrate", root / "deploy/migrate.py")
    assert spec is not None and spec.loader is not None
    deploy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(deploy)
    versions = root / "packages/structured/migrations/versions"
    standalone = Config()
    standalone.set_main_option("script_location", str(versions.parent))
    standalone.set_main_option("version_locations", str(versions))
    standalone.set_main_option("path_separator", "os")
    assert ScriptDirectory.from_config(standalone).get_heads() == ["0015_versioned_embedding_sets"]
    product = ScriptDirectory.from_config(deploy.history_config("structured", versions, None))
    assert product.get_heads() == ["0019_consumer_context"]
    assert product.get_revision("0019_consumer_context").down_revision == "0018_bulk_operations"
    assert product.get_revision("0018_bulk_operations").down_revision == "0017_snapshot_coordinates"
    assert product.get_revision("0017_snapshot_coordinates").down_revision == "0016_immutable_file_lineage"
    assert (
        product.get_revision("0016_immutable_file_lineage").down_revision == "0015_versioned_embedding_sets"
    )
