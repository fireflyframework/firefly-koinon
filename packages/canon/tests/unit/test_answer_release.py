# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from flycanon.config import CanonSettings
from flycanon.core.services.query.answer_service import AnswerOutput, AnswerService
from flycanon.core.services.retrieval.retrieval_service import Hit
from flycanon.interfaces.dtos.query import AnswerRequest


@pytest.mark.asyncio
@pytest.mark.parametrize("ids", [["chunk"], ["chunk", "forged"], []])
async def test_direct_rag_answer_never_releases_model_prose_even_with_a_real_source_id(ids):
    hit = Hit("chunk", "source", None, None, "Recorded policy requires approval.", 1.0, None, None, {})
    service = AnswerService(
        retrieval=SimpleNamespace(search=AsyncMock(return_value=SimpleNamespace(hits=[hit]))),
        prompt=SimpleNamespace(render=lambda **_: ("system", "user")),
        default_model="model",
        fallback_model=None,
        settings=CanonSettings(),
    )
    service._call_model = AsyncMock(
        return_value=AnswerOutput(answer="A poem and invented facts.", citation_chunk_ids=ids)
    )
    result = await service.answer(AnswerRequest(question="Policy?"), tenant_id="tenant", workspace_id="space")
    assert "poem" not in result.answer and "invented" not in result.answer
    if ids == ["chunk"]:
        assert hit.content in result.answer and not result.no_answer
        assert [row.chunk_id for row in result.citations] == ["chunk"]
    else:
        assert result.no_answer and result.citations == []


@pytest.mark.asyncio
@pytest.mark.parametrize("quote,valid", [("Recorded policy", True), ("invented visual claim", False)])
async def test_direct_rlm_requires_actual_page_text_and_never_promotes_derived_prose(
    monkeypatch, quote, valid
):
    from .test_rlm_answer_service import (
        FakeCorpusBuilder,
        FakeSession,
        SourceMeta,
        _docs,
        _request,
        _service,
        svc_mod,
    )

    docs = _docs(
        {"policy": ["Recorded policy requires approval."]},
        {
            "policy": SourceMeta(
                source_id="source",
                filename="policy.txt",
                title="Policy",
                kind="txt",
                object_store_key="key",
                content_sha256="digest",
            )
        },
    )
    monkeypatch.setattr(
        svc_mod,
        "RLMSession",
        lambda *a, **k: FakeSession(
            "Unsupported model analysis.", [{"filing": "policy", "page": 0, "content": quote}]
        ),
    )
    result = await _service(FakeCorpusBuilder(docs)).answer(
        _request(), tenant_id="tenant", workspace_id="space"
    )
    assert "Unsupported model analysis" not in result.answer
    assert result.no_answer is not valid
    if valid:
        assert quote in result.answer and result.citations[0].content == quote
    else:
        assert result.citations == []
