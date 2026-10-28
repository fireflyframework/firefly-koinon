# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from unittest.mock import MagicMock

from pyfly.core import Config


def test_native_structured_storage_config_preserves_falsey_values_and_environment(monkeypatch):
    from flyquery.core.configuration import FlyqueryConfiguration

    monkeypatch.setenv("FLYQUERY_OBJECT_STORE_BASE", "/environment/storage")
    configuration = FlyqueryConfiguration()
    first_registry, second_registry = MagicMock(), MagicMock()
    first = configuration.settings(
        MagicMock(),
        first_registry,
        Config(
            {
                "koinon": {
                    "storage": {
                        "structured": {
                            "backend": "s3",
                            "root": "/owned/structured",
                            "presign_ttl_seconds": 0,
                            "database_url": "must-not-override",
                        }
                    }
                }
            }
        ),
    )
    second = configuration.settings(MagicMock(), second_registry)
    assert first.object_store == "s3" and first.object_store_base == "/owned/structured"
    assert first.object_store_presign_ttl_s == 0 and first.database_url != "must-not-override"
    assert second.object_store_base == "/environment/storage"
    assert first is not second and first._datasource_registry is first_registry
