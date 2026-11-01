# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import httpx
import pytest
from pydantic import ValidationError

from koinon_sdk import AnswerAudit, AnswerRelease, KoinonClient, ResultPin


def release():
    return {
        "run_id": "run",
        "message_id": "answer",
        "tenant_id": "north",
        "generation_id": "generation",
        "publication_sequence": 7,
        "outcome": "grounded",
        "text_sha256": "a" * 64,
        "citations_sha256": "b" * 64,
        "artifacts_sha256": "c" * 64,
        "policy_sha256": "d" * 64,
        "fact_ids": ["fact"],
        "result_pins": [{"id": "result", "sha256": "e" * 64}],
        "source_refs": [{"id": "source-ref", "asset_id": "document", "kind": "document", "title": "Fact"}],
        "created_at": "2026-11-01T19:00:00.123456Z",
    }


async def test_audit_decodes_the_exact_optional_server_release_without_historical_backfill():
    value = {"run_id": "run", "provenance_status": "recorded", "output_release": release()}
    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(200, json=value)

    async with KoinonClient(
        "https://knowledge.example.com/api/v1",
        token_provider=lambda: "fixture",
        transport=httpx.MockTransport(handle),
    ) as client:
        audit = await client.run_audit("north", "run")
    assert isinstance(audit.output_release, AnswerRelease)
    assert isinstance(audit.output_release.result_pins[0], ResultPin)
    assert audit.output_release.publication_sequence == 7
    assert audit.output_release.created_at.microsecond == 123456
    assert audit.output_release.source_refs[0].asset_id == "document"
    assert requests[0].headers["authorization"] == "Bearer fixture"
    assert (
        audit.output_release.model_dump(mode="json", exclude_defaults=True)["result_pins"]
        == release()["result_pins"]
    )
    old = AnswerAudit.model_validate({"run_id": "old", "provenance_status": "not_recorded"})
    assert old.output_release is None


def test_release_fields_retain_wire_constraints_and_timezone_requirement():
    for change in (
        {"publication_sequence": 0},
        {"policy_version": "invented-policy"},
        {"created_at": "2026-11-01T19:00:00"},
        {"result_pins": [{"id": "result", "sha256": "bad"}]},
    ):
        with pytest.raises(ValidationError):
            AnswerRelease.model_validate({**release(), **change})
