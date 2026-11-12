# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Mounted HTTP approval contract; production activation remains a separate gate."""

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from urllib.parse import unquote
from uuid import uuid4

import pytest
from conftest import bearer
from test_content_sources import sources as source_client

from koinon.integrations.content_sources.mapping_policies import SourcePolicies
from koinon.integrations.content_sources.sync_dtos import SourcePolicyOperationOutput


@pytest.fixture
def mappings(tmp_path, monkeypatch, request):
    import koinon.app
    from koinon.integrations.content_sources import configuration

    callspec = getattr(request.node, "callspec", None)
    process = callspec.params.get("source_process_case") if callspec else None
    if process is not None:
        create = koinon.app.create_application

        def configured(config):
            config["koinon"]["process"] = {"role": process[0]}
            config["koinon"]["content_sources"]["synchronization_enabled"] = process[1]
            return create(config, role=process[0])

        monkeypatch.setattr(koinon.app, "create_application", configured)
    original = configuration.register_source_accounts

    def compose(context, config, *, controllers):
        original(context, config, controllers=controllers)
        configuration.register_source_synchronization(context, controllers=controllers)

    monkeypatch.setattr(configuration, "register_source_accounts", compose)
    with contextmanager(source_client.__wrapped__)(tmp_path, monkeypatch, request) as client:
        yield client


@pytest.mark.parametrize("source_process_case", [("api", True)])
def test_real_source_process_composition_limits_execution_to_enabled_workers(mappings, source_process_case):
    from koinon.integrations.content_sources.sync_files import SourceFiles
    from koinon.integrations.content_sources.sync_folders import SourceFolders
    from koinon.integrations.content_sources.sync_replacement import SourceReplacements
    from koinon.integrations.content_sources.sync_worker import SourceSyncWorker
    from koinon.workers.admission import WorkAdmission, WorkAdmissionSettings

    context = mappings.native_app.state.context
    assert context.config.get("koinon.process.role") == source_process_case[0]
    expected = context.config.get("koinon.process.role") == "worker" and context.config.get(
        "koinon.content_sources.synchronization_enabled"
    )
    assert context.container.contains_type(SourceSyncWorker) is expected
    assert isinstance(context.get_bean(WorkAdmission), WorkAdmission)
    assert isinstance(context.get_bean(WorkAdmissionSettings), WorkAdmissionSettings)
    if expected:
        worker = context.get_bean(SourceSyncWorker)
        assert worker.files is context.get_bean(SourceFiles)
        assert worker.folders is context.get_bean(SourceFolders)
        assert worker.replacements is context.get_bean(SourceReplacements)
        assert worker.admission is context.get_bean(WorkAdmission)


@pytest.mark.parametrize("synchronization_enabled", [False, True])
async def test_real_worker_context_resolves_source_execution_and_drains_scheduling(
    tmp_path, synchronization_enabled
):
    import asyncio
    import base64

    from flycanon.config import CanonSettings
    from flyquery.config import FlyquerySettings

    from koinon.app import create_application
    from koinon.integrations.content_sources.configuration import register_source_synchronization
    from koinon.integrations.content_sources.sync_files import SourceFiles
    from koinon.integrations.content_sources.sync_folders import SourceFolders
    from koinon.integrations.content_sources.sync_replacement import SourceReplacements
    from koinon.integrations.content_sources.sync_worker import SourceSyncWorker
    from koinon.workers.admission import WorkAdmission

    application = create_application(
        {
            "koinon": {
                "legacy": {"enabled": False},
                "knowledge": {"enabled": False},
                "mcp": {"enabled": False},
                "content_sources": {
                    "enabled": True,
                    "master_key": base64.b64encode(bytes(range(32))).decode(),
                    "synchronization_enabled": synchronization_enabled,
                },
                "security": {
                    "issuer": "https://identity.invalid",
                    "jwks_uri": "https://identity.invalid/keys",
                    "client_id": "browser",
                    "api_audience": "api",
                    "authorization_uri": "https://identity.invalid/authorize",
                    "token_uri": "https://identity.invalid/token",
                    "redirect_uri": "http://127.0.0.1/callback",
                    "cookie_secure": False,
                },
            },
            "pyfly": {
                "data": {
                    "relational": {
                        "enabled": True,
                        "ddl-auto": "create",
                        "url": f"sqlite+aiosqlite:///{tmp_path / 'worker.db'}",
                        "datasources": {
                            name: {
                                "url": f"sqlite+aiosqlite:///{tmp_path / (name + '.db')}",
                                "ddl-auto": "none",
                            }
                            for name in ("canon", "canon_admin", "structured", "structured_admin")
                        },
                    }
                }
            },
        },
        role="worker",
    )
    context = application.state.context
    context.container.register_instance(
        CanonSettings, CanonSettings(object_store_localfs_root=str(tmp_path / "documents"))
    )
    context.container.register_instance(
        FlyquerySettings, FlyquerySettings(object_store_base=str(tmp_path / "structured"))
    )
    register_source_synchronization(context, controllers=False)
    before = asyncio.all_tasks()
    await context.start()
    try:
        assert not callable(application)
        assert context.config.get("koinon.process.role") == "worker"
        assert context.config.get("pyfly.scheduling.enabled") is True
        for kind in (SourceSyncWorker, SourceFiles, SourceFolders, SourceReplacements):
            assert context.container.contains_type(kind) is synchronization_enabled
        if synchronization_enabled:
            worker = context.get_bean(SourceSyncWorker)
            assert worker.files is context.get_bean(SourceFiles)
            assert worker.folders is context.get_bean(SourceFolders)
            assert worker.replacements is context.get_bean(SourceReplacements)
            assert worker.admission is context.get_bean(WorkAdmission)
    finally:
        await context.stop()
    assert not (asyncio.all_tasks() - before)


def review_body():
    return dict(
        operation_id=str(uuid4()),
        connection_id="connection",
        drive_id="drive",
        root_id="root",
        destination=dict(workspace_id="workspace", project_id="project", parent_id="folder"),
        recursive=True,
        removal_policy="retire",
    )


def test_mounted_review_requires_browser_csrf_and_has_no_tool_approval_field(mappings, monkeypatch):
    policies = mappings.native_app.state.context.get_bean(SourcePolicies)
    calls = []

    async def reviewed(actor, tenant, browser, request):
        await policies.sessions.require(actor, browser)
        calls.append((actor, tenant, browser, request.operation_id))
        return SourcePolicyOperationOutput(
            receipt_id="receipt",
            operation_id=request.operation_id,
            action="review",
            mapping_id="mapping",
            policy_id="review",
            expected_policy_revision=None,
            result_policy_revision=1,
            review_digest="a" * 64,
            review_expires_at=datetime.now(UTC) + timedelta(minutes=15),
            disposition="reviewed",
        )

    monkeypatch.setattr(policies, "review", reviewed)
    root = "/api/v1/tenants/north/content-sources"
    body = review_body()
    mappings.cookies.clear()
    assert mappings.post(root + "/mapping-reviews", headers=bearer(), json=body).status_code == 403
    mappings.cookies.set("PYFLY_SESSION", "source-browser", domain="testserver.local", path="/")
    browser = "/bff" + root
    assert mappings.get(browser + "/connections").status_code == 200
    assert mappings.post(browser + "/mapping-reviews", json=body).status_code == 403
    csrf = {"X-XSRF-TOKEN": unquote(mappings.cookies.get("XSRF-TOKEN"))}
    assert (
        mappings.post(browser + "/mapping-reviews", headers=csrf, json={**body, "approved": True}).status_code
        == 422
    )
    assert calls == []
    response = mappings.post(browser + "/mapping-reviews", headers=csrf, json=body)
    assert response.status_code == 201, response.text
    assert response.json()["schema"] == "koinon.source-policy-operation.v1"
    assert response.json()["operation_id"] == body["operation_id"]
    assert calls[0][1:] == ("north", "source-browser", body["operation_id"])
    assert mappings.get(root + "/connections", headers=bearer()).json()["synchronization_available"] is False


def test_unmounted_synchronization_is_unavailable_in_default_application(sources):
    assert sources.get("/api/v1/tenants/north/content-sources/mappings", headers=bearer()).status_code == 404


sources = source_client


def test_validation_routes_require_browser_csrf_and_keep_scan_commands_separate(mappings, monkeypatch):
    from koinon.integrations.content_sources.mapping_validation import SourceMappingValidations
    from koinon.integrations.content_sources.mapping_validation_dtos import (
        SourceMappingValidationItemPage,
        SourceMappingValidationOutput,
    )

    validations = mappings.native_app.state.context.get_bean(SourceMappingValidations)
    identifier = uuid4()
    result = SourceMappingValidationOutput(
        validation_id=identifier,
        revision=1,
        state="scanning",
        enumeration_complete=False,
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
        continuation_token="opaque",
    )
    calls = []

    def fake(method):
        async def invoke(actor, tenant, browser, *args, **kwargs):
            await validations.sessions.require(actor, browser)
            calls.append((method, tenant, browser, args, kwargs))
            if method == "validation_items":
                return SourceMappingValidationItemPage(
                    validation_id=identifier,
                    revision=1,
                    items=[],
                    visible_count=0,
                    next_cursor=None,
                )
            return result

        return invoke

    for method in (
        "begin_validation",
        "validation_status",
        "creation_receipt",
        "continue_validation",
        "validation_items",
        "abandon_validation",
    ):
        monkeypatch.setattr(validations, method, fake(method))
    root = "/api/v1/tenants/north/content-sources/mapping-validations"
    mappings.cookies.clear()
    assert mappings.post(root, headers=bearer(), json=review_body()).status_code == 403
    assert mappings.get(root + "/" + str(identifier), headers=bearer()).status_code == 403
    assert calls == []
    mappings.cookies.set("PYFLY_SESSION", "source-browser", domain="testserver.local", path="/")
    browser = "/bff" + root
    assert mappings.get("/bff/api/v1/tenants/north/content-sources/connections").status_code == 200
    body = review_body()
    assert mappings.post(browser, json=body).status_code == 403
    csrf = {"X-XSRF-TOKEN": unquote(mappings.cookies.get("XSRF-TOKEN"))}
    assert mappings.post(browser, headers=csrf, json={**body, "approved": True}).status_code == 422
    response = mappings.post(browser, headers=csrf, json=body)
    assert response.status_code == 201, response.text
    assert response.json()["validation_id"] == str(identifier)
    assert response.json()["total"] is None
    for tail in (
        "/" + str(identifier),
        "/operations/" + body["operation_id"],
        "/" + str(identifier) + "/items",
    ):
        response = mappings.get(browser + tail)
        assert response.status_code == 200, response.text
    for action, payload in (
        ("continue", {"expected_revision": 1, "continuation_token": "opaque"}),
        ("abandon", {"expected_revision": 1}),
    ):
        path = browser + "/" + str(identifier) + "/" + action
        assert mappings.post(path, json=payload).status_code == 403
        response = mappings.post(path, headers=csrf, json=payload)
        assert response.status_code == 200, response.text
    assert [call[0] for call in calls] == [
        "begin_validation",
        "validation_status",
        "creation_receipt",
        "validation_items",
        "continue_validation",
        "abandon_validation",
    ]
    assert all(call[1:3] == ("north", "source-browser") for call in calls)
