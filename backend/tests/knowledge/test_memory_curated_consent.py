# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Only explicit confirmation transfers reviewed remembered context into repository knowledge."""

from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from pyfly.kernel import ConflictException
from test_curated_intents import curated as curated
from test_curated_intents import input_for

from koinon.knowledge.curated.dtos import KnowledgeConfirmation


@pytest.mark.parametrize("consent", [None, False])
async def test_preview_without_memory_consent_can_be_explicitly_confirmed_and_retried(
    curated, monkeypatch, consent
):
    service, catalog, destination, context = curated
    original = service.authority.observe

    async def observe(
        subject, tenant_id, request, recorded_at, *, memory_capture=None, output_capture=None
    ):
        evidence, origins = await original(
            subject, tenant_id, request, recorded_at, output_capture=output_capture
        )
        memory_capture.update(
            {
                "present": True,
                "bindings": [
                    {
                        "run_id": "fixed-run",
                        "generation_id": "fixed-generation",
                        "manifest_sha256": "a" * 64,
                        "results": [],
                    }
                ],
            }
        )
        return evidence, origins

    class Memory:
        async def authorize(self, subject, tenant_id, bindings, *, transfer=False, consent=False, **kwargs):
            assert bindings[0].generation_id == "fixed-generation"
            if transfer and not consent:
                raise ConflictException("Review remembered context", code="MEMORY_TRANSFER_REVIEW_REQUIRED")
            return True

    monkeypatch.setattr(service.authority, "observe", observe)
    service.authority.memory = SimpleNamespace(get=lambda: Memory())
    native = object()
    service.native = SimpleNamespace(get=lambda: native)
    preview = await service.preview("issuer|owner", "north", input_for(destination))
    assert preview.remembered_context_present
    confirmation = {
        "confirm": True,
        "expected_revision": preview.revision,
        "authorization_digest": preview.authorization_digest,
    }
    rejected = {**confirmation, **({"include_remembered_context": consent} if consent is not None else {})}
    with pytest.raises(ConflictException) as error:
        await service.admit(
            "issuer|owner", "north", preview.id, KnowledgeConfirmation.model_validate(rejected), "reviewed"
        )
    assert error.value.code == "MEMORY_TRANSFER_REVIEW_REQUIRED"
    approved = KnowledgeConfirmation.model_validate({**confirmation, "include_remembered_context": True})
    accepted, _, port = await service.admit("issuer|owner", "north", preview.id, approved, "reviewed")
    assert accepted.authorization_digest == preview.authorization_digest and port is native
    row = await service.load("issuer|owner", "north", preview.id)
    assert row.request_json["_memory_context"]["consented"] is True
    accepted, _, _ = await service.admit(
        "issuer|owner", "north", preview.id, KnowledgeConfirmation.model_validate(confirmation), "reviewed"
    )
    assert accepted.authorization_digest == preview.authorization_digest


def test_memory_confirmation_rejects_truthy_strings():
    with pytest.raises(ValidationError):
        KnowledgeConfirmation.model_validate(
            {
                "confirm": True,
                "expected_revision": 1,
                "authorization_digest": "a" * 64,
                "include_remembered_context": "true",
            }
        )
