# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import json
from pathlib import Path

import httpx

from koinon_sdk import KoinonClient, ProposalConfirmation, ProposalRevision


async def test_proposals_keep_explicit_confirmation_revision_and_opaque_ids():
    fixture_path = Path(__file__).resolve().parents[2] / "contract/fixtures.json"
    value = json.loads(fixture_path.read_text())["fixtures"]["CatalogProposal"]
    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(200, json=value)

    async with KoinonClient(
        "https://koinon.test/api/v1", token_provider=lambda: "fresh", transport=httpx.MockTransport(handle)
    ) as client:
        await client.proposal("north", "run/one", "proposal/one")
        await client.confirm_proposal(
            "north", "run/one", "proposal/one", ProposalConfirmation(confirm=True, expected_revision=1)
        )
        await client.cancel_proposal(
            "north", "run/one", "proposal/one", ProposalRevision(expected_revision=1)
        )
    assert len(requests) == 3
    assert requests[0].url.raw_path.endswith(b"/chat/runs/run%2Fone/proposals/proposal%2Fone")
    assert json.loads(requests[1].content) == {"confirm": True, "expected_revision": 1}
    assert json.loads(requests[2].content) == {"expected_revision": 1}


def test_proposal_only_policy_is_review_required_and_not_grounded():
    from koinon_sdk import AnswerPolicy

    value = AnswerPolicy.model_validate({"outcome": "review_required", "code": "REVIEW_REQUIRED"})
    assert value.outcome == "review_required"
