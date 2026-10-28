# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from pyfly.core import Config
from pyfly.kernel import ServiceUnavailableException

from koinon.knowledge.attachments.dtos import AttachmentCapabilities
from koinon.web.capabilities import CapabilitiesController, CapabilityRegistry


def descriptor(extraction=None):
    return AttachmentCapabilities.model_validate(
        {
            "storage": {"available": True, "reason": "Checked"},
            "database": {"available": True, "reason": "Checked"},
            "extraction": {"available": extraction, "reason": "Observed" if extraction else "Unknown"},
            "limits": {
                "max_file_bytes": 20971520,
                "max_image_bytes": 8388608,
                "max_selected": 10,
                "max_thread_files": 100,
                "max_thread_bytes": 134217728,
                "max_model_text_chars": 24000,
                "max_model_binary_bytes": 16777216,
                "extraction_timeout_seconds": 60,
                "ttl_seconds": 86400,
            },
            "formats": [],
            "promotion": {},
        }
    )


async def test_global_descriptor_is_late_and_never_creates_or_authorizes_a_thread(monkeypatch):
    monkeypatch.setattr("koinon.web.capabilities.database_ready", AsyncMock(return_value=True))
    service = SimpleNamespace(
        deployment=AsyncMock(return_value=descriptor()),
        for_thread=AsyncMock(side_effect=AssertionError("No thread is selected")),
    )
    provider = SimpleNamespace(get=Mock(return_value=service))
    controller = CapabilitiesController(Config({}), SimpleNamespace(), CapabilityRegistry(), provider)
    provider.get.assert_not_called()
    result = await controller.capabilities()
    assert result["attachments"]["extraction"]["available"] is None
    assert result["attachments"]["limits"]["max_selected"] == 10
    assert not next(feature for feature in result["features"] if feature["id"] == "attachments")["available"]
    provider.get.assert_called_once()
    service.for_thread.assert_not_awaited()


async def test_observed_worker_and_storage_are_required_before_global_available(monkeypatch):
    monkeypatch.setattr("koinon.web.capabilities.database_ready", AsyncMock(return_value=True))
    service = SimpleNamespace(deployment=AsyncMock(return_value=descriptor(True)))
    controller = CapabilitiesController(
        Config({}), SimpleNamespace(), CapabilityRegistry(), SimpleNamespace(get=lambda: service)
    )
    result = await controller.capabilities()
    assert next(feature for feature in result["features"] if feature["id"] == "attachments")["available"]


@pytest.mark.parametrize(
    "adapter",
    [
        None,
        SimpleNamespace(
            deployment=AsyncMock(
                side_effect=ServiceUnavailableException("Private configuration detail must not be exposed")
            )
        ),
    ],
)
async def test_missing_or_unconfigured_adapter_is_safely_unavailable(monkeypatch, adapter):
    monkeypatch.setattr("koinon.web.capabilities.database_ready", AsyncMock(return_value=True))
    controller = CapabilitiesController(
        Config({}), SimpleNamespace(), CapabilityRegistry(), SimpleNamespace(get=lambda: adapter)
    )
    result = await controller.capabilities()
    assert "attachments" not in result
    feature = next(value for value in result["features"] if value["id"] == "attachments")
    assert feature["available"] is False and "configuration detail" not in feature["reason"]
