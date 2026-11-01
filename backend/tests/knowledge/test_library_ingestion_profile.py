# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from unittest.mock import patch

import pytest
from koinon_storage.profile import LibraryIngestionProfile
from pyfly.core import Config

from koinon.knowledge.bulk.settings import BulkSettings
from koinon.knowledge.ingestion_profile import resolve_ingestion_profile


def test_native_profile_alias_drives_real_canon_parser_and_bulk_admission(monkeypatch):
    from flycanon.config import CanonSettings
    from flycanon.core.configuration import CanonCoreConfiguration

    monkeypatch.setenv("PYFLY_KOINON_KNOWLEDGE_INGESTION_RAW_MAX_BYTES", str(64 * 1024**2))
    values = resolve_ingestion_profile({})
    config = Config(values)
    bulk = config.bind(BulkSettings)
    with patch.object(CanonSettings, "bind_native_resources"):
        settings = CanonCoreConfiguration().settings(None, None, config)
    binary = CanonCoreConfiguration().binary_config(settings)
    assert settings.max_bytes == bulk.max_file_bytes == binary.max_bytes == 64 * 1024**2
    assert binary.max_uncompressed_bytes == 256 * 1024**2
    assert settings.file_child_rss_max_bytes == 768 * 1024**2
    assert bulk.max_batch_bytes == 512 * 1024**2


@pytest.mark.parametrize("value", [True, 1.5, "1.5", "-1", 128 * 1024**2 + 1])
def test_profile_rejects_invalid_or_unqualified_admission(value):
    with pytest.raises(ValueError):
        LibraryIngestionProfile.from_config(
            Config({"koinon": {"knowledge": {"ingestion": {"raw_max_bytes": value}}}})
        )


def test_standalone_document_settings_preserve_explicit_legacy_limit(monkeypatch):
    from flycanon.config import CanonSettings
    from flycanon.core.configuration import CanonCoreConfiguration

    monkeypatch.setenv("FLYCANON_MAX_BYTES", "1024")
    with patch.object(CanonSettings, "bind_native_resources"):
        settings = CanonCoreConfiguration().settings(None, None, Config({}))
    assert settings.max_bytes == 1024


def test_synchronous_endpoint_cannot_advertise_large_file_parser_capacity():
    from koinon.knowledge.service import KnowledgeSettings

    with pytest.raises(ValueError, match="queued Library"):
        KnowledgeSettings(max_upload_bytes=128 * 1024**2)


def test_mounted_library_profile_rejects_object_store_smaller_than_its_raw_limit():
    from flycanon.config import CanonSettings
    from flycanon.core.configuration import CanonCoreConfiguration

    config = Config(
        resolve_ingestion_profile({"koinon": {"storage": {"documents": {"max_object_bytes": 1024}}}})
    )
    with (
        patch.object(CanonSettings, "bind_native_resources"),
        pytest.raises(ValueError, match="storage object bound"),
    ):
        CanonCoreConfiguration().settings(None, None, config)
