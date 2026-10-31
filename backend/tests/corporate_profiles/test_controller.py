# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from pyfly.security.context import SecurityContext
from starlette.requests import Request

from koinon.corporate_profiles.dtos import CorporateProfileRefresh, CorporateProfileRefreshInput


@pytest.mark.asyncio
async def test_admin_refresh_forwards_ordinary_canonical_subject_string():
    path = Path(__file__).resolve().parents[2] / "src/koinon/corporate_profiles/controllers.py"
    spec = importlib.util.spec_from_file_location("isolated_corporate_profile_controller", path)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(
        sys.modules,
        {
            "koinon.corporate_profiles.security": SimpleNamespace(
                personal_identity=lambda *args, **kwargs: None
            ),
            "koinon.corporate_profiles.service": SimpleNamespace(CorporateProfileService=object),
        },
    ):
        spec.loader.exec_module(module)
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/tenants/north/organization/people/person/profile-refresh",
            "headers": [],
        }
    )
    request.state.security_context = SecurityContext(
        user_id="admin", attributes={"iss": "https://identity.example", "sub": "admin"}
    )
    result = CorporateProfileRefresh(tenant_id="north", status="queued")
    service = SimpleNamespace(refresh_person=AsyncMock(return_value=result))
    controller = module.CorporateProfilesController(service)
    assert (
        await controller.refresh_person(
            "north", "person", CorporateProfileRefreshInput(), request, workspace_id="workspace"
        )
        == result
    )
    service.refresh_person.assert_awaited_once_with(
        "https://identity.example|admin", "north", "person", workspace_id="workspace"
    )
