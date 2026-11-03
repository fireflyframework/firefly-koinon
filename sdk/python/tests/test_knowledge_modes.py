# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import json
from pathlib import Path

import httpx

from koinon_sdk import KoinonClient, OrganizationKnowledgeSettingsInput
from koinon_sdk.mode_transitions import KnowledgeModeRevisionInput, KnowledgeModeTransitionView


def record():
    fixtures = json.loads((Path(__file__).resolve().parents[2] / "contract/fixtures.json").read_text())[
        "fixtures"
    ]
    return dict(
        id="transition/one",
        tenant_id="north/one",
        job_id="job",
        revision=1,
        base_revision=0,
        base_digest="a" * 64,
        active_mode="rlm",
        requested_mode="rag",
        requested_settings=fixtures["OrganizationKnowledgeSettingsInput"],
        status="queued",
        stage="discovery",
        counters={},
        stage_milliseconds={},
        error_code=None,
        error=None,
        created_at="2026-11-03T00:00:00Z",
        updated_at="2026-11-03T00:00:00Z",
    )


async def test_mode_api_encodes_ids_preserves_idempotency_and_typed_progress():
    calls, value = [], record()

    def handle(request):
        calls.append(request)
        response = (
            {"transition": value}
            if request.url.path.endswith("/current")
            else ({"items": [], "next_cursor": "next"} if request.url.path.endswith(("/targets", "/recoveries")) else value)
        )
        return httpx.Response(200, json=response)

    async with KoinonClient(
        "https://koinon.test/api/v1", token_provider=lambda: "fixture", transport=httpx.MockTransport(handle)
    ) as client:
        created = await client.create_knowledge_mode_transition(
            "north/one",
            OrganizationKnowledgeSettingsInput.model_validate(value["requested_settings"]),
            idempotency_key="stable",
        )
        assert isinstance(created, KnowledgeModeTransitionView)
        assert (await client.current_knowledge_mode_transition("north/one")).transition.id == created.id
        assert (await client.knowledge_mode_transition("north/one", created.id)).job_id == "job"
        page = await client.knowledge_mode_targets("north/one", created.id, after="cursor/one", limit=25)
        assert page.next_cursor == "next"
        revision = KnowledgeModeRevisionInput(expected_revision=created.revision)
        await client.cancel_knowledge_mode_transition("north/one", created.id, revision)
        await client.retry_knowledge_mode_transition("north/one", created.id, revision)
        recovery = await client.knowledge_mode_recoveries("north/one", created.id, after="attempt/one", limit=25)
        assert recovery.next_cursor == "next"
    assert calls[0].headers["Idempotency-Key"] == "stable"
    assert calls[2].url.raw_path.endswith(b"/north%2Fone/knowledge/settings/transitions/transition%2Fone")
    assert dict(calls[3].url.params) == {"after": "cursor/one", "limit": "25"}
    assert [call.method for call in calls] == ["POST", "GET", "GET", "GET", "POST", "POST", "GET"]
    assert json.loads(calls[-2].content) == {"expected_revision": 1}
