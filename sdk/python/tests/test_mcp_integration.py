# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import httpx

from koinon_sdk import KoinonClient


async def test_connection_descriptor_is_a_typed_deployment_read_without_tenant_or_secret():
    seen = []
    value = {
        "enabled": True,
        "endpoint": "https://organization.example.test/mcp",
        "authentication": ["personal_token", "oauth"],
        "oauth_enabled": True,
        "oauth_registration": "pre_registered",
        "supported_scopes": ["catalog:read"],
        "tools": [],
        "review": {"supported": True},
    }

    def handle(request):
        seen.append((request.method, request.url.path))
        return httpx.Response(200, json=value)

    async with KoinonClient(
        "https://organization.example.test/api/v1",
        token_provider=lambda: "owned-test",
        transport=httpx.MockTransport(handle),
    ) as client:
        assert hasattr(client, "mcp_connection"), "The SDK must expose the deployment connection descriptor"
        descriptor = await client.mcp_connection()
    assert descriptor.endpoint == value["endpoint"]
    assert descriptor.review.external_redirect is False
    assert seen == [("GET", "/api/v1/mcp/connection")]


def test_all_external_review_operations_are_explicit_and_no_challenge_reader_is_exposed():
    assert all(
        hasattr(KoinonClient, name)
        for name in (
            "stage_external_review",
            "external_review",
            "approve_external_review",
            "cancel_external_review",
        )
    )
    assert not hasattr(KoinonClient, "external_review_challenge")


async def test_external_text_and_file_operations_preserve_scope_decisions_keys_and_unknown_outcomes():
    import json
    from pathlib import Path

    from koinon_sdk import (
        ExternalFileChunkInput,
        ExternalFileReviewInput,
        ExternalReviewDecision,
        ExternalReviewInput,
        KnowledgeContent,
    )

    fixtures = json.loads((Path(__file__).resolve().parents[3] / "sdk/contract/fixtures.json").read_text())[
        "fixtures"
    ]
    seen = []

    def handle(request):
        body = json.loads(request.content) if request.content else None
        seen.append((request.method, request.url.path, request.headers.get("idempotency-key"), body))
        if "/external-file-reviews" in request.url.path:
            value = {**fixtures["ExternalFileReviewView"]}
            if request.url.path.endswith("/approve"):
                value.update(status="unresolved", source_id=None, receipt=None)
        elif request.url.path.endswith("/approve"):
            value = fixtures["PendingKnowledgeCommit"]
        else:
            value = fixtures["ExternalReviewView"]
        return httpx.Response(202 if request.url.path.endswith("/approve") else 200, json=value)

    decision = ExternalReviewDecision(expected_revision=1, authorization_digest="a" * 64, nonce="n" * 43)
    proposal = ExternalReviewInput(
        action="create_draft",
        destination_id="owned-collection",
        content=KnowledgeContent(title="Proposed", body="External proposed text."),
    )
    file = ExternalFileReviewInput(
        filename="owned.txt",
        mode="document",
        destination_id="owned-collection",
        size_bytes=3,
        sha256="b" * 64,
    )
    chunk = ExternalFileChunkInput(index=0, data_base64="YWJj", sha256="b" * 64)
    async with KoinonClient(
        "https://organization.example.test/api/v1",
        token_provider=lambda: "owned-test",
        transport=httpx.MockTransport(handle),
    ) as client:
        await client.stage_external_review("north/team", proposal, idempotency_key="text-stage")
        await client.external_review("north/team", "review/one")
        pending = await client.approve_external_review(
            "north/team", "review/one", decision, idempotency_key="text-approval"
        )
        await client.cancel_external_review("north/team", "review/one", decision)
        await client.stage_external_file_review("north/team", file, idempotency_key="file-stage")
        await client.external_file_review("north/team", "file/one")
        await client.upload_external_file_chunk("north/team", "file/one", chunk)
        await client.seal_external_file_review("north/team", "file/one")
        unresolved = await client.approve_external_file_review(
            "north/team", "file/one", decision, idempotency_key="file-approval"
        )
        await client.cancel_external_file_review("north/team", "file/one", decision)
    assert pending.status == "pending" and unresolved.status == "unresolved" and unresolved.receipt is None
    assert len(seen) == 10 and [row[0] for row in seen] == [
        "POST",
        "GET",
        "POST",
        "POST",
        "POST",
        "GET",
        "POST",
        "POST",
        "POST",
        "POST",
    ]
    assert [row[2] for row in seen] == [
        "text-stage",
        None,
        "text-approval",
        None,
        "file-stage",
        None,
        None,
        None,
        "file-approval",
        None,
    ]
    assert seen[0][3]["destination_id"] == "owned-collection" and "origin" not in seen[0][3]
    assert seen[2][3] == decision.model_dump() and seen[8][3] == decision.model_dump()
    assert seen[6][3] == chunk.model_dump()


def test_external_review_inputs_do_not_accept_fabricated_origins_or_expose_private_challenge_models():
    import pytest
    from pydantic import ValidationError

    import koinon_sdk
    from koinon_sdk import ExternalReviewInput

    with pytest.raises(ValidationError):
        ExternalReviewInput.model_validate(
            {
                "action": "create_draft",
                "destination_id": "owned-collection",
                "content": {"title": "Proposed", "body": "Text"},
                "origin": {"kind": "user_statement"},
            }
        )
    assert not hasattr(koinon_sdk, "ExternalReviewChallenge")
    assert not hasattr(koinon_sdk, "ExternalFileReviewChallenge")


def test_mcp_canonical_model_fixtures_validate_against_actual_generated_types():
    import json
    from pathlib import Path

    from koinon_sdk import (
        ExternalFileReviewView,
        ExternalProposalEvidence,
        ExternalReviewView,
        McpConnectionDescriptor,
    )

    fixtures = json.loads((Path(__file__).resolve().parents[3] / "sdk/contract/fixtures.json").read_text())[
        "fixtures"
    ]
    from koinon_sdk import ExternalReviewDecision

    for model in (
        ExternalFileReviewView,
        ExternalReviewView,
        ExternalProposalEvidence,
        McpConnectionDescriptor,
        ExternalReviewDecision,
    ):
        model.model_validate(fixtures[model.__name__])
