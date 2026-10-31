# Copyright 2024-2026 Firefly Software Foundation
# Modifications Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""RLM answerer -- whole-document corpus + CodeAct REPL with citations.

Drop-in alternative to the RAG :class:`AnswerService`: same ``answer()``
contract (``AnswerRequest`` in, ``AnswerResponse`` out), so the query
dispatcher can swap one for the other. Instead of hybrid retrieval +
single grounded LLM call, it builds the whole-document corpus
(:class:`CanonCorpusBuilder`), runs the Recursive Language Model engine
(:class:`RLMSession` driven by an :class:`RlmChatClient` -- Anthropic or
Azure OpenAI, per ``FLYCANON_RLM_ROOT_MODEL``) inside
``asyncio.to_thread`` so the synchronous engine never blocks the event
loop, then maps the engine's citation dicts back to :class:`Hit` rows
via :meth:`CanonDocStore.resolve`.

Engine citations are ``{"filing": key, "page": int (0-based), "content":
snippet}``; :class:`Hit.page` is 1-based, so pages are shifted by one and
clamped to ``>= 1``. Citations whose ``filing`` key no longer resolves to
a source are dropped.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from collections.abc import Callable

from pyfly.kernel import ServiceUnavailableException

from flycanon.config import CanonSettings
from flycanon.core.agents.model_bindings import current_scope, model_reference
from flycanon.core.services.billing.cost_service import CostService
from flycanon.core.services.query import provenance
from flycanon.core.services.query.rlm.chat import RlmChatClient
from flycanon.core.services.query.rlm.citation_mapper import map_citations as _map_citations
from flycanon.core.services.query.rlm.corpus import CanonCorpusBuilder, Filters
from flycanon.core.services.query.rlm.session import RLMSession
from flycanon.interfaces.dtos.query import AnswerRequest, AnswerResponse
from flycanon.interfaces.knowledge_corpus import RlmCorpus

logger = logging.getLogger(__name__)

# The not-found sentinels the engine emits when the evidence is absent
# (see the ``final("the documents do not contain this", ...)`` guidance in
# the RLM system prompt). Used -- alongside an empty citation list -- as a
# fallback for deciding ``no_answer`` when the engine's structured
# ``found=False`` flag is not set.
_NOT_FOUND_MARKERS = ("do not contain", "not found", "no documents", "cannot find")

# Returned when the engine yields no usable answer text -- e.g. the CodeAct
# loop exhausted ``rlm_max_iters`` without ever calling ``final()`` and the
# plain-text fallback came back empty. Paired with ``no_answer=True`` so the
# caller treats it as an explanatory note rather than a substantive answer.
_NO_ANSWER_NOTE = "The selected knowledge does not contain enough evidence to answer this question."

# Cap on how many prior turns we fold into the question for conversational
# parity, and how much of each we keep -- bounded so a long history can't
# blow up the orchestrator's first prompt.
_MAX_PRIOR_TURNS = 6
_PRIOR_TURN_CHARS = 500


class RLMAnswerService:
    """RLM answerer mirroring the RAG :class:`AnswerService` interface.

    ``corpus_builder`` / ``client`` are injected so tests can supply a
    fake corpus and a fake (non-networked) chat client. ``client`` is the
    provider-agnostic :class:`RlmChatClient`; which provider it speaks is
    decided once, at boot, by
    :func:`~flycanon.core.services.query.rlm.chat.build_rlm_client`.
    """

    def __init__(
        self,
        *,
        corpus_builder: CanonCorpusBuilder,
        client: RlmChatClient,
        settings: CanonSettings,
        cost_service: CostService,
    ) -> None:
        self._corpus_builder = corpus_builder
        self._client = client
        self._settings = settings
        self._cost_service = cost_service

    def _request_client(self) -> RlmChatClient:
        from flycanon.core.services.query.rlm.native_client import NativeRlmChatClient

        if current_scope() is not None:
            factory = self._settings._agent_factory
            if factory is None:
                raise ServiceUnavailableException(
                    "Bind the context-owned AgentFactory for the selected RLM connection",
                    code="KNOWLEDGE_MODEL_BINDING_REQUIRED",
                )
            return NativeRlmChatClient.from_binding(factory)
        return self._client.fork()

    async def answer(
        self,
        request: AnswerRequest,
        *,
        prior_turns: list[tuple[str, str]] | None = None,
        tenant_id: str | None = None,
        workspace_id: str | None = None,
        on_turn: Callable[[int, list[str]], None] | None = None,
    ) -> AnswerResponse:
        """Single-turn (or conversational) RLM answer.

        Mirrors :meth:`AnswerService.answer`: ``tenant_id`` /
        ``workspace_id`` are the authoritative scope (the corpus builder
        lists the workspace's sources under them), and ``prior_turns`` is
        an optional ``[(user_text, assistant_text), ...]`` conversational
        context. The reported ``model`` is the RLM orchestrator model
        (``settings.rlm_root_model``), which drives the CodeAct loop.

        ``on_turn`` is an optional per-REPL-turn progress hook the
        streaming controllers pass to surface live progress; it stays
        ``None`` on the non-streaming path. It fires from the engine's
        worker thread, so the caller is responsible for marshalling work
        back onto its event loop.
        """
        start = time.perf_counter()
        scope = current_scope()
        required = scope is not None and scope.required
        model_id = model_reference("documents.rlm", self._settings.rlm_root_model)

        docs = await self._corpus_builder.build(
            tenant_id=tenant_id or "",
            workspace_id=workspace_id or "",
            filters=_filters_from_request(request),
        )
        if len(docs) == 0:
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            return AnswerResponse(
                answer=("The selected knowledge does not provide enough evidence to answer this question."),
                citations=[],
                model=model_id,
                elapsed_ms=elapsed_ms,
                no_answer=True,
            )

        corpus_context = await provenance.corpus(docs)

        # Per-request lever: a hard multi-fact question can opt into twice the
        # configured iteration budget (rlm_max_iters * 2) without a global bump.
        max_iters = self._settings.rlm_max_iters
        if request.extended_reasoning:
            max_iters *= 2
        question = _question_with_history(request.question, prior_turns)
        # Self-consistency guard (FLYCANON_RLM_SELF_CONSISTENCY): >1 runs the engine
        # N times in parallel and selects the most-grounded answer, clawing back the
        # run-to-run variance. Only on the non-streaming path (on_turn is None);
        # streaming keeps a single run so the live turns map to one trajectory.
        n = max(1, self._settings.rlm_self_consistency)
        if n > 1 and on_turn is None:
            runs = await asyncio.gather(
                *(
                    asyncio.to_thread(self._run_once, docs, question, max_iters, None, corpus_context)
                    for _ in range(n)
                ),
                return_exceptions=True,
            )
            if required:
                for run in runs:
                    if isinstance(run, BaseException):
                        raise run
            await provenance.authorize()
            if required:
                answer_text, cites, engine_no_answer, usage = await asyncio.to_thread(
                    provenance.worker(self._select_consistent), question, runs
                )
                await provenance.authorize()
                if current_scope() is not scope:
                    raise ServiceUnavailableException(
                        "The admitted knowledge connection lifetime has ended",
                        code="KNOWLEDGE_MODEL_SCOPE_CLOSED",
                    )
            else:
                answer_text, cites, engine_no_answer, usage = self._select_consistent(question, runs)
        else:
            answer_text, cites, engine_no_answer, usage = await asyncio.to_thread(
                self._run_once, docs, question, max_iters, on_turn, corpus_context
            )

        await provenance.authorize()
        citations = _map_citations(cites, docs)
        # A blank answer is a degenerate non-answer: the CodeAct loop ran out of
        # iterations without calling ``final()``, so the engine handed back an
        # empty string with ``found`` defaulted to True. Surface it as a
        # detectable no-answer with an explanatory note instead of an empty body
        # the caller cannot distinguish from a real answer.
        blank_answer = not answer_text.strip()
        # Trust the engine's structured no-answer flag first; keep the
        # text-marker check as a fallback for models that answer in plain text
        # without passing ``found=False``.
        no_answer = engine_no_answer or blank_answer or (not citations and _looks_not_found(answer_text))
        if blank_answer:
            logger.warning(
                "rlm produced no usable answer text for question=%s (docs=%d); returning no_answer",
                request.question[:80],
                len(docs),
            )
            answer_text = _NO_ANSWER_NOTE
            citations = []

        if required and not no_answer and not citations:
            raise ServiceUnavailableException(
                "An answer requires citations to executed immutable knowledge inputs",
                code="EVIDENCE_UNAVAILABLE",
            )
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        await self._record_cost(usage, elapsed_ms, tenant_id, workspace_id)
        await provenance.authorize()
        if required and current_scope() is not scope:
            raise ServiceUnavailableException(
                "The admitted knowledge connection lifetime has ended",
                code="KNOWLEDGE_MODEL_SCOPE_CLOSED",
            )
        logger.info(
            "rlm answered question=%s docs=%d citations=%d elapsed_ms=%d",
            request.question[:80],
            len(docs),
            len(citations),
            elapsed_ms,
        )
        return AnswerResponse(
            answer=answer_text,
            citations=citations,
            model=model_id,
            elapsed_ms=elapsed_ms,
            no_answer=no_answer,
        )

    @provenance.worker
    def _run_once(
        self,
        docs: RlmCorpus,
        question: str,
        max_iters: int,
        on_turn: Callable[[int, list[str]], None] | None,
        corpus_context: str | None = None,
    ) -> tuple[str, list[dict], bool, dict]:
        """One RLM run on a freshly forked client; returns ``(answer, cites,
        no_answer, usage)``. Runs synchronously (the caller wraps it in a
        thread) so several runs can proceed in parallel for self-consistency.
        """
        client = self._request_client()
        session = RLMSession(
            client,
            max_depth=self._settings.rlm_max_depth,
            max_iters=max_iters,
            sub_budget=self._settings.rlm_sub_budget,
            on_turn=on_turn,
            sandbox_mode=self._settings.rlm_sandbox,
            sandbox_timeout_s=self._settings.rlm_sandbox_timeout_s,
            corpus_context=corpus_context,
        )
        answer, cites, no_answer = session.run(question, docs)
        return answer, cites, no_answer, client.token_totals()

    def _select_consistent(self, question: str, runs: list) -> tuple[str, list[dict], bool, dict]:
        """Select the most-grounded answer across self-consistency runs.

        ``runs`` is the ``asyncio.gather(..., return_exceptions=True)`` result:
        a mix of ``(answer, cites, no_answer, usage)`` tuples and Exceptions.
        Standalone failed runs are dropped; required callers reject failures
        before selection. A real (non-blank, answered) candidate is preferred;
        ties are broken by an LLM selector. Successful-run and selector usage
        is merged here; failed-run billing is separate.
        """
        ok = [r for r in runs if isinstance(r, tuple)]
        if not ok:
            return _NO_ANSWER_NOTE, [], True, _merge_usage([])
        usage = _merge_usage([r[3] for r in ok])
        viable = [(a, c, na) for (a, c, na, _u) in ok if (a or "").strip() and not na]
        pool = viable or [(a, c, na) for (a, c, na, _u) in ok]
        if len(pool) == 1:
            answer, cites, no_answer = pool[0]
            return answer, cites, no_answer, usage
        idx, sel_usage = self._selector_pick(question, [a for (a, _c, _na) in pool])
        answer, cites, no_answer = pool[idx]
        logger.info(
            "rlm self-consistency: %d/%d runs viable, selected candidate %d",
            len(pool),
            len(runs),
            idx + 1,
        )
        return answer, cites, no_answer, _merge_usage([usage, sel_usage])

    def _selector_pick(self, question: str, answers: list[str]) -> tuple[int, dict]:
        """Ask the model to pick the most-grounded/consistent candidate.

        Required scopes reject selector failures. Standalone selection retains
        its candidate-zero fallback for errors or invalid replies.
        """
        client = self._request_client()
        scope = current_scope()
        required = scope is not None and scope.required
        listing = "\n\n".join(f"[{i + 1}]\n{(a or '')[:6000]}" for i, a in enumerate(answers))
        prompt = (
            f"Question:\n{question}\n\n{len(answers)} independent answers were produced for this "
            "question by the same engine. Select the SINGLE best one -- the most grounded in the "
            "source documents, the most complete, and the most consistent with what the majority "
            "of the answers agree on. Reply with ONLY the candidate number.\n\n" + listing
        )
        try:
            provenance.model("rlm.selector", prompt)
            reply = client.complete(prompt)
        except Exception:  # noqa: BLE001 -- standalone selection retains its fallback
            if required:
                raise
            return 0, client.token_totals()
        if required:
            value = reply.strip() if type(reply) is str else ""
            if (
                len(value) > len(str(len(answers)))
                or not re.fullmatch(r"[1-9][0-9]*", value)
                or not 1 <= int(value) <= len(answers)
            ):
                raise ServiceUnavailableException(
                    "The selected model did not return one valid candidate number.",
                    code="RLM_SELECTOR_PROTOCOL_REQUIRED",
                )
            return int(value) - 1, client.token_totals()
        match = re.search(r"\d+", reply or "")
        idx = (int(match.group()) - 1) if match else 0
        if idx < 0 or idx >= len(answers):
            idx = 0
        return idx, client.token_totals()

    async def _record_cost(
        self,
        usage: dict,
        elapsed_ms: int,
        tenant_id: str | None,
        workspace_id: str | None,
    ) -> None:
        """Best-effort cost record for one RLM answer query.

        A billing-write failure must never fail the user's answer, so the
        record call is wrapped and only logged on error.
        """
        try:
            await self._cost_service.record(
                agent_name="flycanon-rlm-answerer",
                model=self._settings.rlm_root_model,
                input_tokens=usage["input_tokens"],
                output_tokens=usage["output_tokens"],
                cost_usd=usage["estimated_cost_usd"],
                tenant_id=tenant_id or "default",
                workspace_id=workspace_id or "default",
                latency_ms=elapsed_ms,
            )
        except Exception:  # noqa: BLE001 -- billing must not break the answer
            logger.warning("failed to record RLM query cost", exc_info=True)


def _filters_from_request(request: AnswerRequest) -> Filters:
    """Map the ``AnswerRequest`` filter fields onto the corpus ``Filters``.

    Enum-valued dimensions are passed as their ``.value`` strings, the
    same way the RAG search service hands plain strings to the retrieval
    filter.
    """
    return Filters(
        source_ids=request.source_ids,
        knowledge_item_ids=request.knowledge_item_ids,
        domains=[d.value for d in request.domains] if request.domains else None,
        jurisdictions=[j.value for j in request.jurisdictions] if request.jurisdictions else None,
        tags=request.tags,
        statuses=[s.value for s in request.statuses] if request.statuses else None,
    )


def _question_with_history(
    question: str,
    prior_turns: list[tuple[str, str]] | None,
) -> str:
    """Prepend a short, bounded ``Previous turns:`` block to the question.

    Conversational parity with the RAG path: when ``prior_turns`` are
    present, the most recent turns are folded into the question the
    orchestrator sees. Empty / ``None`` history leaves the question
    untouched.
    """
    if not prior_turns:
        return question
    lines: list[str] = []
    for user_text, assistant_text in prior_turns[-_MAX_PRIOR_TURNS:]:
        if not user_text and not assistant_text:
            continue
        lines.append(f"User: {(user_text or '')[:_PRIOR_TURN_CHARS]}")
        lines.append(f"Assistant: {(assistant_text or '')[:_PRIOR_TURN_CHARS]}")
    if not lines:
        return question
    history = "\n".join(lines)
    return f"Previous turns:\n{history}\n\nCurrent question: {question}"


def _looks_not_found(answer: str) -> bool:
    """Whether the answer text matches an engine not-found sentinel."""
    lowered = answer.lower()
    return any(marker in lowered for marker in _NOT_FOUND_MARKERS)


def _merge_usage(usages: list[dict]) -> dict:
    """Sum token-usage dicts across self-consistency runs + the selector call."""
    merged: dict = {"input_tokens": 0, "output_tokens": 0, "estimated_cost_usd": 0.0, "by_model": {}}
    for usage in usages:
        if not isinstance(usage, dict):
            continue
        merged["input_tokens"] += usage.get("input_tokens", 0)
        merged["output_tokens"] += usage.get("output_tokens", 0)
        merged["estimated_cost_usd"] += usage.get("estimated_cost_usd", 0.0)
        for name, tally in (usage.get("by_model") or {}).items():
            entry = merged["by_model"].setdefault(name, {"input": 0, "output": 0})
            entry["input"] += tally.get("input", 0)
            entry["output"] += tally.get("output", 0)
    return merged
