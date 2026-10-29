# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from unittest.mock import MagicMock

import pytest
from pyfly.core import Config

from koinon.knowledge.attachments.settings import AttachmentSettings
from koinon.knowledge.attachments.storage import AttachmentStorage
from koinon.operations.configuration import configure_storage
from koinon.storage.settings import AttachmentStorageProfile


@pytest.mark.parametrize("backend", ["azure", "gcs"])
@pytest.mark.parametrize("domain", ["documents", "structured", "attachments"])
def test_cloud_environment_profiles_bind_through_native_factories(domain, backend):
    prefix = {"documents": "DOCUMENT", "structured": "STRUCTURED", "attachments": "ATTACHMENT"}[
        domain
    ] + "_STORAGE_"
    settings = {
        "BACKEND": backend,
        "AZURE_ACCOUNT_URL": "https://owned.blob.core.windows.net",
        "AZURE_CONTAINER": "private-owned",
        "AZURE_PREFIX": "retained/docs",
        "GCS_BUCKET": "private-owned",
        "GCS_PROJECT": "owned-project",
        "GCS_PREFIX": "retained/docs",
        "GCS_ENDPOINT_URL": "http://127.0.0.1:4443",
        "REQUEST_TIMEOUT_SECONDS": "7",
        "MAX_OBJECT_BYTES": "1048576",
    }
    aliases = {prefix + key: value for key, value in settings.items()}
    values = {}
    configure_storage(values, lambda alias, path, default: aliases.get(alias, default))
    config = Config({"koinon": values})
    if domain == "attachments":
        profile = config.bind(AttachmentStorageProfile)
        store = AttachmentStorage(AttachmentSettings(), profile).configured().native
    elif domain == "documents":
        from flycanon.core.configuration import CanonCoreConfiguration
        from flycanon.core.services.storage.factory import build_object_store

        profile = CanonCoreConfiguration().settings(MagicMock(), MagicMock(), config)
        store = build_object_store(profile).native
    else:
        from flyquery.core.configuration import FlyqueryConfiguration
        from flyquery.core.services.storage.object_store_factory import build_object_store

        profile = FlyqueryConfiguration().settings(MagicMock(), MagicMock(), config)
        store = build_object_store(profile).native
    assert store.profile.backend == backend and store._client is None
    if backend == "azure":
        assert (
            store.profile.azure_container == "private-owned" and store.profile.azure_prefix == "retained/docs"
        )
    else:
        assert store.profile.gcs_bucket == "private-owned" and store.profile.gcs_project == "owned-project"
        assert store.profile.gcs_endpoint_url == "http://127.0.0.1:4443"
    assert store.profile.request_timeout_seconds == 7 and store.profile.max_object_bytes == 1048576


@pytest.mark.parametrize("backend", ["azure", "gcs"])
async def test_cloud_attachment_observation_keeps_health_unknown_without_client(monkeypatch, backend):
    from types import SimpleNamespace

    from sqlalchemy.engine import make_url

    import koinon.knowledge.attachments.capabilities as capabilities
    from koinon.knowledge.attachments.capabilities import AttachmentCapabilityService

    monkeypatch.setattr(capabilities, "find_spec", lambda name: object())
    settings = AttachmentSettings()
    storage = AttachmentStorage(
        settings,
        AttachmentStorageProfile(
            backend=backend,
            azure_account_url="https://owned.blob.core.windows.net",
            azure_container="owned-private",
            gcs_bucket="owned-private",
        ),
    )
    data = SimpleNamespace(registry=SimpleNamespace(primary=SimpleNamespace(url=make_url("sqlite://"))))
    service = AttachmentCapabilityService(None, data, storage, settings, SimpleNamespace(last_tick=None))
    descriptor = await service.deployment()
    assert descriptor.storage.configured is True and descriptor.storage.available is None
    assert storage.store.native._client is None
