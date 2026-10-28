# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from unittest.mock import MagicMock

from pyfly.core import Config


def test_native_document_storage_config_is_allowlisted_and_context_local(monkeypatch):
    from flycanon.core.configuration import CanonCoreConfiguration

    monkeypatch.setenv("FLYCANON_OBJECT_STORE_BACKEND", "localfs")
    first_registry, second_registry = MagicMock(), MagicMock()
    configuration = CanonCoreConfiguration()
    config = Config(
        {
            "koinon": {
                "storage": {
                    "documents": {
                        "backend": "s3",
                        "root": "/owned/documents",
                        "store_originals": False,
                        "s3_bucket": "owned-bucket",
                        "s3_prefix": "docs",
                        "s3_endpoint_url": "http://127.0.0.1:19000",
                        "s3_region": "us-east-1",
                        "database_url": "must-not-override",
                    }
                }
            }
        }
    )
    first = configuration.settings(MagicMock(), first_registry, config)
    second = configuration.settings(MagicMock(), second_registry)
    assert first.object_store_backend == "s3" and first.store_originals is False
    assert (
        first.object_store_localfs_root == "/owned/documents"
        and first.object_store_s3_bucket == "owned-bucket"
    )
    assert first.object_store_s3_prefix == "docs" and first.object_store_s3_region == "us-east-1"
    assert first.object_store_s3_endpoint_url == "http://127.0.0.1:19000"
    assert first.database_url != "must-not-override"
    assert first is not second and second.object_store_backend == "localfs"
    assert first._datasource_registry is first_registry and second._datasource_registry is second_registry
