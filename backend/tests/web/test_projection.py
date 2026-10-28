# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import pytest
from conftest import bearer
from pyfly.container import rest_controller
from pyfly.web import get_mapping, post_mapping, request_mapping
from starlette.requests import Request


@rest_controller
@request_mapping("/api/v1/probe")
class OriginalController:
    calls = 0

    @get_mapping("")
    async def get(self, request: Request) -> dict:
        OriginalController.calls += 1
        return {"subject": request.state.identity.subject, "tenant": request.state.verified_tenant_id}

    @post_mapping("")
    async def post(self, request: Request) -> dict:
        OriginalController.calls += 1
        return {"changed": True}


@rest_controller
@request_mapping("/api/v1/delegated-probe")
class DelegatingController:
    def __init__(self, delegate: OriginalController):
        self.delegate = delegate


def test_original_controller_dependencies_resolve_to_public_projection():
    from pyfly.context import ApplicationContext
    from pyfly.core import Config

    from koinon.web.projection import register_controller

    context = ApplicationContext(Config({}))
    public, browser = register_controller(context, OriginalController, "canon")
    delegated, _ = register_controller(context, DelegatingController, "canon")
    resolved = context.container.resolve(delegated)
    assert resolved.delegate is context.container.resolve(public)
    assert type(resolved.delegate) is public
    assert type(resolved.delegate) is not browser
    assert OriginalController.__pyfly_request_mapping__ == "/api/v1/probe"


@pytest.mark.parametrize("client", [OriginalController], indirect=True)
def test_original_metadata_preserved_and_membership_precedes_agent_tokens(client):
    assert OriginalController.__pyfly_request_mapping__ == "/api/v1/probe"
    OriginalController.calls = 0
    headers = {"X-Tenant-Id": "north", "X-Workspace-Id": client.workspace_id, "X-Agent-Token": "legacy-token"}
    url = "/api/v1/canon/probe"
    assert client.get(url, headers=headers).status_code == 401
    assert OriginalController.calls == 0
    assert client.get(url, headers={**headers, **bearer("outsider")}).status_code == 403
    assert OriginalController.calls == 0
    assert client.post(url, headers={**headers, **bearer("viewer")}).status_code == 403
    assert OriginalController.calls == 0
    assert client.get(url, headers={**headers, **bearer("viewer")}).status_code == 503
    assert OriginalController.calls == 0
    from koinon.web.legacy_security import LegacyOperationPolicies

    async def verified_no_resource_ids(request, identity, tenant, workspace, params):
        return None

    policies = client.native_app.state.context.get_bean(LegacyOperationPolicies)
    policies.register("canon", "GET", "/probe", verified_no_resource_ids)
    response = client.get(url, headers={**headers, **bearer("viewer")})
    assert response.status_code == 200, response.text
    assert response.json()["tenant"] == "north"
    assert OriginalController.calls == 1
    assert client.get("/api/v1/probe", headers=bearer()).status_code == 404


def test_projected_configuration_factory_names_do_not_mutate_original():
    from pyfly.container import bean, configuration

    from koinon.web.projection import _configuration

    @configuration
    class Original:
        @bean
        def settings(self) -> str:
            return "retained"

    projected = _configuration(Original, "canon")
    assert not hasattr(Original.settings, "__pyfly_bean_name__")
    assert projected.settings.__pyfly_bean_name__ == "canon.settings"
    assert projected().settings() == "retained"


@rest_controller
@request_mapping("/api/v1")
class OriginalDomainRoot:
    @get_mapping("")
    async def status(self) -> dict:
        return {"private": "must stay gated"}


@pytest.mark.parametrize("client", [OriginalDomainRoot], indirect=True)
def test_exact_domain_root_is_gated_like_nested_routes(client):
    response = client.get(
        "/api/v1/canon",
        headers={
            **bearer(),
            "X-Tenant-Id": "north",
            "X-Workspace-Id": client.workspace_id,
        },
    )
    assert response.status_code == 503
    assert response.json()["code"] == "LEGACY_OPERATION_UNQUALIFIED"


def test_configuration_preserves_already_qualified_bean_name():
    from pyfly.container import bean, configuration

    from koinon.web.projection import _configuration

    @configuration
    class NamedConfiguration:
        @bean(name="structured.sessions")
        def sessions(self) -> str:
            return "borrowed"

    projected = _configuration(NamedConfiguration, "structured")
    assert projected.sessions.__pyfly_bean_name__ == "structured.sessions"
    assert NamedConfiguration.sessions.__pyfly_bean_name__ == "structured.sessions"


def test_local_structured_registration_does_not_import_unselected_cloud_storage(monkeypatch):
    import importlib

    from pyfly.context import ApplicationContext
    from pyfly.core import Config

    from koinon.web.projection import register_optional_domain

    original = importlib.import_module

    def guarded(name, *args, **kwargs):
        if name.startswith("flyquery.core.services.storage.adapters."):
            raise AssertionError("Unselected storage adapters must remain lazy")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(importlib, "import_module", guarded)
    context = ApplicationContext(Config({}))
    assert register_optional_domain(context, "flyquery", "structured")["registered"] is True


@rest_controller
@request_mapping("/api/v1/business-error")
class OriginalBusinessController:
    @get_mapping("")
    async def denied(self):
        from flyquery.web.conventions.exceptions import InvalidRequest

        raise InvalidRequest("Use an allowed query")


@pytest.mark.parametrize("client", [(OriginalBusinessController, "structured")], indirect=True)
def test_preserved_business_exception_keeps_problem_status(client):
    from koinon.web.legacy_security import LegacyOperationPolicies

    async def verified(request, identity, tenant, workspace, params):
        return None

    client.native_app.state.context.get_bean(LegacyOperationPolicies).register(
        "structured",
        "GET",
        "/business-error",
        verified,
    )
    response = client.get(
        "/api/v1/structured/business-error",
        headers={
            **bearer(),
            "X-Tenant-Id": "north",
            "X-Workspace-Id": client.workspace_id,
        },
    )
    assert response.status_code == 422
    assert response.json()["code"] == "invalid_request"
    assert response.headers["content-type"].startswith("application/problem+json")
