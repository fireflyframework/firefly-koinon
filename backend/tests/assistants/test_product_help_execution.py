# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic_ai.models.test import TestModel
from pyfly.agentic.models import ModelFactory
from test_service import assistants as base_assistants
from test_service import configured

from koinon.assistants.execution import AssistantExecutor
from koinon.assistants.probe import ProviderProbe
from koinon.assistants.queue import AssistantQueue
from koinon.profiles.service import ProfileService


@pytest.fixture
async def assistants(tmp_path, monkeypatch):
    import pyfly.container.scanner as scanner

    original = scanner.scan_package

    def scan(package, container):
        original(package, container)
        if package == "koinon.assistants":
            for extension in ("koinon.tokens", "koinon.evidence", "koinon.exports", "koinon.sharing"):
                original(extension, container)

    monkeypatch.setattr(scanner, "scan_package", scan)
    async for value in base_assistants.__wrapped__(tmp_path):
        yield value


@pytest.mark.parametrize(
    "question,language,profile_language,expected",
    [
        ("Hola, ¿quién eres? Please answer in English.", "en", "es", "I'm"),
        ("Who are you? Responde en español.", "es", "en", "Soy"),
    ],
)
async def test_help_uses_current_brand_and_explicit_turn_language_without_fake_sources(
    assistants, monkeypatch, question, language, profile_language, expected
):
    service, context = assistants
    monkeypatch.setattr(
        ProviderProbe,
        "check",
        AsyncMock(
            return_value=[
                {"id": "connection", "status": "passed", "message": "Controlled"},
                {"id": "models", "status": "passed", "message": "Discovered"},
            ]
        ),
    )
    provider, agent = await configured(service)
    await service.validate_provider("issuer|admin", "north", provider["id"])
    from koinon.organization_branding.service import OrganizationBrandingService

    branding = context.get_bean(OrganizationBrandingService)
    branding.defaults = branding.defaults.model_copy(
        update={"assistant_name": "Sócrates", "product_name": "Corporate Brain"}
    )
    context.container.register_instance(
        ProfileService,
        SimpleNamespace(
            get=AsyncMock(
                return_value={
                    "locale": "en-US",
                    "time_zone": "UTC",
                    "response_language": profile_language,
                }
            )
        ),
    )
    model = TestModel(
        call_tools=[],
        custom_output_args={
            "outcome": "product_help",
            "help_topic": "identity",
            "language": language,
        },
    )
    monkeypatch.setattr(ModelFactory, "build_with_secret", lambda self, spec, secret: model)
    thread = await service.create_thread("issuer|viewer", "north", {})
    submitted = await service.submit(
        "issuer|viewer",
        "north",
        thread["id"],
        {
            "agent_id": agent["id"],
            "message": question,
            "client_request_id": "identity-help",
        },
    )
    run = await context.get_bean(AssistantQueue).claim("help-worker")
    await context.get_bean(AssistantExecutor).execute(run.id, "help-worker")
    message = (await service.messages("issuer|viewer", "north", thread["id"]))[-1]
    assert message["status"] == "completed" and expected in message["text"]
    assert "Sócrates" in message["text"] and "Corporate Brain" in message["text"]
    assert message["answer_policy"]["outcome"] == "product_help"
    assert message["presentation"]["effective_language"] == language
    assert message["citations"] == [] and message["artifacts"] == []
    rows = await service.active_results(await service.runs.find_by_id(submitted["run_id"]))
    trusted = [row for row in rows if row.kind == "product_context"]
    assert len(trusted) == 1 and trusted[0].payload["context"]["kind"] == "product_configuration"
    assert not [row for row in rows if row.kind in {"search", "query", "schema"}]
    release = next(row.payload["release"] for row in rows if row.kind == "answer_release")
    assert release["outcome"] == "product_help" and release["policy_version"] == "knowledge-only-v2"
    assert release["fact_ids"] == [] and release["source_refs"] == []
    assert [pin["id"] for pin in release["result_pins"]] == [trusted[0].id]
    from koinon.assistants.audit import AnswerAudits

    audit = await context.get_bean(AnswerAudits).get("issuer|viewer", "north", run.id)
    assert audit["product_context"]["assistant_name"] == "Sócrates"
    assert audit["sources"] == [] and audit["native_reads"] == []
    from koinon.evidence.ports import ConversationSnapshotPort
    from koinon.exports.dtos import ConversationExportInput, ExportCreate
    from koinon.exports.service import KnowledgeExports
    from koinon.sharing.dtos import ShareCreate, ShareReviewInput
    from koinon.sharing.service import ConversationShares

    snapshot = await context.get_bean(ConversationSnapshotPort).snapshot(
        "issuer|viewer", "north", thread["id"], [message["id"]]
    )
    assert snapshot.source_manifest_complete is True and snapshot.sources == ()
    assert snapshot.messages[0].source_ids == ()
    assert snapshot.messages[0].result_ids == (trusted[0].id,)
    exports = context.get_bean(KnowledgeExports)
    preview = await exports.preview(
        "issuer|viewer",
        "north",
        ConversationExportInput(
            kind="conversation", format="json", thread_id=thread["id"], message_ids=[message["id"]]
        ),
    )
    exported = await exports.create(
        "issuer|viewer", "north", ExportCreate(review_id=preview.id, expected_revision=preview.revision)
    )
    assert "Sócrates" in (await exports.download("issuer|viewer", "north", exported.id)).content.decode()
    shares = context.get_bean(ConversationShares)
    review = await shares.preview(
        "issuer|viewer", "north", ShareReviewInput(thread_id=thread["id"], message_ids=[message["id"]])
    )
    shared = await shares.create(
        "issuer|viewer", "north", ShareCreate(review_id=review.id, expected_revision=review.revision)
    )
    viewed = await shares.read("issuer|other", "north", shared.id)
    assert viewed.messages[0].text == message["text"] and not viewed.sources
    trusted[0].payload = {
        **trusted[0].payload,
        "context": {**trusted[0].payload["context"], "assistant_name": "Forged name"},
    }
    await service.results.save(trusted[0])
    from koinon.catalog.errors import AccessDenied

    with pytest.raises(AccessDenied):
        await exports.download("issuer|viewer", "north", exported.id)
    with pytest.raises(AccessDenied):
        await shares.read("issuer|other", "north", shared.id)
    masked = (await service.messages("issuer|viewer", "north", thread["id"]))[-1]
    assert "Sócrates" not in masked["text"] and "Forged name" not in masked["text"]
    assert (await context.get_bean(AnswerAudits).get("issuer|viewer", "north", run.id))[
        "product_context"
    ] is None
