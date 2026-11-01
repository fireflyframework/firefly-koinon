# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import base64
from unittest.mock import MagicMock

import pytest
from pyfly.kernel import PayloadTooLargeException

from flycanon.config import CanonSettings
from flycanon.core.services.sources.url_fetcher import UrlFetcher
from flycanon.web.controllers.sources_controller import SourcesController, SubmitSourceJsonPayload


def controller(settings):
    return SourcesController(MagicMock(), MagicMock(), UrlFetcher(settings), MagicMock())


async def test_inline_predecode_guard_does_not_inherit_large_queued_file_limit():
    settings = CanonSettings(max_bytes=128 * 1024**2, inline_max_bytes=3)
    with pytest.raises(PayloadTooLargeException):
        await controller(settings)._resolve_payload_content(
            SubmitSourceJsonPayload(content_base64=base64.b64encode(b"four").decode())
        )


async def test_standalone_inline_and_url_limits_preserve_explicit_legacy_settings():
    settings = CanonSettings(max_bytes=4)
    value = await controller(settings)._resolve_payload_content(
        SubmitSourceJsonPayload(content_base64=base64.b64encode(b"four").decode())
    )
    assert value[0] == b"four" and UrlFetcher(settings).max_bytes == 4


def test_mounted_product_inline_limit_is_independent_of_queued_raw_limit():
    from unittest.mock import patch

    from pyfly.core import Config

    from flycanon.core.configuration import CanonCoreConfiguration

    with patch.object(CanonSettings, "bind_native_resources"):
        settings = CanonCoreConfiguration().settings(
            None, None, Config({"koinon": {"knowledge": {"ingestion": {"raw_max_bytes": 128 * 1024**2}}}})
        )
    assert settings.max_bytes == 128 * 1024**2
    assert settings.inline_max_bytes == UrlFetcher(settings).max_bytes == 32 * 1024**2
