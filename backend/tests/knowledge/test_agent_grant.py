# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from importlib import import_module
from types import MappingProxyType, SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from starlette.requests import Request


@contextmanager
def _grant(domain, package):
    contexts = import_module(package + ".web.conventions.context")
    scope = "agent.sources:read" if domain == "canon" else "flyquery.datasets:read"
    path = "/api/v1/" + domain + "/agent/resource/native-id"
    context = contexts.TenantContext(
        tenant_id="north", workspace_id="native-workspace", actor="issuer|alice", correlation_id="correlation"
    )
    token = contexts.set_tenant_context(context)
    value = dict(
        domain=domain,
        method="GET",
        path=path,
        tenant_id="north",
        workspace_id="native-workspace",
        subject="issuer|alice",
        scopes=(scope,),
    )
    http = Request(
        {
            "type": "http",
            "method": "GET",
            "path": path,
            "headers": [],
            "query_string": b"",
            "state": {
                "legacy_tenant_context": context,
                "identity": SimpleNamespace(subject="issuer|alice"),
                "verified_legacy_agent_grant": MappingProxyType(value),
            },
        }
    )
    try:
        yield domain, package, scope, http, value, context
    finally:
        token.var.reset(token.token)


@pytest.fixture(params=[("canon", "flycanon"), ("structured", "flyquery")])
def grant(request):
    with _grant(*request.param) as value:
        yield value


@pytest.fixture
def document_grant():
    with _grant("canon", "flycanon") as value:
        yield value


@pytest.fixture
def structured_grant():
    with _grant("structured", "flyquery") as value:
        yield value


def test_exact_native_agent_grant_retains_trusted_context_without_synthetic_token_ids(grant):
    _, package, scope, request, _, context = grant
    verify = import_module(package + ".web.native_agent_grant").verified_agent_context
    result = verify(request, scope=scope)
    assert result is context and result.actor == "issuer|alice"
    assert not hasattr(result, "agent_token_id")
    request.scope["path"] = "/bff" + request.scope["path"]
    assert verify(request, scope=scope) is context


@pytest.mark.parametrize(
    "field,value",
    [
        ("domain", "other"),
        ("method", "POST"),
        ("path", "/different"),
        ("tenant_id", "south"),
        ("workspace_id", "foreign"),
        ("subject", "forged"),
        ("scopes", ("*",)),
        ("scopes", ()),
    ],
)
def test_present_but_mismatched_grants_are_denied_without_legacy_fallback(grant, field, value):
    _, package, scope, request, authority, _ = grant
    authority[field] = value
    denied = import_module(package + ".core.services.auth.agent_token_service").AgentScopeDenied
    verify = import_module(package + ".web.native_agent_grant").verified_agent_context
    with pytest.raises(denied):
        verify(request, scope=scope)


def test_native_grant_requires_identity_and_absence_preserves_standalone(grant):
    _, package, scope, request, _, _ = grant
    verify = import_module(package + ".web.native_agent_grant").verified_agent_context
    request.state.identity = SimpleNamespace(subject="issuer|other")
    denied = import_module(package + ".core.services.auth.agent_token_service").AgentScopeDenied
    with pytest.raises(denied):
        verify(request, scope=scope)
    del request.state.verified_legacy_agent_grant
    assert verify(request, scope=scope) is None


async def test_document_agent_helper_uses_exact_server_grant_without_token_database(document_grant):
    _, package, scope, request, _, context = document_grant
    verify = import_module(package + ".web.controllers.agent._helpers").verify_agent_token
    service = SimpleNamespace(verify=AsyncMock())
    assert await verify(request, service=service, scope=scope) is context
    service.verify.assert_not_awaited()


def test_active_database_scope_must_match_the_server_grant(grant):
    _, package, scope, request, _, context = grant
    module = import_module(package + ".web.conventions.context")
    token = module.set_tenant_context(context.model_copy(update={"workspace_id": "foreign"}))
    try:
        denied = import_module(package + ".core.services.auth.agent_token_service").AgentScopeDenied
        with pytest.raises(denied):
            import_module(package + ".web.native_agent_grant").verified_agent_context(request, scope=scope)
    finally:
        token.var.reset(token.token)


@pytest.mark.parametrize(
    "module,class_name,scope,dynamic",
    [
        ("datasets", "AgentDatasetsController", "flyquery.datasets:read", False),
        ("tables", "AgentTablesController", "flyquery.schema:read", False),
        ("query", "AgentQueryController", "flyquery.query:read", False),
        ("sql_execute", "AgentSqlExecuteController", "flyquery.sql:execute", False),
        ("relations", "AgentRelationsController", "flyquery.relations:read", False),
        ("examples", "AgentExamplesController", "flyquery.examples:read", True),
        ("glossary", "AgentGlossaryController", "flyquery.semantic:read", True),
        ("semantic_metrics", "AgentSemanticMetricsController", "flyquery.semantic:read", True),
        ("semantic_dimensions", "AgentSemanticDimensionsController", "flyquery.semantic:read", True),
        ("ingest_jobs", "AgentIngestJobsController", "flyquery.ingest:read", True),
        ("conversations", "AgentConversationsController", "flyquery.conversations:read", True),
    ],
)
async def test_each_structured_agent_controller_gate_consumes_the_exact_native_scope(
    structured_grant, module, class_name, scope, dynamic
):
    _, package, _, request, authority, _ = structured_grant
    authority["scopes"] = (scope,)
    cls = getattr(import_module(package + ".web.controllers.agent." + module + "_controller"), class_name)
    controller = object.__new__(cls)
    controller._token_service = SimpleNamespace(verify=AsyncMock())
    await controller._verify(request, scope) if dynamic else await controller._verify(request)
    controller._token_service.verify.assert_not_awaited()
