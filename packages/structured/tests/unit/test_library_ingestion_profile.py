# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Mounted Koinon profile preserves exact byte caps; standalone settings retain legacy behavior."""

from unittest.mock import MagicMock

import pytest
from pyfly.core import Config


def test_mounted_profile_binds_native_settings_and_exact_odd_byte_limit():
    from flyquery.core.configuration import FlyqueryConfiguration
    from flyquery.core.services.ingestion.caps import FileTooLargeError, enforce_upload_cap

    configured = Config(
        {
            "koinon": {
                "knowledge": {
                    "ingestion": {
                        "raw_max_bytes": 1024**2 + 17,
                        "expanded_max_bytes": 4 * 1024**2,
                        "scratch_max_bytes": 8 * 1024**2,
                        "child_rss_max_bytes": 64 * 1024**2,
                        "wall_seconds": 9,
                    }
                }
            }
        }
    )
    registry = MagicMock()
    settings = FlyqueryConfiguration().settings(MagicMock(), registry, configured)
    assert settings.max_file_bytes == 1024**2 + 17 and settings.max_file_mb == 2
    assert settings.ingest_decompressed_max_bytes == 4 * 1024**2
    assert settings.ingest_scratch_max_bytes == 8 * 1024**2
    assert (
        settings.ingest_reader_rss_max_bytes == 64 * 1024**2 and settings.ingest_reader_timeout_seconds == 9
    )
    assert settings._datasource_registry is registry
    enforce_upload_cap(1024**2 + 17, 0, settings)
    with pytest.raises(FileTooLargeError) as failure:
        enforce_upload_cap(1024**2 + 18, 0, settings)
    assert failure.value.limit_bytes == 1024**2 + 17


def test_standalone_config_preserves_existing_legacy_environment(monkeypatch):
    from flyquery.core.configuration import FlyqueryConfiguration

    monkeypatch.setenv("FLYQUERY_MAX_FILE_MB", "73")
    monkeypatch.setenv("FLYQUERY_INGEST_READER_TIMEOUT_SECONDS", "41")
    settings = FlyqueryConfiguration().settings(MagicMock(), MagicMock(), Config({}))
    assert settings.max_file_mb == 73 and settings.max_file_bytes is None
    assert settings.ingest_reader_timeout_seconds == 41
