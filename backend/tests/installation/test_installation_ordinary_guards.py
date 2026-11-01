# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import pytest
from test_service import assistants as assistants

from koinon.catalog.errors import AccessDenied


async def test_operator_audit_label_is_not_a_user_or_an_http_authority(assistants):
    service, _ = assistants
    with pytest.raises(AccessDenied):
        await service.save_provider(
            "system:installation",
            "north",
            {
                "name": "Untrusted",
                "kind": "ollama",
                "base_url": "http://127.0.0.1:11434/v1",
                "model_ids": ["model"],
            },
        )
    assert await service.providers.find_all(tenant_id="north") == []
