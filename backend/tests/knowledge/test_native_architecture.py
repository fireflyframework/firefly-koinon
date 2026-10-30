# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pyfly.container import Container
from pyfly.container.exceptions import NoUniqueBeanError

from koinon.knowledge.adapters import NativeDomains


class NativePort:
    pass


class FirstNative(NativePort):
    pass


class SecondNative(NativePort):
    pass


def test_native_resolution_honors_primary_interface_binding():
    container = Container()
    container.register(FirstNative)
    container.register(SecondNative)
    container.bind(NativePort, FirstNative)
    container.bind(NativePort, SecondNative)
    container.get_registration(SecondNative).primary = True
    assert isinstance(NativeDomains(container)._resolve(NativePort), SecondNative)


def test_native_resolution_does_not_mask_ambiguous_interface_binding():
    container = Container()
    for kind in (FirstNative, SecondNative):
        container.register(kind)
        container.bind(NativePort, kind)
    with pytest.raises(NoUniqueBeanError):
        NativeDomains(container)._resolve(NativePort)


async def test_index_coverage_uses_injected_native_domains(monkeypatch):
    from koinon.knowledge.indexes import adapters

    repository = SimpleNamespace(
        coverage_counts=AsyncMock(return_value={"chunk_count": 2, "vector_count": 2})
    )
    native = SimpleNamespace(_resolve=lambda kind: repository)
    source = object()

    @asynccontextmanager
    async def unit(value):
        assert value is source
        yield

    monkeypatch.setattr(adapters, "infrastructure_unit", unit)
    adapter = adapters.NativeIndexAdapter(SimpleNamespace(get=lambda name: source), native)
    result = await adapter.coverage(
        SimpleNamespace(
            domain="documents",
            tenant_id="tenant",
            native_workspace_id="workspace",
            native_id="set",
        )
    )
    assert result == {"chunk_count": 2, "vector_count": 2, "complete": True}
    repository.coverage_counts.assert_awaited_once_with(
        tenant_id="tenant", workspace_id="workspace", set_id="set"
    )


def test_history_public_service_depends_on_typed_port_and_has_no_native_sql_imports():
    import inspect

    from koinon.knowledge.document_history.ports import DocumentHistoryPort
    from koinon.knowledge.document_history.service import DocumentHistoryService

    assert inspect.signature(DocumentHistoryService).parameters["history"].annotation is DocumentHistoryPort


def test_history_port_override_and_disabled_canon_share_one_native_lifecycle(tmp_path):
    from pyfly.container import component
    from pyfly.context.lifecycle import post_construct, pre_destroy
    from starlette.testclient import TestClient

    from koinon.app import create_application
    from koinon.knowledge.document_history.ports import DocumentHistoryPort
    from koinon.knowledge.document_history.service import DocumentHistoryService

    calls = []

    @component
    class Witness:
        @post_construct
        def start(self):
            calls.append("start")

        @pre_destroy
        def stop(self):
            calls.append("stop")

    app = create_application(
        {
            "koinon": {
                "knowledge": {"enabled": True},
                "legacy": {"enabled": False},
                "security": {
                    "issuer": "https://identity.example.test",
                    "jwks_uri": "https://identity.example.test/keys",
                    "client_id": "browser",
                    "api_audience": "api",
                    "authorization_uri": "https://identity.example.test/authorize",
                    "token_uri": "https://identity.example.test/token",
                    "redirect_uri": "http://127.0.0.1/callback",
                    "cookie_secure": False,
                },
            },
            "pyfly": {
                "data": {
                    "relational": {
                        "enabled": True,
                        "ddl-auto": "create",
                        "url": f"sqlite+aiosqlite:///{tmp_path / 'app.db'}",
                    }
                }
            },
        }
    )
    context = app.state.context
    replacement = SimpleNamespace(versions=AsyncMock())
    context.container.register_instance(DocumentHistoryPort, replacement)
    context.register_bean(Witness)
    with TestClient(app):
        assert calls == ["start"]
        assert context.get_bean(DocumentHistoryService).history is replacement
        from flycanon.models.repositories import SourceRepository

        assert not context.container.contains_type(SourceRepository)
    assert calls == ["start", "stop"]


async def test_disabled_canon_history_binding_is_lazy_and_fails_at_operation():
    from pyfly.kernel import ServiceUnavailableException

    from koinon.knowledge.document_history.configuration import DocumentHistoryConfiguration
    from koinon.knowledge.document_history.repositories import DocumentHistoryRepository

    resources = DocumentHistoryConfiguration().document_history_resources(Container())
    repository = DocumentHistoryRepository(resources)
    with pytest.raises(ServiceUnavailableException) as denied:
        await repository.versions(
            tenant_id="tenant", workspace_id="workspace", source_id="source", actor="actor"
        )
    assert denied.value.code == "DOMAIN_PREREQUISITE_REQUIRED"


async def test_query_uses_public_managed_runtime_inside_model_bindings():
    from uuid import uuid4

    from flyquery.core.services.datasets.dataset_service import DatasetService
    from flyquery.core.services.query.runtime import StructuredQueryRuntimeFactory

    workspace, dataset = str(uuid4()), str(uuid4())
    calls = []

    async def answer(**arguments):
        assert calls == ["models", "unit"]
        assert arguments["dataset_allowlist"] == {dataset}
        assert arguments["scopes"] == {"flyquery.query:read", "flyquery.sql:execute"}
        return {"answer": "verified"}

    @asynccontextmanager
    async def unit(*, settings_overrides=None):
        assert settings_overrides is None
        calls.append("unit")
        try:
            yield SimpleNamespace(pipeline=SimpleNamespace(answer=answer))
        finally:
            calls.append("unit_closed")

    @asynccontextmanager
    async def models(*args, **kwargs):
        calls.append("models")
        try:
            yield
        finally:
            calls.append("models_closed")

    services = {
        DatasetService: SimpleNamespace(
            get=AsyncMock(
                return_value={
                    "tenant_id": "tenant",
                    "workspace_id": workspace,
                }
            )
        ),
        StructuredQueryRuntimeFactory: SimpleNamespace(unit=unit),
    }
    container = Container()
    for kind, value in services.items():
        container.register_instance(kind, value)
    domains = NativeDomains(container)
    domains.model_connections = models
    result = await domains.query(
        tenant_id="tenant",
        workspace_id=workspace,
        dataset_id=dataset,
        dataset_allowlist={dataset},
        question="Question",
        conversation_id=None,
        sql=None,
        actor="actor",
    )
    assert result == {"answer": "verified"}
    assert calls == ["models", "unit", "unit_closed", "models_closed"]
