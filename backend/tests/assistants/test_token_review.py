# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Signed HTTP regressions for authority retained by delegated retries."""

import importlib.util
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from koinon.assistants.repositories import ChatRunRepository
from koinon.assistants.service import AssistantService
from koinon.assistants.settings import AssistantSettings

spec = importlib.util.spec_from_file_location(
    "token_review_web_fixture", Path(__file__).resolve().parents[1] / "web/conftest.py"
)
assert spec and spec.loader
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)
client = native.client


def issue(client, scopes):
    response = client.post(
        "/api/v1/tokens",
        headers=native.bearer(),
        json={
            "name": "Delegated retry review",
            "tenant_id": "north",
            "scopes": scopes,
            "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        },
    )
    assert response.status_code == 201
    return response.json()


@pytest.mark.parametrize("original_authority", ["interactive", "broader_personal_token"])
def test_retry_records_the_current_callers_token_authority(client, original_authority):
    context = client.native_app.state.context

    async def setup():
        context.get_bean(AssistantSettings).allowed_provider_hosts = ["127.0.0.1"]
        service = context.get_bean(AssistantService)
        provider = await service.save_provider(
            native.ISSUER + "|admin",
            "north",
            {
                "name": "Controlled retry provider",
                "kind": "ollama",
                "base_url": "http://127.0.0.1:11434/v1",
                "model_ids": ["controlled"],
            },
        )
        return await service.save_agent(
            native.ISSUER + "|admin",
            "north",
            {
                "name": "Controlled retry agent",
                "provider_id": provider["id"],
                "model_id": "controlled",
                "tools": ["query_dataset"],
            },
        )

    agent = client.portal.call(setup)
    original_headers = native.bearer()
    if original_authority == "broader_personal_token":
        original = issue(client, ["chat:use", "query:execute"])
        original_headers = {"Authorization": "Bearer " + original["token"]}
    thread = client.post("/api/v1/tenants/north/chat/threads", headers=original_headers, json={})
    assert thread.status_code == 201
    run = client.post(
        "/api/v1/tenants/north/chat/threads/" + thread.json()["id"] + "/runs",
        headers=original_headers,
        json={"agent_id": agent["id"], "message": "Controlled retry", "client_request_id": "review-retry"},
    )
    assert run.status_code == 202
    run_id = run.json()["run_id"]
    assert (
        client.post(
            "/api/v1/tenants/north/chat/runs/" + run_id + "/cancel", headers=native.bearer()
        ).status_code
        == 200
    )
    current = issue(client, ["chat:use"])
    retried = client.post(
        "/api/v1/tenants/north/chat/runs/" + run_id + "/retry",
        headers={"Authorization": "Bearer " + current["token"]},
    )
    assert retried.status_code == 202

    async def retained_authority():
        row = await context.get_bean(ChatRunRepository).find_by_id(run_id)
        return row.access_token_id

    assert client.portal.call(retained_authority) == current["id"], (
        "A retry must not regain interactive or older broader token authority"
    )
