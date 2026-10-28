# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from conftest import ISSUER, bearer
from test_chat_sse import seed


def test_native_proposal_diff_requires_explicit_current_owner_confirmation(client):
    async def populate():
        from koinon.assistants.proposals import CatalogProposals
        from koinon.assistants.queue import AssistantQueue
        from koinon.assistants.repositories import ChatRunRepository
        from koinon.catalog.service import CatalogService

        context = client.native_app.state.context
        catalog = context.get_bean(CatalogService)
        entry = None
        for kind in ("workspace", "project", "collection", "source", "document"):
            entry = await catalog.create(
                f"{ISSUER}|admin", "north", kind=kind, name=kind, parent_id=entry.id if entry else None
            )
        run_id = await seed(context)
        repository = context.get_bean(ChatRunRepository)
        run = await repository.find_by_id(run_id)
        run.status, run.scope = "queued", {"asset_ids": [entry.id]}
        await repository.save(run)
        queue = context.get_bean(AssistantQueue)
        claimed = await queue.claim("proposal-http")
        proposal = await context.get_bean(CatalogProposals).propose(
            claimed.id, "proposal-http", entry.id, {"name": "Reviewed label"}
        )
        await queue.finish(claimed.id, "proposal-http")
        return run_id, proposal.id

    run_id, proposal_id = client.portal.call(populate)
    url = f"/api/v1/tenants/north/chat/runs/{run_id}/proposals/{proposal_id}"
    diff = client.get(url, headers=bearer())
    assert diff.status_code == 200, diff.text
    assert diff.json()["changes"] == {"name": "Reviewed label"}
    assert diff.json()["status"] == "pending" and "no-store" in diff.headers["cache-control"]
    for confirm in (False, 1, "true"):
        response = client.post(
            url + "/confirm", json={"confirm": confirm, "expected_revision": 1}, headers=bearer()
        )
        assert response.status_code == 422, response.text
    assert client.get(url, headers=bearer("viewer")).status_code == 403
    result = client.post(url + "/confirm", json={"confirm": True, "expected_revision": 1}, headers=bearer())
    assert result.status_code == 200, result.text
    assert result.json()["status"] == "applied"
    assert (
        client.post(url + "/confirm", json={"confirm": True, "expected_revision": 1}, headers=bearer()).json()
        == result.json()
    )

    async def revoke_origin():
        from datetime import timedelta

        from koinon.assistants.lifecycle import timestamp
        from koinon.assistants.repositories import ChatRunRepository
        from koinon.tokens.entities import PersonalToken
        from koinon.tokens.repositories import PersonalTokenRepository

        context = client.native_app.state.context
        await context.get_bean(PersonalTokenRepository).save(
            PersonalToken(
                id="proposal-origin",
                subject=f"{ISSUER}|admin",
                tenant_id="north",
                name="Origin",
                token_hash="a" * 64,
                prefix="redacted",
                scopes=["catalog:read", "catalog:write", "chat:use"],
                expires_at=timestamp() + timedelta(hours=1),
                revoked_at=timestamp(),
            )
        )
        repository = context.get_bean(ChatRunRepository)
        run = await repository.find_by_id(run_id)
        run.access_token_id = "proposal-origin"
        await repository.save(run)

    client.portal.call(revoke_origin)
    assert client.get(url, headers=bearer()).status_code == 403
    assert (
        client.post(
            url + "/confirm", json={"confirm": True, "expected_revision": 1}, headers=bearer()
        ).status_code
        == 403
    )
