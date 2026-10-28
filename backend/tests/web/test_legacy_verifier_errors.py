# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from conftest import bearer
from pyfly.kernel import InvalidRequestException, PayloadTooLargeException
from starlette.requests import Request

from koinon.web.legacy_security import LegacyMembershipFilter, LegacyOperationPolicies


def test_registered_verifier_http_errors_preserve_specific_status_without_calling_domain(client):
    from flyquery.core.services.glossary.errors import GlossaryRevisionConflict, GlossaryRevisionRequired

    policies = client.native_app.state.context.get_bean(LegacyOperationPolicies)
    headers = {**bearer(), "X-Tenant-ID": "north", "X-Workspace-ID": client.workspace_id}
    for error, status in (
        (GlossaryRevisionRequired(), 428),
        (GlossaryRevisionConflict(), 409),
        (InvalidRequestException("Invalid glossary fields", code="INVALID_GLOSSARY_PAYLOAD"), 400),
        (PayloadTooLargeException("Glossary JSON exceeds 64 KiB", code="GLOSSARY_PAYLOAD_TOO_LARGE"), 413),
    ):

        async def verify(*args, failure=error):
            raise failure

        route = "/verifier-errors/" + str(status)
        policies.register("structured", "POST", route, verify, permission="catalog:write")
        response = client.post("/api/v1/structured" + route, headers=headers, json={})
        assert response.status_code == status, response.text
        assert response.headers["content-type"].startswith("application/problem+json")
        assert response.json()["code"] == error.code
    denied = client.post(
        "/api/v1/structured/verifier-errors/428",
        headers={**headers, **bearer("viewer")},
        json={},
    )
    assert denied.status_code == 403


async def test_unexpected_verifier_exception_is_not_translated_or_exposed(monkeypatch):
    from koinon.security.identity import RequestIdentity

    monkeypatch.setattr(
        "koinon.web.legacy_security.identity_from_request",
        lambda request: RequestIdentity("issuer|admin", True, "bearer"),
    )
    policies = LegacyOperationPolicies()
    verify = AsyncMock(side_effect=RuntimeError("Internal storage detail must not become a public problem"))
    policies.register("structured", "POST", "/glossary", verify, permission="catalog:write")
    catalog = SimpleNamespace(
        get=AsyncMock(return_value=SimpleNamespace(kind="workspace")), authorize=AsyncMock()
    )
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/structured/glossary",
            "headers": [(b"x-tenant-id", b"north"), (b"x-workspace-id", b"workspace")],
            "state": {},
            "app": SimpleNamespace(exception_handlers={}),
        }
    )
    following = AsyncMock()
    with pytest.raises(RuntimeError, match="Internal storage"):
        await LegacyMembershipFilter(catalog, policies).do_filter(request, following)
    following.assert_not_awaited()
