# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Isolated signed-HTTP review; no managed services, models, or provider requests."""

from datetime import UTC, datetime, timedelta

import pytest
from conftest import ISSUER, bearer

from koinon.assistants.queue import AssistantQueue
from koinon.assistants.service import AssistantService
from koinon.assistants.settings import AssistantSettings
from koinon.evidence.dtos import SourceReference
from koinon.knowledge.capture_dtos import CapturedEvidence


@pytest.mark.parametrize("fresh_retry", [False, True])
def test_revoked_origin_token_cannot_replay_through_broader_owner_session(client, fresh_retry):
    context = client.native_app.state.context
    subject = ISSUER + "|admin"

    async def configure():
        context.get_bean(AssistantSettings).allowed_provider_hosts = ["127.0.0.1"]
        service = context.get_bean(AssistantService)
        provider = await service.save_provider(
            subject,
            "north",
            {
                "name": "Isolated review",
                "kind": "ollama",
                "base_url": "http://127.0.0.1:11434/v1",
                "model_ids": ["no-network"],
            },
        )
        agent = await service.save_agent(
            subject,
            "north",
            {
                "name": "Review agent",
                "provider_id": provider["id"],
                "model_id": "no-network",
                "tools": ["search_knowledge"],
            },
        )
        parent = None
        for kind in ("workspace", "project", "collection", "source", "document"):
            parent = await service.catalog.create(
                subject, "north", kind=kind, name=kind, parent_id=parent.id if parent else None
            )
        return agent, parent

    agent, asset = client.portal.call(configure)
    token = client.post(
        "/api/v1/tokens",
        headers=bearer(),
        json={
            "name": "Origin review",
            "tenant_id": "north",
            "scopes": ["chat:use", "catalog:read", "knowledge:search"],
            "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        },
    )
    assert token.status_code == 201
    authority = {"Authorization": "Bearer " + token.json()["token"]}
    thread = client.post(
        "/api/v1/tenants/north/chat/threads", headers=authority, json={"scope": {"asset_ids": [asset.id]}}
    )
    assert thread.status_code == 201
    run = client.post(
        "/api/v1/tenants/north/chat/threads/" + thread.json()["id"] + "/runs",
        headers=authority,
        json={"agent_id": agent["id"], "message": "Read owned fact", "client_request_id": "origin-review"},
    )
    assert run.status_code == 202

    async def retain():
        queue = context.get_bean(AssistantQueue)
        claimed = await queue.claim("audit-review")
        assert claimed.id == run.json()["run_id"]
        data = {
            "hits": [
                {
                    "id": "chunk",
                    "asset_id": asset.id,
                    "source_id": asset.parent_id,
                    "title": "Document",
                    "text": "Owned captured passage",
                }
            ]
        }
        source = SourceReference(
            id="used",
            asset_id=asset.id,
            source_id=asset.parent_id,
            kind="document",
            title="Document",
            used_revision="chunk-sha256:" + "a" * 64,
            chunk_id="chunk",
            quote="Owned captured passage",
        )
        result = await queue.evidence(
            claimed.id,
            "audit-review",
            "search",
            data,
            [asset.id],
            capture=CapturedEvidence(data, (source,), True),
        )
        await queue.policy(claimed.id, "audit-review", {"outcome": "grounded"})
        await queue.append(claimed.id, "audit-review", "message_delta", {"text": "Owned captured passage"})
        await queue.finish(claimed.id, "audit-review", code="CONTROLLED_FAILURE" if fresh_retry else None)
        return result

    result_id = client.portal.call(retain)
    revoked = client.delete("/api/v1/tokens/" + token.json()["id"], headers=bearer())
    assert revoked.status_code == 204
    prefix = "/api/v1/tenants/north/chat/"
    responses = {
        "audit": client.get(prefix + "runs/" + run.json()["run_id"] + "/audit", headers=bearer()),
        "history": client.get(prefix + "threads/" + thread.json()["id"] + "/messages", headers=bearer()),
        "SSE": client.get(prefix + "runs/" + run.json()["run_id"] + "/events", headers=bearer()),
        "result": client.get(
            prefix + "runs/" + run.json()["run_id"] + "/results/" + result_id, headers=bearer()
        ),
    }
    observed = {name: response.status_code for name, response in responses.items()}
    assert all(status == 403 for status in observed.values()), observed

    assert (
        client.get(prefix + "runs/" + run.json()["run_id"] + "/activity", headers=bearer()).status_code == 200
    )
    if fresh_retry:
        repeated = client.post(prefix + "runs/" + run.json()["run_id"] + "/retry", headers=bearer())
        assert repeated.status_code == 202, repeated.text

        async def finish_fresh():
            queue = context.get_bean(AssistantQueue)
            claimed = await queue.claim("fresh-review")
            assert claimed.id == run.json()["run_id"]
            from koinon.answers.dtos import EvidenceAnswerPlan

            await queue.release_answer(
                claimed.id,
                "fresh-review",
                EvidenceAnswerPlan(outcome="insufficient_evidence"),
                "en",
                refusal_code="KNOWLEDGE_ONLY",
            )
            await queue.finish(claimed.id, "fresh-review")

        client.portal.call(finish_fresh)
        audit = client.get(prefix + "runs/" + run.json()["run_id"] + "/audit", headers=bearer())
        assert audit.status_code == 200, audit.text
        assert audit.json()["sources"] == []
        page = client.get(prefix + "threads/" + thread.json()["id"] + "/messages", headers=bearer())
        assert page.status_code == 200, page.text
        assert "Owned captured passage" not in page.text
        replay = client.get(prefix + "runs/" + run.json()["run_id"] + "/events", headers=bearer())
        assert replay.status_code == 200, replay.text
        assert "Owned captured passage" not in replay.text
        from koinon.assistants.grounding import refusal_message

        assert "message_reset" in replay.text and refusal_message("en", "KNOWLEDGE_ONLY") in replay.text
        assert audit.json()["output_release"]["generation_id"] is None
        old = client.get(prefix + "runs/" + run.json()["run_id"] + "/results/" + result_id, headers=bearer())
        assert old.status_code == 403, old.text
