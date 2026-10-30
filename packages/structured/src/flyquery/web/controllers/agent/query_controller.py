# Copyright 2024-2026 Firefly Software Foundation
# Modifications Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
# Modifications Copyright 2026 Firefly Software Foundation
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

"""Agent-tier query pipeline controller.

``/api/v1/agent/query`` — same pipeline as the user-tier ``/api/v1/query``
but requires a valid ``X-Agent-Token`` with ``flyquery.query:read`` scope.

Delegates to the same :class:`QueryService` as the user-tier controller.
Auth difference: verifies ``X-Agent-Token`` instead of a JWT bearer.

Path conventions:
* ``POST /api/v1/agent/query``          -- full sync pipeline
* ``POST /api/v1/agent/query:explain``  -- Grounding + Generation only
* ``POST /api/v1/agent/query:validate`` -- Grounding + Generation + AST + ScopeGuard
* ``POST /api/v1/agent/query/stream``   -- SSE event stream
"""

from __future__ import annotations

import uuid

from pyfly.container import rest_controller
from pyfly.web import Body, Valid, post_mapping, request_mapping
from starlette.requests import Request
from starlette.responses import StreamingResponse

from flyquery.core.services.auth.agent_token_service import AgentTokenService
from flyquery.core.services.execution.scope_guard import ScopeGuardError
from flyquery.core.services.query.runtime import StructuredQueryRuntimeFactory
from flyquery.interfaces.query import (
    AnswerResponse,
    BatchQueryRequest,
    BatchQueryResponse,
    ClarificationFrame,
    ExplainResponse,
    QueryRequest,
    ValidateResponse,
)
from flyquery.web.controllers.query_controller import QueryController
from flyquery.web.conventions import (
    HEADER_AGENT_TOKEN,
    FireflyHTTPException,
    IdempotencyStore,
    InvalidRequest,
    tenant_context_from_request,
)
from flyquery.web.idempotent_handler import replay_dedup
from flyquery.web.native_agent_grant import verified_agent_context

_SCOPE_QUERY_READ = "flyquery.query:read"


class MissingAgentToken(FireflyHTTPException):
    status = 401
    code = "missing_agent_token"
    title = "Missing X-Agent-Token header"


def _parse_workspace_id(s: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(s))
    except (ValueError, AttributeError) as exc:
        raise InvalidRequest(f"workspace_id {s!r} is not a valid UUID") from exc


@rest_controller(name="structured.AgentQueryController")
@request_mapping("/api/v1/agent")
class AgentQueryController:
    """Token-authorized transport over the shared structured query runtime."""

    def __init__(
        self,
        runtime_factory: StructuredQueryRuntimeFactory,
        query_controller: QueryController,
        agent_token_service: AgentTokenService,
        idempotency_store: IdempotencyStore,
    ) -> None:
        self._runtime_factory = runtime_factory
        self._query_controller = query_controller
        self._token_service = agent_token_service
        self._idempotency_store = idempotency_store

    async def _verify(self, http_request: Request) -> None:
        """Verify X-Agent-Token with flyquery.query:read scope.

        :raises MissingAgentToken: when header is absent
        :raises 403: when token does not carry the required scope
        """
        if verified_agent_context(http_request, scope=_SCOPE_QUERY_READ) is not None:
            return
        token = http_request.headers.get(HEADER_AGENT_TOKEN)
        if not token:
            raise MissingAgentToken("X-Agent-Token header is required for /api/v1/agent/* routes.")
        ctx = tenant_context_from_request(http_request)
        await self._token_service.verify(
            token,
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            scope=_SCOPE_QUERY_READ,
        )

    # ------------------------------------------------------------------
    # POST /api/v1/agent/query
    # ------------------------------------------------------------------

    @post_mapping("/query")
    async def query(
        self,
        http_request: Request,
        body: Valid[Body[QueryRequest]],
    ) -> AnswerResponse:
        """Run the full NL → SQL → result pipeline (agent-tier).

        Replay-dedup'd via ``Idempotency-Key``. The header is *required*
        on the agent surface so an at-least-once delivery agent (which
        retries on network error) doesn't burn budget by re-running the
        same multi-LLM pipeline twice.

        :param http_request: Starlette request (provides tenant context + agent token)
        :param body: validated QueryRequest
        :return: AnswerResponse
        """
        await self._verify(http_request)
        ctx = tenant_context_from_request(http_request)
        workspace_id = _parse_workspace_id(ctx.workspace_id)

        async def _do_query() -> AnswerResponse:
            async with self._runtime_factory.unit(with_conversation=True) as runtime:
                svc = runtime.pipeline
                result = await svc.answer(
                    tenant_id=ctx.tenant_id,
                    workspace_id=workspace_id,
                    dataset_id=body.dataset_id,
                    question=body.question,
                    scopes={_SCOPE_QUERY_READ},
                    conversation_id=body.conversation_id,
                )

            return AnswerResponse(
                query_id=result.query_id,
                sql=result.sql,
                execution_status=result.execution_status,
                preview=result.preview,
                row_count=result.row_count,
                truncated=result.truncated,
                elapsed_ms=result.elapsed_ms,
                chart_hint=result.chart_hint,
                explanation=result.explanation,
                clarification=result.clarification,
                grounded_summary=result.grounded_summary,
            )

        return await replay_dedup(
            request=http_request,
            store=self._idempotency_store,
            tenant_id=ctx.tenant_id,
            route="POST /api/v1/agent/query",
            handler=_do_query,
            status_code=200,
            require_key=True,
        )

    # ------------------------------------------------------------------
    # POST /api/v1/agent/query:batch
    # ------------------------------------------------------------------

    @post_mapping("/query:batch")
    async def batch(
        self,
        http_request: Request,
        body: Valid[Body[BatchQueryRequest]],
    ) -> BatchQueryResponse:
        """Agent-tier mirror of POST /api/v1/query:batch.

        Shares the managed query runtime with the user-tier batch route.
        Replay-dedup'd via ``Idempotency-Key`` (required) -- a batch
        is N parallel multi-LLM pipelines, the costliest single
        request shape in the API.
        """
        await self._verify(http_request)
        ctx = tenant_context_from_request(http_request)

        async def _do_batch() -> BatchQueryResponse:
            import asyncio

            from flyquery.interfaces.query import BatchQueryResultItem

            workspace_id = _parse_workspace_id(ctx.workspace_id)

            async def _ask(idx: int, item):
                try:
                    async with self._runtime_factory.unit() as runtime:
                        svc = runtime.pipeline
                        r = await svc.answer(
                            tenant_id=ctx.tenant_id,
                            workspace_id=workspace_id,
                            dataset_id=item.dataset_id,
                            question=item.question,
                            scopes={_SCOPE_QUERY_READ},
                            conversation_id=item.conversation_id,
                        )
                    return BatchQueryResultItem(
                        index=idx,
                        status="OK",
                        query_id=r.query_id,
                        sql=r.sql,
                        execution_status=r.execution_status,
                        preview=r.preview,
                        row_count=r.row_count,
                        elapsed_ms=r.elapsed_ms,
                        chart_hint=r.chart_hint,
                        explanation=r.explanation,
                        grounded_summary=r.grounded_summary,
                    )
                except Exception as exc:  # noqa: BLE001
                    return BatchQueryResultItem(index=idx, status="FAILED", error=str(exc))

            results = await asyncio.gather(*[_ask(i, item) for i, item in enumerate(body.queries)])
            succeeded = sum(1 for r in results if r.status == "OK")
            return BatchQueryResponse(
                results=list(results),
                total_queries=len(results),
                succeeded=succeeded,
                failed=len(results) - succeeded,
            )

        return await replay_dedup(
            request=http_request,
            store=self._idempotency_store,
            tenant_id=ctx.tenant_id,
            route="POST /api/v1/agent/query:batch",
            handler=_do_batch,
            status_code=200,
            require_key=True,
        )

    # ------------------------------------------------------------------
    # POST /api/v1/agent/query:explain
    # ------------------------------------------------------------------

    @post_mapping("/query:explain")
    async def explain(
        self,
        http_request: Request,
        body: Valid[Body[QueryRequest]],
    ) -> ExplainResponse:
        """Run Grounding + Generation only (agent-tier).

        :param http_request: Starlette request
        :param body: validated QueryRequest
        :return: ExplainResponse with candidate SQL and reasoning
        """
        await self._verify(http_request)
        ctx = tenant_context_from_request(http_request)
        workspace_id = _parse_workspace_id(ctx.workspace_id)

        async with self._runtime_factory.unit(preview=True) as runtime:
            retriever, reranker = runtime.retriever, runtime.reranker

            bundle = await retriever.retrieve(
                body.question,
                dataset_id=body.dataset_id,
                workspace_id=workspace_id,
                top_k_schema=runtime.settings.top_k_schema * 3,
            )
            schema_hits = bundle.get("schema_objects", [])
            reranked = await reranker.rerank(body.question, schema_hits, top_n=runtime.settings.top_k_schema)
            bundle["schema_objects"] = reranked

            grounding_agent = runtime.grounding_agent
            grounded = await grounding_agent.run(
                {"question": body.question, "bundle": bundle, "starting_point_sql": None}
            )

            generation_agent = runtime.generation_agent
            gen_out = await generation_agent.run(
                {"grounded": grounded, "question": body.question, "starting_point_sql": None}
            )
            candidate = gen_out.candidates[0]

        clarification: ClarificationFrame | None = None
        if grounded.confidence < runtime.settings.grounding_min_confidence and grounded.missing_info:
            clarification = ClarificationFrame(questions=grounded.missing_info, reasons=[])

        return ExplainResponse(
            sql=candidate.sql,
            reasoning=candidate.reasoning,
            confidence=candidate.confidence,
            grounded_summary={
                "path": grounded.path,
                "confidence": grounded.confidence,
                "table_count": len(grounded.tables),
            },
            clarification=clarification,
        )

    # ------------------------------------------------------------------
    # POST /api/v1/agent/query:validate
    # ------------------------------------------------------------------

    @post_mapping("/query:validate")
    async def validate(
        self,
        http_request: Request,
        body: Valid[Body[QueryRequest]],
    ) -> ValidateResponse:
        """Run Grounding + Generation + AST + ScopeGuard (agent-tier).

        :param http_request: Starlette request
        :param body: validated QueryRequest
        :return: ValidateResponse
        """
        await self._verify(http_request)
        ctx = tenant_context_from_request(http_request)
        workspace_id = _parse_workspace_id(ctx.workspace_id)

        async with self._runtime_factory.unit(preview=True) as runtime:
            retriever, reranker = runtime.retriever, runtime.reranker

            bundle = await retriever.retrieve(
                body.question,
                dataset_id=body.dataset_id,
                workspace_id=workspace_id,
                top_k_schema=runtime.settings.top_k_schema * 3,
            )
            schema_hits = bundle.get("schema_objects", [])
            reranked = await reranker.rerank(body.question, schema_hits, top_n=runtime.settings.top_k_schema)
            bundle["schema_objects"] = reranked

            grounding_agent = runtime.grounding_agent
            grounded = await grounding_agent.run(
                {"question": body.question, "bundle": bundle, "starting_point_sql": None}
            )

            generation_agent = runtime.generation_agent
            gen_out = await generation_agent.run(
                {"grounded": grounded, "question": body.question, "starting_point_sql": None}
            )
            chosen_sql = gen_out.candidates[0].sql

        ast = runtime.ast_classifier.classify(chosen_sql)
        scope_error: str | None = None
        try:
            runtime.scope_guard.check(
                classification=ast,
                scopes={_SCOPE_QUERY_READ},
                table_kinds_by_name={},
                dataset_allowlist=None,
                dataset_of_table={},
            )
        except ScopeGuardError as exc:
            scope_error = str(exc)

        clarification: ClarificationFrame | None = None
        if grounded.confidence < runtime.settings.grounding_min_confidence and grounded.missing_info:
            clarification = ClarificationFrame(questions=grounded.missing_info, reasons=[])

        return ValidateResponse(
            sql=chosen_sql,
            ast_classification=ast.classification,
            table_refs=list(ast.table_refs),
            single_statement=ast.single_statement,
            scope_error=scope_error,
            clarification=clarification,
        )

    # ------------------------------------------------------------------
    # POST /api/v1/agent/query/stream
    # ------------------------------------------------------------------

    @post_mapping("/query/stream")
    async def stream(
        self,
        http_request: Request,
        body: Valid[Body[QueryRequest]],
    ) -> StreamingResponse:
        """Run the pipeline as SSE stream (agent-tier).

        :param http_request: Starlette request
        :param body: validated QueryRequest
        :return: StreamingResponse with text/event-stream
        """
        await self._verify(http_request)
        ctx = tenant_context_from_request(http_request)
        workspace_id = _parse_workspace_id(ctx.workspace_id)

        return StreamingResponse(
            self._query_controller._stream_events(
                tenant_id=ctx.tenant_id,
                workspace_id=workspace_id,
                request=body,
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )
