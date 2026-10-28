# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from types import SimpleNamespace

import pytest
from pyfly.core import Config
from sqlalchemy.engine import make_url

from koinon.knowledge.attachments.capabilities import AttachmentCapabilityService
from koinon.knowledge.attachments.settings import AttachmentSettings
from koinon.knowledge.attachments.storage import AttachmentStorage
from koinon.storage.settings import AttachmentStorageProfile
from koinon.web.capabilities import CapabilitiesController, CapabilityRegistry


def service(storage, settings):
    data = SimpleNamespace(registry=SimpleNamespace(primary=SimpleNamespace(url=make_url("sqlite://"))))
    return AttachmentCapabilityService(None, data, storage, settings, SimpleNamespace(last_tick=None))


@pytest.mark.parametrize("installed", [True, False])
async def test_s3_configuration_and_health_are_distinct_without_creating_a_client(monkeypatch, installed):
    import koinon.knowledge.attachments.capabilities as capabilities

    original = capabilities.find_spec
    monkeypatch.setattr(
        capabilities,
        "find_spec",
        lambda name: (object() if installed else None) if name == "boto3" else original(name),
    )
    settings = AttachmentSettings()
    storage = AttachmentStorage(settings, AttachmentStorageProfile(backend="s3", s3_bucket="owned-test"))
    descriptor = await service(storage, settings).deployment()
    assert descriptor.storage.configured is installed
    assert descriptor.storage.available is (None if installed else False)
    assert storage.store._client is None


async def test_legacy_local_storage_reports_configured_and_checked(tmp_path):
    settings = AttachmentSettings(storage_root=str(tmp_path / "private"))
    descriptor = await service(AttachmentStorage(settings), settings).deployment()
    assert descriptor.storage.configured is True and descriptor.storage.available is True


async def test_configured_unknown_storage_permits_attempt_with_observed_database_and_worker(monkeypatch):
    from unittest.mock import AsyncMock

    from koinon.knowledge.attachments.dtos import AttachmentCapabilities

    limits = {
        name: getattr(AttachmentSettings(), name)
        for name in (
            "max_file_bytes",
            "max_image_bytes",
            "max_selected",
            "max_thread_files",
            "max_thread_bytes",
            "extraction_timeout_seconds",
            "ttl_seconds",
        )
    }
    descriptor = AttachmentCapabilities.model_validate(
        {
            "storage": {"configured": True, "available": None, "reason": "Provider unverified"},
            "database": {"available": True, "reason": "Checked"},
            "extraction": {"available": True, "reason": "Heartbeat observed"},
            "limits": {**limits, "max_model_text_chars": 24000, "max_model_binary_bytes": 16777216},
            "formats": [],
            "promotion": {},
        }
    )
    monkeypatch.setattr("koinon.web.capabilities.database_ready", AsyncMock(return_value=True))
    provider = SimpleNamespace(get=lambda: SimpleNamespace(deployment=AsyncMock(return_value=descriptor)))
    result = await CapabilitiesController(Config({}), None, CapabilityRegistry(), provider).capabilities()
    assert next(feature for feature in result["features"] if feature["id"] == "attachments")["available"]
    assert result["attachments"]["storage"]["available"] is None
