# Copyright 2024-2026 Firefly Software Foundation
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

"""QueryService orchestrator — the complete NL → SQL → result pipeline.

Execution order
---------------
1.  Retrieve schema KB hits (BM25 + pgvector via HybridRetriever)
2.  Rerank top-K schema objects via the cross-encoder reranker
3.  Run GroundingAgent → GroundedContext
4.  Semantic-layer fast-path (SEMANTIC_LAYER + metrics) → compile SQL via MetricFlowCompiler
    OR synthesis path → run GenerationAgent → take candidates[0]
5.  AST classify the chosen SQL (sqlglot)
6.  ScopeGuard.check() — table-kind + dataset allowlist + scope enforcement
7.  Resolve parquet paths for AST table_refs (TableResolver)
8.  DuckDBExecutor.execute() — execute with LIMIT row_cap+1
9.  CriticAgent loop: on ExecutionError, retry up to max_refine_retries times
10. ExplainerAgent — NL summary + chart hint
11. Persist flyquery_queries row via QueryRepository
12. Upload result Parquet + upsert flyquery_query_results via ResultUploader
13. Optional authorized auto-learning — first-shot OK + no PII → create an unapproved draft
14. Return AnswerResult
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any

from flyquery.core.agents.model_bindings import model_reference
from flyquery.core.services.examples.auto_learner import autolearn_allowed
from flyquery.core.services.execution.ast_classifier import AstClassifier
from flyquery.core.services.execution.duckdb_executor import ExecutionError, ExecutionResult
from flyquery.core.services.execution.scope_guard import ScopeGuard, ScopeGuardError
from flyquery.core.services.query import provenance, value_anchoring
from flyquery.core.services.query.dtos import AnswerResult as AnswerResult
from flyquery.core.services.query.prompts import (
    _render_critic_prompt,
    _render_explainer_prompt,
    _render_generation_prompt,
    _render_grounding_prompt,
)
from flyquery.core.services.query.sql_names import bind_registered_table_names
from flyquery.core.services.semantic.compiler import SemanticCompiler
from flyquery.core.services.tables.table_repository import TableRepository

logger = logging.getLogger(__name__)


class QueryService:
    """Orchestrates the Grounding → Generation → AST → Exec → Critic → Explainer loop.

    All agents are injected (built by ``build_*_agent`` factories) so they
    can be replaced with canned fakes in unit tests without touching LLM APIs.

    :param retriever: HybridRetriever
    :param reranker: cross-encoder reranker (NoopReranker when unavailable)
    :param grounding_agent: FireflyAgent[GroundedContext]
    :param generation_agent: FireflyAgent[GeneratedCandidates]
    :param critic_agent: FireflyAgent[RefinedSql]
    :param explainer_agent: FireflyAgent[ResultExplanation]
    :param ast_classifier: AstClassifier
    :param scope_guard: ScopeGuard
    :param table_resolver: TableResolver
    :param executor: DuckDBExecutor
    :param query_repo: QueryRepository
    :param settings: FlyquerySettings
    :param result_uploader: ResultUploader
    :param auto_learner: AutoLearner
    :param table_repository: native metadata repository for the dataset firewall
    :param metric_compiler: MetricFlowCompiler (optional — used for SEMANTIC_LAYER path)
    :param semantic_repo: SemanticRepository (optional — fetches compiled SQL)
    :param conversation_service: ConversationService (optional — Phase E drill-down)
    """

    def __init__(
        self,
        retriever,
        reranker,
        grounding_agent,
        generation_agent,
        critic_agent,
        explainer_agent,
        ast_classifier: AstClassifier,
        scope_guard: ScopeGuard,
        table_resolver,
        executor,
        query_repo,
        settings,
        result_uploader,
        auto_learner,
        table_repository: TableRepository,
        metric_compiler=None,
        semantic_repo=None,
        conversation_service=None,
    ) -> None:
        self._retriever = retriever
        self._reranker = reranker
        self._grounding_agent = grounding_agent
        self._generation_agent = generation_agent
        self._critic_agent = critic_agent
        self._explainer_agent = explainer_agent
        self._ast_classifier = ast_classifier
        self._scope_guard = scope_guard
        self._table_resolver = table_resolver
        self._executor = executor
        self._query_repo = query_repo
        self._settings = settings
        self._result_uploader = result_uploader
        self._auto_learner = auto_learner
        self._table_repo = table_repository
        self._metric_compiler = metric_compiler
        self._semantic_repo = semantic_repo
        self._conversation_service = conversation_service

    async def answer(
        self,
        *,
        tenant_id: str,
        workspace_id: uuid.UUID,
        dataset_id: uuid.UUID,
        question: str,
        scopes: set[str],
        dataset_allowlist: set[str] | None = None,
        conversation_id: uuid.UUID | None = None,
    ) -> AnswerResult:
        """Run the full NL → SQL → result pipeline.

        :param tenant_id: tenant identifier
        :param workspace_id: workspace UUID
        :param dataset_id: dataset to query
        :param question: natural-language question
        :param scopes: caller's token scopes (used by ScopeGuard)
        :param dataset_allowlist: optional set of allowed dataset IDs (None = unrestricted)
        :param conversation_id: optional conversation for drill-down context (Phase E)
        :return: :class:`AnswerResult`
        """
        start_ms = time.monotonic_ns() // 1_000_000

        if not scopes.intersection({"flyquery.query:read", "flyquery.sql:execute", "*"}) or (
            dataset_allowlist is not None and str(dataset_id) not in dataset_allowlist
        ):
            elapsed = (time.monotonic_ns() // 1_000_000) - start_ms
            # Retain caller-supplied denial evidence without attaching the
            # record to an unauthorized dataset or invoking retrieval/models.
            query_id = await self._query_repo.create_query(
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                dataset_id=None,
                question=question,
                semantic_path_taken=None,
                candidates_json=[],
                chosen_candidate_index=None,
                executed_sql=None,
                ast_classification=None,
                execution_status="REJECTED_BY_FIREWALL",
                retries=0,
                row_count=None,
                elapsed_ms=elapsed,
                clarification_emitted=False,
                clarification_json=None,
                pii_findings_json=None,
                error_json={"code": "SCOPE_ADMISSION_DENIED", "requested_dataset_id": str(dataset_id)},
            )
            return AnswerResult(
                query_id=query_id,
                sql=None,
                execution_status="REJECTED_BY_FIREWALL",
                preview=None,
                row_count=None,
                truncated=False,
                elapsed_ms=elapsed,
                chart_hint=None,
                explanation=None,
                clarification=None,
                grounded_summary=None,
            )

        # ------------------------------------------------------------------
        # 1. Hybrid retrieval
        # ------------------------------------------------------------------
        bundle = await self._retriever.retrieve(
            question,
            dataset_id=dataset_id,
            workspace_id=workspace_id,
            top_k_schema=self._settings.top_k_schema * 3,
            top_k_examples=self._settings.top_k_examples,
            top_k_metrics=self._settings.top_k_metrics,
        )

        # ------------------------------------------------------------------
        # 2. Rerank top-30 schema hits → top-K
        # ------------------------------------------------------------------
        schema_hits = bundle.get("schema_objects", [])
        top_k = self._settings.top_k_schema
        await provenance.before_model(
            "rerank",
            question + "\n" + "\n".join(h.text for h in schema_hits),
            bundle,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            dataset_id=dataset_id,
        )
        reranked = await self._reranker.rerank(question, schema_hits, top_n=top_k)
        bundle["schema_objects"] = reranked

        # ------------------------------------------------------------------
        # 2b. Load drill-down context from prior turn (Phase E)
        # ------------------------------------------------------------------
        starting_point_sql: str | None = None
        prior_table_qnames: list[str] = []
        prior_snapshot_pins: dict[str, str] = {}

        if conversation_id is not None and self._conversation_service is not None:
            prior_turn = await self._conversation_service.last_turn(conversation_id)
            if prior_turn is not None:
                starting_point_sql = prior_turn.get("executed_sql")
                prior_table_qnames = prior_turn.get("table_qnames_json") or []
                prior_snapshot_pins = prior_turn.get("snapshot_pins_json") or {}

        bundle["starting_point_sql"] = starting_point_sql
        bundle["prior_table_qnames"] = prior_table_qnames
        bundle["snapshot_pins"] = dict(prior_snapshot_pins)

        # ------------------------------------------------------------------
        # 3. Grounding — pydantic-ai's Agent.run expects a STRING prompt,
        # so we render the retrieval bundle into a markdown-ish doc that
        # Claude can reason over.
        # ------------------------------------------------------------------
        grounding_prompt = _render_grounding_prompt(
            question=question,
            bundle=bundle,
            starting_point_sql=starting_point_sql,
        )
        await provenance.before_model(
            "grounding",
            grounding_prompt,
            bundle,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            dataset_id=dataset_id,
        )
        grounded_run = await self._grounding_agent.run(grounding_prompt)
        # pydantic-ai's AgentRunResult wraps the structured response on .output
        grounded = getattr(grounded_run, "output", grounded_run)

        # ------------------------------------------------------------------
        # 4. Value catalogue + entity / group resolution (G1/G3 + round-2 #1/#2)
        # ------------------------------------------------------------------
        col_catalog = bundle.get("column_catalog") or []
        resolution = await self._resolve_entities(dataset_id, question, col_catalog, bundle)
        resolved_entities = resolution["entities"]
        resolved_groups = resolution["groups"]
        hierarchy_intent = resolution["hierarchy_intent"]

        # ------------------------------------------------------------------
        # 5. SQL generation (semantic-layer fast path OR synthesis)
        # ------------------------------------------------------------------
        chosen_sql: str
        candidates_json: list = []
        candidate_sqls: list[str] = []

        if grounded.path == "SEMANTIC_LAYER" and grounded.metrics:
            metric_name = grounded.metrics[0].metric_name
            compiled, metric_version = await self._compiled_metric_sql(
                metric_name, dataset_id, tenant_id=tenant_id, workspace_id=workspace_id
            )
            if compiled:
                candidate_sqls = [compiled]
                candidates_json = [
                    {
                        "sql": compiled,
                        "reasoning": "semantic-layer compiled",
                        "confidence": 1.0,
                        "metric_name": metric_name,
                        "metric_version": metric_version,
                    }
                ]
        if not candidate_sqls:
            gen_prompt = _render_generation_prompt(
                question,
                grounded,
                starting_point_sql,
                schema_inventory=bundle.get("schema_inventory"),
                col_catalog=col_catalog,
                resolved_entities=resolved_entities,
                resolved_groups=resolved_groups,
                hierarchy_intent=hierarchy_intent,
                examples=bundle.get("examples"),
                n_candidates=self._settings.generation_candidates,
                max_columns=self._settings.value_catalog_max_columns,
                char_budget=self._settings.value_catalog_char_budget,
            )
            await provenance.before_model(
                "generation",
                gen_prompt,
                bundle,
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                dataset_id=dataset_id,
            )
            gen_run = await self._generation_agent.run(gen_prompt)
            gen_out = getattr(gen_run, "output", gen_run)
            candidates_json = [c.model_dump() for c in gen_out.candidates]
            candidate_sqls = [c.sql for c in gen_out.candidates if getattr(c, "sql", None)]
        if not candidate_sqls:
            candidate_sqls = [""]
        candidate_sqls = [bind_registered_table_names(sql, bundle) for sql in candidate_sqls]

        # ------------------------------------------------------------------
        # 6. Candidate selection by EXECUTION (G5): drop degenerate, prefer a
        #    candidate that runs AND returns rows. Each candidate passes the
        #    scope guard + synthesis function firewall (G8) + table guard (G6).
        # ------------------------------------------------------------------
        ordered = [s for s in candidate_sqls if not value_anchoring.is_degenerate_sql(s)] or candidate_sqls
        select_pool = ordered if self._settings.candidate_exec_selection else ordered[:1]

        best: tuple[str, Any, Any] | None = None
        scope_reject: ScopeGuardError | None = None
        firewall_reject: str | None = None
        for cand in select_pool:
            run = await self._run_sql_once(cand, dataset_id, scopes, dataset_allowlist, bundle)
            if run["status"] == "scope":
                scope_reject = run["error"]
                continue
            if run["status"] == "firewall":
                firewall_reject = run["error"]
                continue
            if best is None:
                best = (cand, run["result"], run["ast"])
            res = run["result"]
            if (
                isinstance(res, ExecutionResult)
                and res.row_count > 0
                and not value_anchoring.is_degenerate_sql(cand)
            ):
                best = (cand, res, run["ast"])
                break

        if best is None:
            # Nothing executed. If the only blockers were scope/firewall, reject.
            if scope_reject is not None or firewall_reject is not None:
                reason = str(scope_reject) if scope_reject is not None else (firewall_reject or "")
                chosen_sql = ordered[0]
                ast = self._ast_classifier.classify(chosen_sql)
                elapsed = (time.monotonic_ns() // 1_000_000) - start_ms
                query_id = await self._query_repo.create_query(
                    tenant_id=tenant_id,
                    workspace_id=workspace_id,
                    dataset_id=dataset_id,
                    question=question,
                    semantic_path_taken=grounded.path,
                    candidates_json=candidates_json,
                    chosen_candidate_index=0,
                    executed_sql=chosen_sql,
                    ast_classification=ast.classification,
                    execution_status="REJECTED_BY_FIREWALL",
                    retries=0,
                    row_count=None,
                    elapsed_ms=elapsed,
                    clarification_emitted=False,
                    clarification_json=None,
                    pii_findings_json=None,
                    error_json={"firewall_error": reason},
                )
                return AnswerResult(
                    query_id=query_id,
                    sql=chosen_sql,
                    execution_status="REJECTED_BY_FIREWALL",
                    preview=None,
                    row_count=None,
                    truncated=False,
                    elapsed_ms=elapsed,
                    chart_hint=None,
                    explanation=None,
                    clarification=self._clarification(grounded),
                    grounded_summary=self._grounded_summary(grounded),
                )
            chosen_sql = ordered[0]
            best = (
                chosen_sql,
                ExecutionError(message="generation produced no usable SQL"),
                self._ast_classifier.classify(chosen_sql),
            )

        chosen_sql, result, ast = best
        chosen_index = candidate_sqls.index(chosen_sql) if chosen_sql in candidate_sqls else 0
        retries = 0

        def _is_good(r, s) -> bool:
            return (
                isinstance(r, ExecutionResult)
                and r.row_count > 0
                and not value_anchoring.is_degenerate_sql(s)
            )

        # Retain an executed, nonempty result if a repair fails. Row count is
        # an execution check; it does not establish semantic correctness.
        best_ok = (chosen_sql, result, ast) if _is_good(result, chosen_sql) else None

        # round-2 #5B/#7: when the result is already OK, an advisory check may still
        # ask the critic to reconsider (signed-measure double-subtraction; an IN-list
        # that under-covers a value group). It rides the non-destructive loop below,
        # and preserves the previous executed result when a proposal fails.
        adv_msg = None
        if _is_good(result, chosen_sql):
            adv_msg = await self._advisory_repair(chosen_sql, ast, col_catalog, question, dataset_id, bundle)

        # ------------------------------------------------------------------
        # 7. Repair loop: HARD repair (error / degenerate / 0-row-with-filter) OR an
        #    ADVISORY reconsideration. The critic receives the REAL stored values of
        #    the filtered columns so it replaces wrong literals/columns/signs instead
        #    of guessing again, and MAY keep the original SQL if it is already correct.
        # ------------------------------------------------------------------
        while (
            self._needs_repair(result, chosen_sql) or adv_msg
        ) and retries < self._settings.max_refine_retries:
            if self._needs_repair(result, chosen_sql):
                critic_msg = self._repair_message(result, chosen_sql, ast, col_catalog)
            else:
                critic_msg = adv_msg or ""
            value_hints = self._build_value_hints(chosen_sql, col_catalog, ast)
            critic_prompt = _render_critic_prompt(
                question=question,
                failing_sql=chosen_sql,
                error_message=critic_msg,
                grounded=grounded,
                schema_inventory=bundle.get("schema_inventory"),
                value_hints=value_hints,
            )
            await provenance.before_model(
                "critic",
                critic_prompt,
                bundle,
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                dataset_id=dataset_id,
            )
            refined_run = await self._critic_agent.run(critic_prompt)
            refined = getattr(refined_run, "output", refined_run)
            new_sql = getattr(refined, "sql", None) or chosen_sql
            new_sql = bind_registered_table_names(new_sql, bundle)
            if new_sql.strip() == chosen_sql.strip():
                break  # critic kept the SQL -> accept it as already correct
            if value_anchoring.is_degenerate_sql(new_sql):
                break  # never adopt a placeholder; best_ok (if any) is restored below
            run = await self._run_sql_once(
                new_sql, dataset_id, scopes, dataset_allowlist, bundle, _evidence_stage="critic"
            )
            if run["status"] in ("scope", "firewall"):
                break
            chosen_sql = new_sql
            result = run["result"]
            ast = run["ast"]
            retries += 1
            if _is_good(result, chosen_sql):
                best_ok = (chosen_sql, result, ast)
                adv_msg = await self._advisory_repair(
                    chosen_sql, ast, col_catalog, question, dataset_id, bundle
                )
            else:
                adv_msg = None

        # Restore the executed fallback when repair produces no usable result.
        terminal_timeout = isinstance(result, ExecutionError) and result.sql_state == "57014"
        if best_ok is not None and not _is_good(result, chosen_sql) and not terminal_timeout:
            chosen_sql, result, ast = best_ok

        # ------------------------------------------------------------------
        # 8. Determine execution status
        # ------------------------------------------------------------------
        if isinstance(result, ExecutionResult) and retries == 0:
            execution_status: str = "OK"
        elif isinstance(result, ExecutionResult):
            execution_status = "REFINED_OK"
        else:
            execution_status = "FAILED"

        # ------------------------------------------------------------------
        # 8. Explain
        # ------------------------------------------------------------------
        explanation_obj = None
        if isinstance(result, ExecutionResult):
            explainer_prompt = _render_explainer_prompt(
                question=question,
                executed_sql=chosen_sql,
                row_count=result.row_count,
                preview_rows=result.rows[:50],
            )
            await provenance.before_model(
                "explainer",
                explainer_prompt,
                bundle,
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                dataset_id=dataset_id,
                execution={"sql": chosen_sql, "result": result},
            )
            explanation_run = await self._explainer_agent.run(explainer_prompt)
            explanation_obj = getattr(explanation_run, "output", explanation_run)

        # ------------------------------------------------------------------
        # 9. Clarification frame (low confidence, OR confident-but-still-empty)
        # ------------------------------------------------------------------
        final_row_count = result.row_count if isinstance(result, ExecutionResult) else None
        clarification = self._clarification(grounded, row_count=final_row_count)
        clarification_emitted = clarification is not None

        # ------------------------------------------------------------------
        # 10. Persist query row
        # ------------------------------------------------------------------
        elapsed = (time.monotonic_ns() // 1_000_000) - start_ms
        error_json: dict | None = None
        if isinstance(result, ExecutionError):
            error_json = {"message": result.message}
            if result.sql_state is not None:
                error_json["sql_state"] = result.sql_state

        query_id = await self._query_repo.create_query(
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            dataset_id=dataset_id,
            question=question,
            semantic_path_taken=grounded.path,
            candidates_json=candidates_json,
            chosen_candidate_index=chosen_index,
            executed_sql=chosen_sql,
            ast_classification=ast.classification,
            execution_status=execution_status,
            retries=retries,
            row_count=result.row_count if isinstance(result, ExecutionResult) else None,
            elapsed_ms=elapsed,
            clarification_emitted=clarification_emitted,
            clarification_json=clarification.model_dump() if clarification else None,
            pii_findings_json=None,  # PII scanning in result is Phase F
            error_json=error_json,
            model_grounding=model_reference("structured.grounding", self._settings.grounding_model),
            model_generation=model_reference("structured.generation", self._settings.generation_model),
            model_critic=model_reference("structured.critic", self._settings.critic_model)
            if retries > 0
            else None,
            model_explainer=model_reference("structured.explainer", self._settings.explainer_model)
            if explanation_obj
            else None,
        )

        # ------------------------------------------------------------------
        # 11. Upload result
        # ------------------------------------------------------------------
        if isinstance(result, ExecutionResult):
            await self._result_uploader.upload(
                query_id=query_id,
                result=result,
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                dataset_id=dataset_id,
            )

        # ------------------------------------------------------------------
        # 12. Auto-learn (only on first-shot OK + no PII + no clarification)
        # ------------------------------------------------------------------
        if (
            autolearn_allowed(self._settings, scopes)
            and execution_status == "OK"
            and isinstance(result, ExecutionResult)
            and not clarification_emitted
        ):
            await self._auto_learner.maybe_propose(
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                dataset_id=dataset_id,
                question=question,
                generated_sql=chosen_sql,
                retries=retries,
                pii_findings=[],
                query_id=query_id,
                row_count=result.row_count,
                authorized=True,
            )

        # ------------------------------------------------------------------
        # 13. Persist conversation turn (Phase E drill-down)
        # ------------------------------------------------------------------
        execution_snapshot_pins = {
            name: bundle["snapshot_pins"][name] for name in ast.table_refs if name in bundle["snapshot_pins"]
        }
        if (
            conversation_id is not None
            and self._conversation_service is not None
            and execution_status in ("OK", "REFINED_OK")
        ):
            await self._conversation_service.append_turn(
                conversation_id=conversation_id,
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                question=question,
                executed_sql=chosen_sql,
                summary=explanation_obj.summary if explanation_obj else None,
                table_qnames_json=list(ast.table_refs),
                snapshot_pins_json=execution_snapshot_pins,
                elapsed_ms=elapsed,
            )

        return AnswerResult(
            query_id=query_id,
            sql=chosen_sql,
            execution_status=execution_status,  # type: ignore[arg-type]
            preview=result.rows[:10] if isinstance(result, ExecutionResult) else None,
            row_count=result.row_count if isinstance(result, ExecutionResult) else None,
            truncated=result.truncated if isinstance(result, ExecutionResult) else False,
            elapsed_ms=elapsed,
            chart_hint=explanation_obj.chart_hint if explanation_obj else None,
            explanation=explanation_obj.summary if explanation_obj else None,
            clarification=clarification,
            grounded_summary=self._grounded_summary(grounded),
            snapshot_pins=execution_snapshot_pins,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _table_kinds_by_name(
        self,
        table_names: list[str],
        dataset_id: uuid.UUID,
    ) -> dict[str, str]:
        """Read active table kinds through the native repository."""
        rows = await self._table_repo.list_kinds_for_dataset_by_names(dataset_id, table_names)
        return {row["name"]: row["kind"] for row in rows}

    async def _dataset_of_tables(
        self,
        table_names: list[str],
        dataset_id: uuid.UUID,
    ) -> dict[str, str]:
        """Return {name: dataset_id_str} — all resolved tables share the same dataset."""
        return {name: str(dataset_id) for name in table_names}

    async def _compiled_metric_sql(
        self,
        metric_name: str,
        dataset_id: uuid.UUID,
        *,
        tenant_id: str,
        workspace_id: uuid.UUID,
    ) -> tuple[str | None, int | None]:
        """Fetch + bind the compiled SQL for a PUBLISHED metric.

        Returns ``(bound_sql, current_version)`` so the version can be pinned
        in the query record, or ``(None, None)`` when no usable metric is found.
        """
        if self._semantic_repo is None:
            return None, None
        try:
            row = await self._semantic_repo.get_by_name(
                metric_name, dataset_id, tenant_id=tenant_id, workspace_id=workspace_id
            )
        except (AttributeError, KeyError, TypeError) as exc:  # pragma: no cover - defensive
            logger.warning("semantic metric lookup failed for %r: %s", metric_name, exc)
            return None, None
        if not row or not row.get("compiled_sql_template"):
            return None, None
        bound = SemanticCompiler.bind(row["compiled_sql_template"])
        return bound, row.get("current_version")

    def _clarification(self, grounded, *, row_count: int | None = None) -> Any:
        """Build a ClarificationFrame if grounding confidence is low or the
        (confident) query still returned 0 rows (G7 -- couple clarification to
        the observed empty result instead of confidence alone)."""
        from flyquery.interfaces.query import ClarificationFrame

        if grounded.confidence < self._settings.grounding_min_confidence and grounded.missing_info:
            return ClarificationFrame(questions=grounded.missing_info, reasons=[])
        if row_count == 0:
            return ClarificationFrame(
                questions=[
                    "The query executed but matched 0 rows -- a filter value, period, "
                    "or entity may not match how it is stored in the data. Please confirm "
                    "the exact value you mean."
                ],
                reasons=[],
            )
        return None

    def _grounded_summary(self, grounded) -> dict:
        """Convert GroundedContext to a summary dict for the response."""
        return {
            "path": grounded.path,
            "confidence": grounded.confidence,
            "table_count": len(grounded.tables),
            "missing_info": grounded.missing_info,
        }

    # ------------------------------------------------------------------
    # Value-anchoring / repair helpers (G2/G3/G5/G6/G8)
    # ------------------------------------------------------------------

    @provenance.candidate
    async def _run_sql_once(
        self,
        sql: str,
        dataset_id: uuid.UUID,
        scopes: set[str],
        dataset_allowlist: set[str] | None,
        bundle: dict,
        *,
        _evidence_stage: str = "candidate",
    ) -> dict:
        """Classify, guard, and execute one candidate SQL.

        Returns ``{status, result, ast, error}`` where status is one of
        ``ok`` / ``empty`` / ``error`` / ``scope`` / ``firewall``.
        """
        ast = self._ast_classifier.classify(sql)

        # G8: block filesystem/exfiltration table-functions on the synthesis path.
        if self._settings.synthesis_function_firewall:
            dangerous = value_anchoring.find_dangerous_functions(sql)
            if dangerous:
                return {
                    "status": "firewall",
                    "result": None,
                    "ast": ast,
                    "error": f"disallowed function(s) in generated SQL: {sorted(dangerous)}",
                }

        table_kinds = await self._table_kinds_by_name(list(ast.table_refs), dataset_id)
        dataset_of_table = await self._dataset_of_tables(list(ast.table_refs), dataset_id)
        try:
            self._scope_guard.check(
                classification=ast,
                scopes=scopes,
                table_kinds_by_name=table_kinds,
                dataset_allowlist=dataset_allowlist,
                dataset_of_table=dataset_of_table,
            )
        except ScopeGuardError as exc:
            return {"status": "scope", "result": None, "ast": ast, "error": exc}

        # G6: CTE-aware unknown-table guard. CTE / derived-table aliases are NOT
        # real tables, so subtract them before the set-difference -- otherwise a
        # valid `WITH x AS (...) SELECT ... FROM x` is wrongly rejected.
        synthetic = {n.lower() for n in value_anchoring.cte_and_derived_names(sql)}
        ref_set = {t for t in ast.table_refs if t and t.lower() not in synthetic}
        bad_tables = sorted(ref_set - set(table_kinds.keys()))
        if bad_tables:
            real_tables = sorted(table_kinds.keys()) + [
                (getattr(h, "metadata", {}) or {}).get("qualified_name", "").rsplit(".", 1)[-1]
                for h in (bundle.get("schema_inventory") or [])
                if (getattr(h, "metadata", {}) or {}).get("kind") == "TABLE"
            ]
            real_tables = [t for t in dict.fromkeys(real_tables) if t]
            return {
                "status": "error",
                "result": ExecutionError(
                    message=(
                        f"Table(s) {bad_tables!r} do not exist in this dataset. "
                        f"Use ONLY these tables: {real_tables[:80]!r}."
                    )
                ),
                "ast": ast,
                "error": None,
            }

        attached = await self._resolve_attached_tables(dataset_id, list(ast.table_refs), bundle)
        result = await self._executor.execute(sql, attached)
        if isinstance(result, ExecutionResult):
            status = "ok" if result.row_count > 0 else "empty"
        else:
            status = "error"
        return {"status": status, "result": result, "ast": ast, "error": None}

    async def _resolve_attached_tables(self, dataset_id, table_names: list[str], bundle: dict) -> dict:
        pins = bundle.setdefault("snapshot_pins", {})
        unpinned = [name for name in table_names if name not in pins]
        if unpinned:
            pins.update(await self._table_resolver.current_snapshots(dataset_id, unpinned))
        # Resolve using captured IDs so re-ingestion cannot change the data
        # between candidate selection, repair, and a later conversation turn.
        return await self._table_resolver.resolve(
            dataset_id, table_names, pins={name: pins[name] for name in table_names if name in pins}
        )

    def _needs_repair(self, result, sql: str) -> bool:
        """A query needs repair if it errored, is degenerate, or ran to 0 rows
        while filtering on equality/IN literals (G2/G5)."""
        if isinstance(result, ExecutionError):
            return result.sql_state != "57014"
        if value_anchoring.is_degenerate_sql(sql):
            return True
        return bool(
            self._settings.zero_row_repair_enabled
            and isinstance(result, ExecutionResult)
            and result.row_count == 0
            and value_anchoring.equality_predicate_columns(sql)
        )

    def _repair_message(self, result, sql: str, ast, col_catalog: list[dict]) -> str:
        unknown = self._unknown_columns(ast, col_catalog, sql)
        suffix = ""
        if unknown:
            names = sorted({c.get("qualified_name", "").rsplit(".", 1)[-1] for c in col_catalog})
            suffix = (
                f" Also: column(s) {unknown!r} are not real columns -- use only these "
                f"columns: {names[:80]!r}."
            )
        if isinstance(result, ExecutionError):
            return result.message + suffix
        if value_anchoring.is_degenerate_sql(sql):
            return (
                "The previous SQL is a no-op (constant/placeholder, e.g. WHERE 1=0 or "
                "SUM(CASE..THEN 0 ELSE 0)). Rewrite it to actually compute the answer "
                "using real columns and literal values from the catalogue below." + suffix
            )
        return (
            "The previous SQL executed but returned 0 ROWS. One or more filter literals "
            "or filtered columns is wrong. Replace each WHERE/IN literal with a value that "
            "actually appears in that column (see the value catalogue). If the entity belongs "
            "to a different column, filter THAT column instead." + suffix
        )

    def _build_value_hints(self, sql: str, col_catalog: list[dict], ast) -> list[str]:
        """Render value-catalogue lines for the columns the failing SQL touched."""
        wanted: set[str] = {c.lower() for c in value_anchoring.equality_predicate_columns(sql)}
        wanted |= {c.lower() for c in (getattr(ast, "column_refs", ()) or ())}
        hints: list[str] = []
        seen: set[str] = set()
        for c in col_catalog:
            tail = c["qualified_name"].rsplit(".", 1)[-1].lower()
            if tail in wanted and tail not in seen:
                seen.add(tail)
                hints.append(value_anchoring.render_catalog_from_meta(c["qualified_name"], c))
        return hints[:40]

    def _unknown_columns(self, ast, col_catalog: list[dict], sql: str) -> list[str]:
        if not col_catalog:
            return []
        known = {c["qualified_name"].rsplit(".", 1)[-1].lower() for c in col_catalog}
        aliases = value_anchoring.select_aliases(sql)
        out: list[str] = []
        for c in getattr(ast, "column_refs", ()) or ():
            cl = c.lower()
            if cl not in known and cl not in aliases and cl != "*":
                out.append(c)
        return out[:20]

    async def _advisory_repair(self, sql, ast, col_catalog, question, dataset_id, bundle) -> str | None:
        """Non-error reasons to ask the critic to reconsider an already-OK result.

        Rides the non-destructive loop (round-2 #4): under-covered value groups (#7)
        and signed-measure double-subtraction (#5B). Returns a combined message or None.
        """
        reasons: list[str] = []
        if self._settings.group_coverage_repair_enabled:
            lits = value_anchoring.extract_question_literals(question)
            for g in value_anchoring.group_coverage_gaps(sql, col_catalog, lits):
                col = g["column"].rsplit(".", 1)[-1]
                reasons.append(
                    f"The filter on `{col}` lists only SOME of the values the question's group "
                    f"covers; it is MISSING {g['missing']!r}. Include ALL of them (IN-list) or use "
                    f"an anchored LIKE; keep the original only if the exclusion is genuinely intended."
                )
        if self._settings.signed_measure_repair_enabled:
            hint = await self._signed_measure_hint(sql, ast, col_catalog, dataset_id, bundle)
            if hint:
                reasons.append(hint)
        return " ".join(reasons) if reasons else None

    async def _signed_measure_hint(self, sql, ast, col_catalog, dataset_id, bundle) -> str | None:
        """Probe whether the SQL subtracts a term whose SIGNED measure is already
        stored negative (so subtracting double-counts the sign). Best-effort (#5B)."""
        try:
            tables = [t for t in ast.table_refs if t]
            eligible = _eligible_value_columns(col_catalog, tables)
            mixed = {
                c["qualified_name"].rsplit(".", 1)[-1].lower()
                for c in col_catalog
                if _allows_value_access(c)
                and c.get("mixed_sign")
                and value_anchoring.semantic_role(c.get("semantic_type")) == "measure"
            }
            if not mixed:
                return None
            terms = value_anchoring.signed_subtraction_terms(sql)
            subtracted = [
                t
                for t in terms
                if t["sign"] < 0 and t["measure_col"].lower() in mixed and t["dim_col"] and t["literals"]
            ]
            if not subtracted:
                return None
            eligible = {
                table: columns
                for table, columns in eligible.items()
                if any(
                    term["measure_col"].lower() in columns and term["dim_col"].lower() in columns
                    for term in subtracted
                )
            }
            if not eligible:
                return None
            attached = await self._resolve_attached_tables(dataset_id, list(eligible), bundle)
            if not attached:
                return None
            offenders = await self._probe_signed_terms(attached, subtracted, eligible)
            if not offenders:
                return None
            parts = "; ".join(f"{o['dim']} IN {o['literals']} sums to {o['sum']:.0f}" for o in offenders[:6])
            # build the corrected single-signed-sum pattern from ALL the formula's
            # terms (the generic fix: the data already carries the sign).
            all_terms = [
                t for t in terms if t["measure_col"].lower() in mixed and t["dim_col"] and t["literals"]
            ]
            allowed = sorted({lit for t in all_terms for lit in t["literals"]})
            dim = all_terms[0]["dim_col"]
            meas = all_terms[0]["measure_col"]
            lits_sql = ", ".join("'" + lit.replace("'", "''") + "'" for lit in allowed)
            return (
                f"SIGN ERROR (must fix): this formula SUBTRACTS terms whose measure is ALREADY STORED "
                f"NEGATIVE ({parts}). Subtracting an already-negative value double-counts the sign and "
                f"inflates the result above total revenue. The data already carries the economic sign, so "
                f"REWRITE the whole +/- expression as ONE signed sum over all its line-items: "
                f'SUM(CASE WHEN "{dim}" IN ({lits_sql}) THEN "{meas}" ELSE 0 END) -- keep the original '
                f"WHERE filters and any GROUP BY. Do NOT keep the subtraction chain."
            )
        except Exception as exc:  # noqa: BLE001 - best-effort
            logger.debug("signed-measure probe failed: %s", exc)
            return None

    async def _probe_signed_terms(
        self, attached: dict[str, str], terms: list[dict], eligible: dict
    ) -> list[dict]:
        offenders: list[dict] = []
        for term in terms[:6]:
            # A partial literal set can reverse the sign and produce a false repair.
            if not term["literals"] or len(term["literals"]) > 25:
                continue
            total = None
            for table, path in attached.items():
                columns = eligible.get(table, {})
                measure = columns.get(term["measure_col"].lower())
                dimension = columns.get(term["dim_col"].lower())
                if measure is None or dimension is None:
                    continue
                in_list = ", ".join(_sql_literal(str(lit)) for lit in term["literals"])
                sql = (
                    f"SELECT SUM(TRY_CAST({_sql_identifier(measure['column'])} AS DOUBLE)) AS total "
                    f"FROM {_sql_identifier(table)} "
                    f"WHERE CAST({_sql_identifier(dimension['column'])} AS VARCHAR) IN ({in_list})"
                )
                result = await self._executor.execute(sql, {table: path})
                if isinstance(result, ExecutionResult) and result.rows:
                    value = result.rows[0].get("total")
                    if value is not None:
                        total = (total or 0.0) + float(value)
            if total is not None and total < 0:
                offenders.append({"dim": term["dim_col"], "literals": term["literals"], "sum": total})
        return offenders

    async def _resolve_entities(
        self,
        dataset_id: uuid.UUID,
        question: str,
        col_catalog: list[dict],
        bundle: dict,
    ) -> dict:
        """Map question literals to the columns that actually store them (G3).

        First via the low-cardinality value catalogue (cheap), then -- for
        unresolved entity-looking literals (e.g. person names in a high-card
        column) -- via a bounded live DuckDB scan of the dataset's tables.
        """
        empty = {"entities": [], "groups": [], "hierarchy_intent": False}
        if not self._settings.entity_resolution_enabled:
            return empty
        literals = value_anchoring.extract_question_literals(question)
        if not literals:
            return empty

        col_catalog = [column for column in col_catalog if _allows_value_access(column)]
        hierarchy = value_anchoring.relationship_intent(question)
        # round-2 #1: a term that umbrellas >=2 values of one column -> a group.
        groups: list[dict] = []
        if self._settings.group_resolution_enabled:
            groups = value_anchoring.resolve_value_groups(literals, col_catalog)
        group_keys = {(g["literal"].lower(), g["column"]) for g in groups}
        group_lits = {g["literal"].lower() for g in groups}

        resolved = value_anchoring.resolve_from_catalog(literals, col_catalog)
        # a single value superseded by a group is dropped (the group is the truth)
        resolved = [r for r in resolved if (r["literal"].lower(), r["column"]) not in group_keys]
        done = {r["literal"].lower() for r in resolved} | group_lits
        remaining = [lit for lit in literals if lit.lower() not in done][
            : self._settings.entity_resolution_max_literals
        ]
        if remaining:
            try:
                resolved += await self._scan_columns_for_values(dataset_id, remaining, bundle)
            except Exception as exc:  # noqa: BLE001 - resolution is best-effort
                logger.warning("live entity resolution failed: %s", exc)

        # de-dup entities by (literal, column), keeping the highest match_count
        merged: dict[tuple[str, str], dict] = {}
        for r in resolved:
            key = (r["literal"].lower(), r["column"])
            cur = merged.get(key)
            if cur is None or (r.get("match_count") or 0) > (cur.get("match_count") or 0):
                merged[key] = r
        # de-dup groups by (literal, column)
        gseen: set[tuple[str, str]] = set()
        gout: list[dict] = []
        for g in groups:
            k = (g["literal"].lower(), g["column"])
            if k not in gseen:
                gseen.add(k)
                gout.append(g)
        entities = sorted(merged.values(), key=lambda r: r.get("match_count") or 0, reverse=True)[:25]
        return {"entities": entities, "groups": gout[:12], "hierarchy_intent": hierarchy}

    async def _scan_columns_for_values(
        self,
        dataset_id: uuid.UUID,
        literals: list[str],
        bundle: dict,
    ) -> list[dict]:
        table_names = [
            (getattr(h, "metadata", {}) or {}).get("qualified_name", "").rsplit(".", 1)[-1]
            for h in (bundle.get("schema_inventory") or [])
            if (getattr(h, "metadata", {}) or {}).get("kind") == "TABLE"
        ]
        table_names = [t for t in dict.fromkeys(table_names) if t]
        eligible = _eligible_value_columns(bundle.get("column_catalog") or [], table_names)
        eligible = {
            table: {
                name: column
                for name, column in columns.items()
                if str(column.get("data_type") or "")
                .upper()
                .startswith(("VARCHAR", "TEXT", "STRING", "CHAR"))
            }
            for table, columns in eligible.items()
        }
        eligible = {table: columns for table, columns in eligible.items() if columns}
        literals = list(dict.fromkeys(lit.lower() for lit in literals if lit))[
            : self._settings.entity_resolution_max_literals
        ]
        if not eligible or not literals:
            return []
        attached = await self._resolve_attached_tables(dataset_id, list(eligible), bundle)
        in_list = ", ".join(_sql_literal(lit) for lit in literals)
        found: list[dict] = []
        for table, path in attached.items():
            columns = list(eligible.get(table, {}).values())[:80]
            if not columns:
                continue
            expressions: list[str] = []
            for i, column in enumerate(columns):
                identifier = _sql_identifier(column["column"])
                predicate = f"lower(CAST({identifier} AS VARCHAR)) IN ({in_list})"
                expressions.append(
                    f"MAX(CASE WHEN {predicate} THEN CAST({identifier} AS VARCHAR) END) AS m{i}"
                )
                expressions.append(f"SUM(CASE WHEN {predicate} THEN 1 ELSE 0 END) AS c{i}")
            result = await self._executor.execute(
                f"SELECT {', '.join(expressions)} FROM {_sql_identifier(table)}", {table: path}
            )
            if not isinstance(result, ExecutionResult) or not result.rows:
                continue
            row = result.rows[0]
            for i, column in enumerate(columns):
                value = row.get(f"m{i}")
                if value is None:
                    continue
                found.append(
                    {
                        "literal": str(value),
                        "column": column["qualified_name"],
                        "value": value,
                        "match_count": int(row.get(f"c{i}") or 0),
                    }
                )
        return found


def _allows_value_access(column: dict) -> bool:
    samples = column.get("sample_values_json")
    return (
        column.get("value_access") is True
        and samples != []
        and (samples is None or isinstance(samples, list))
    )


def _eligible_value_columns(catalog: list[dict], tables: list[str]) -> dict[str, dict[str, dict]]:
    eligible: dict[str, dict[str, dict]] = {}
    blocked = {column.get("qualified_name") for column in catalog if not _allows_value_access(column)}
    for column in catalog:
        qualified = column.get("qualified_name")
        if not isinstance(qualified, str) or qualified in blocked or not _allows_value_access(column):
            continue
        parent, separator, name = qualified.rpartition(".")
        table = parent.rsplit(".", 1)[-1]
        if not separator or not name or table not in tables:
            continue
        eligible.setdefault(table, {})[name.lower()] = {**column, "column": name}
    return eligible


def _sql_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"
