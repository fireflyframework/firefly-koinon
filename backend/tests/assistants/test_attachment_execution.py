# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pyfly.agentic.types import BinaryContent
from pyfly.kernel import InvalidRequestException
from test_service import assistants as assistants

from koinon.assistants.lifecycle import timestamp
from koinon.knowledge.attachments.ports import AttachmentContent, AttachmentRef


def ref():
    return AttachmentRef(
        "file",
        "north",
        "thread",
        "issuer|viewer",
        "a" * 64,
        1,
        "Notes.md",
        "text/markdown",
        "document",
        30,
        timestamp() + timedelta(hours=1),
    )


async def test_private_text_budget_measures_exact_prompt_and_keeps_reference_metadata():
    from koinon.assistants.attachment_input import prepare_attachment_input

    item = ref()
    access = SimpleNamespace(
        content_for_model=AsyncMock(
            return_value=(AttachmentContent(item, text="Verified private text", complete=True),)
        )
    )
    seen = []

    async def fits(value):
        seen.append(value)
        return len(value) < 500

    result = await prepare_attachment_input(
        access,
        subject=item.subject,
        tenant_id=item.tenant_id,
        thread_id=item.thread_id,
        refs=(item,),
        question="Compare notes",
        fits_text=fits,
        input_modalities=["text"],
    )
    assert result.prompt.startswith("Compare notes")
    assert "Verified private text" in result.prompt and "untrusted" in result.prompt
    assert result.text == result.prompt
    assert result.evidence["attachments"][0]["sha256"] == item.sha256
    assert "data" not in result.evidence["attachments"][0]
    budget = access.content_for_model.call_args.kwargs["budget"]
    await budget.fits_text("replacement")
    assert "Compare notes" in seen[-1] and "replacement" in seen[-1]
    assert budget.allowed_media_types == frozenset()


async def test_binary_requires_positive_modality_and_native_token_count_before_input():
    from koinon.assistants.attachment_input import prepare_attachment_input

    item = ref()
    content = AttachmentContent(item, data=b"private-image", media_type="image/png", complete=True)
    access = SimpleNamespace(content_for_model=AsyncMock(return_value=(content,)))
    arguments = dict(
        subject=item.subject,
        tenant_id=item.tenant_id,
        thread_id=item.thread_id,
        refs=(item,),
        question="Read image",
        fits_text=AsyncMock(return_value=True),
    )
    for modalities in (["text"], ["text", "image"]):
        with pytest.raises(InvalidRequestException):
            await prepare_attachment_input(access, **arguments, input_modalities=modalities)
    counter = AsyncMock(return_value=True)
    result = await prepare_attachment_input(
        access, **arguments, input_modalities=["text", "image"], fits_binary=counter
    )
    assert isinstance(result.prompt[-1], BinaryContent)
    assert result.prompt[-1].data == b"private-image"
    counter.assert_awaited_once()
    assert "image/png" in access.content_for_model.call_args.kwargs["budget"].allowed_media_types


def test_native_prompt_identifies_product_without_forcing_response_prefix():
    from pathlib import Path

    from pyfly.agentic.prompts import PromptLoader

    import koinon.assistants.execution as execution

    prompt = PromptLoader.from_file(Path(execution.__file__).parent / "prompts/knowledge-guide.yaml").render(
        instructions="Approved agent policy",
        question="What is known?",
        locale="en-US",
        time_zone="UTC",
        response_language="auto",
    )
    assert "You are koinon" in prompt.system
    assert "Knowledge assistant" not in prompt.system
    assert "Approved agent policy" in prompt.system


@pytest.mark.parametrize(
    ("model_text", "visible_text"),
    [
        ("The private selected notes say twelve.", "The private selected notes say twelve."),
        ("Attachment file: Notes.md says twelve.", "Notes.md says twelve."),
    ],
)
async def test_selected_private_text_grounds_native_run_and_never_enters_later_unselected_history(
    assistants, monkeypatch, model_text, visible_text
):
    from dataclasses import replace

    from pydantic_ai.models.test import TestModel
    from pyfly.agentic.models import ModelFactory
    from test_service import configured

    from koinon.assistants.execution import AssistantExecutor
    from koinon.assistants.probe import ProviderProbe
    from koinon.assistants.queue import AssistantQueue
    from koinon.assistants.repositories import ChatRunRepository

    service, context = assistants
    monkeypatch.setattr(
        ProviderProbe,
        "check",
        AsyncMock(
            return_value=[{"id": "connection", "status": "passed"}, {"id": "models", "status": "passed"}]
        ),
    )
    provider, agent = await configured(service)
    await service.validate_provider("issuer|admin", "north", provider["id"])
    agent = await service.save_agent("issuer|admin", "north", {"tools": []}, agent["id"])
    model = TestModel(call_tools=[], custom_output_text=model_text)
    monkeypatch.setattr(ModelFactory, "build_with_secret", lambda self, spec, secret: model)
    thread = await service.create_thread("issuer|viewer", "north", {})
    item = replace(ref(), thread_id=thread["id"])
    access = SimpleNamespace(
        validate_selection=AsyncMock(return_value=(item,)),
        pin_selection=AsyncMock(),
        for_run=AsyncMock(return_value=(item,)),
        authorize_evidence=AsyncMock(),
        content_for_model=AsyncMock(
            return_value=(AttachmentContent(item, text="Notes say twelve.", complete=True),)
        ),
        summaries_for_message=AsyncMock(return_value=()),
    )
    service.attachments = access
    accepted = await service.submit(
        "issuer|viewer",
        "north",
        thread["id"],
        {
            "agent_id": agent["id"],
            "message": "What do my notes say?",
            "attachment_ids": [item.id],
            "client_request_id": "attachment-run",
        },
    )
    queue = context.get_bean(AssistantQueue)
    run = await queue.claim("file-worker")
    executor = context.get_bean(AssistantExecutor)
    await executor.execute(run.id, "file-worker")
    stored = await context.get_bean(ChatRunRepository).find_by_id(accepted["run_id"])
    assert stored.status == "completed", stored.error_code
    answer = (await service.messages("issuer|viewer", "north", thread["id"]))[-1]
    assert answer["text"] == visible_text
    assert answer["answer_policy"]["outcome"] == "grounded"
    results = await service.results.find_all(run_id=run.id)
    assert [row.kind for row in results if row.kind != "generation"] == ["attachment"]
    assert "Notes say twelve" not in str(results[0].payload)
    from koinon.assistants.audit import AnswerAudits
    from koinon.knowledge.attachments.dtos import AttachmentHistorySummary

    access.summaries_for_message.return_value = (
        AttachmentHistorySummary(
            id=item.id,
            filename=item.filename,
            media_type=item.media_type,
            kind="document",
            size_bytes=item.size_bytes,
            sha256=item.sha256,
            status="expired",
            revision=2,
            expires_at=timestamp() - timedelta(seconds=1),
            available=False,
        ),
    )
    audit = await context.get_bean(AnswerAudits).get("issuer|viewer", "north", run.id)
    assert audit["source_provenance_complete"] is True
    assert audit["private_files"][0]["used_revision"] == 1
    assert audit["private_files"][0]["sha256"] == item.sha256
    assert audit["private_files"][0]["availability"] == "expired"
    later = await service.submit(
        "issuer|viewer",
        "north",
        thread["id"],
        {
            "agent_id": agent["id"],
            "message": "Unrelated new question",
            "attachment_ids": [],
            "client_request_id": "without-file",
        },
    )
    current = await service.runs.find_by_id(later["run_id"])
    assert await executor.history(current) == []
    access.for_run.side_effect = InvalidRequestException("The private file expired")
    assert await executor.history(current) == []


async def test_private_context_never_exposes_shared_persisting_domain_tools():
    from koinon.assistants.execution import AssistantExecutor

    executor = object.__new__(AssistantExecutor)
    executor.assistants = SimpleNamespace(settings=SimpleNamespace(tool_result_tokens=4096))
    executor.queue = SimpleNamespace()
    enabled = ["search_knowledge", "query_dataset", "inspect_schema"]
    private = await executor.tools("run", "worker", enabled, attachment_refs=(ref(),))
    assert [tool.name for tool in private] == ["search_private_attachments"]
    from koinon.assistants.tool_offering import AssistantToolAvailability

    executor.authority = AsyncMock(
        return_value=(
            SimpleNamespace(tenant_id="north", scope={}),
            SimpleNamespace(subject="issuer|reader"),
            None,
            None,
        )
    )
    executor.tool_availability = AssistantToolAvailability(
        SimpleNamespace(authorize=AsyncMock()), SimpleNamespace(validate_scope=AsyncMock(return_value={}))
    )
    ordinary = await executor.tools("run", "worker", enabled)
    assert [tool.name for tool in ordinary] == enabled
