# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""The native context owns agents; tools reauthorize canonical scope before every read."""

import asyncio
import json
import logging
from contextlib import asynccontextmanager, nullcontext, suppress
from pathlib import Path

from pydantic_ai import Tool as PydanticTool
from pydantic_ai.messages import ModelRequest, ModelResponse, SystemPromptPart, TextPart, UserPromptPart
from pydantic_ai.models import ModelRequestParameters
from pydantic_ai.usage import UsageLimits
from pyfly.agentic.factory import AgentFactory
from pyfly.agentic.memory import ConversationMemory
from pyfly.agentic.models import ModelFactory
from pyfly.agentic.prompts import PromptLoader
from pyfly.agentic.tools import agent_tool
from pyfly.container import service
from pyfly.container.container import Container
from pyfly.kernel import ConflictException, InvalidRequestException, ServiceUnavailableException
from pyfly.security.context import SecurityContext
from pyfly.security.context_holder import SecurityContextHolder

from koinon.assistants.attachment_input import prepare_attachment_input
from koinon.assistants.connections import (
    input_modalities,
    options_fingerprint,
    output_mode_for,
    provider_state,
)
from koinon.assistants.context_budget import ConservativeTokenEstimator, history_budget
from koinon.assistants.entities import ChatRun
from koinon.assistants.grounding import evidence_view, has_evidence, refusal_message
from koinon.assistants.lifecycle import timestamp
from koinon.assistants.model_bindings import BorrowedModel, bind_model
from koinon.assistants.private_citations import PrivateCitationLabels
from koinon.assistants.queue import AssistantQueue
from koinon.assistants.service import AssistantService
from koinon.assistants.tool_activity import tracked_tool
from koinon.catalog.errors import AccessDenied
from koinon.knowledge.attachments.ports import AttachmentRef
from koinon.knowledge.capture_dtos import CapturedEvidence
from koinon.knowledge.evidence_capture import NativeEvidenceFailure, NativeKnowledgeEvidence, failure_capture
from koinon.organization_knowledge.dtos import OrganizationKnowledgeSnapshot
from koinon.organization_knowledge.runtime import bind_snapshot, snapshot_for_run

logger = logging.getLogger(__name__)
_NATIVE_POLICY_REFUSALS = frozenset(
    {
        "RLM_DOCUMENT_VIEWS_REQUIRED",
        "KNOWLEDGE_RLM_UNQUALIFIED",
        "KNOWLEDGE_SETTINGS_SNAPSHOT_REQUIRED",
        "KNOWLEDGE_SETTINGS_SNAPSHOT_INVALID",
    }
)


@service(name="assistants.executor")
class AssistantExecutor:
    def __init__(
        self, assistants: AssistantService, queue: AssistantQueue, container: Container, models: ModelFactory
    ):
        self.assistants, self.queue, self.container, self.models = assistants, queue, container, models
        self.prompt = PromptLoader.from_file(Path(__file__).parent / "prompts" / "knowledge-guide.yaml")

    async def authority(self, run_id: str, worker_id: str):
        run = await self.assistants.runs.find_by_id(run_id)
        if (
            run is None
            or run.status != "running"
            or run.worker_id != worker_id
            or run.lease_until is None
            or run.lease_until <= timestamp()
        ):
            raise ConflictException("The answer is no longer running", code="RUN_LEASE_LOST")
        thread = await self.assistants.threads.find_by_id(run.thread_id)
        await self.assistants.owned_run(thread.subject, run.tenant_id, run.id)
        agent = await self.assistants.scoped(self.assistants.agents, run.tenant_id, run.agent_id)
        provider = await self.assistants.scoped(self.assistants.providers, run.tenant_id, agent.provider_id)
        if (
            not agent.enabled
            or not provider.enabled
            or agent.revision != run.agent_revision
            or provider.revision != run.provider_revision
        ):
            raise ConflictException(
                "Agent configuration changed. Start the answer again.", code="CONFIGURATION_CHANGED"
            )
        await self.assistants.validate_scope(thread.subject, run.tenant_id, run.scope, agent.scope)
        return run, thread, agent, provider

    def knowledge_evidence(self) -> NativeKnowledgeEvidence:
        if not self.container.contains_type(NativeKnowledgeEvidence):
            raise ServiceUnavailableException(
                "Enable the knowledge module before using this tool", code="KNOWLEDGE_CAPTURE_UNAVAILABLE"
            )
        return self.container.resolve(NativeKnowledgeEvidence)

    @staticmethod
    def policy_for_run(run: ChatRun) -> OrganizationKnowledgeSnapshot:
        snapshot = snapshot_for_run(run)
        if snapshot is None:
            raise ServiceUnavailableException(
                "This answer has no recorded knowledge settings. Start a new answer.",
                code="KNOWLEDGE_SETTINGS_SNAPSHOT_REQUIRED",
            )
        return snapshot

    async def tools(
        self,
        run_id: str,
        worker_id: str,
        enabled: list[str],
        observed: set[str] | None = None,
        grounded: set[str] | None = None,
        attachment_refs: tuple[AttachmentRef, ...] = (),
        private_search_enabled: bool = True,
    ):
        remaining = getattr(self.assistants.settings, "tool_result_tokens", 4096)
        native_capture_lock = asyncio.Lock()

        async def record_observation(kind, capture, assets):
            if capture.sources or capture.native_reads or capture.sql_attempts:
                observed_assets = list(
                    dict.fromkeys(
                        [
                            *assets,
                            *(row.asset_id for row in capture.sources),
                            *(row.entity_id for row in capture.native_reads),
                        ]
                    )
                )
                await self.queue.observation(run_id, worker_id, kind, observed_assets, capture=capture)

        @asynccontextmanager
        async def captured_call(kind, method, *args, assets=(), **kwargs):
            async with native_capture_lock:
                run, thread, _, _ = await self.authority(run_id, worker_id)
                snapshot = self.policy_for_run(run) if kind in {"search", "query"} else None
                limits = await self.queue.capture_limits(run_id, worker_id, kind)
                capture = None
                with bind_snapshot(snapshot, thread.subject) if snapshot is not None else nullcontext():
                    try:
                        capture = await method(*args, _limits=limits, **kwargs)
                        yield capture
                    except NativeEvidenceFailure as error:
                        await record_observation(kind, error.capture, assets)
                        raise
                    except asyncio.CancelledError as error:
                        receipt = failure_capture(error) or capture
                        if receipt is not None:
                            try:
                                async with asyncio.timeout(2):
                                    await record_observation(kind, receipt, assets)
                            except Exception:
                                logger.info("Cancelled native receipt could not be retained")
                        raise

        async def evidence(kind: str, capture: CapturedEvidence, assets: list[str]):
            data = capture.data
            nonlocal remaining
            if not capture.complete:
                await record_observation(kind, capture, assets)
                raise ServiceUnavailableException(
                    "Exact source provenance is required before using this evidence",
                    code="EVIDENCE_PROVENANCE_REQUIRED",
                )
            try:
                run, _, _, _ = await self.authority(run_id, worker_id)
            except AccessDenied:
                await record_observation(kind, capture, assets)
                raise
            try:
                result_id = await self.queue.evidence(run.id, worker_id, kind, data, assets, capture=capture)
            except InvalidRequestException as error:
                if error.code != "EVIDENCE_TOO_LARGE":
                    raise
                await record_observation(kind, capture, assets)
                raise ServiceUnavailableException(
                    "Narrow the question to fit the source audit budget", code="EVIDENCE_BUDGET_EXCEEDED"
                ) from error
            view = evidence_view(kind, data, result_id, remaining)
            remaining = max(
                0, remaining - ConservativeTokenEstimator().estimate(json.dumps(view, ensure_ascii=False))
            )
            if grounded is not None and has_evidence(kind, view):
                grounded.add(result_id)
            return view

        @agent_tool(
            name="search_knowledge",
            description="Search documents and published knowledge inside the conversation's allowed scope.",
            auto_register=False,
        )
        @tracked_tool(self.queue, self.authority, run_id, worker_id, "search_knowledge")
        async def search_knowledge(question: str) -> dict:
            run, thread, _, _ = await self.authority(run_id, worker_id)
            policy = self.policy_for_run(run)
            scope = dict(run.scope)
            if "asset_ids" in scope:
                documents = []
                for asset_id in scope["asset_ids"]:
                    entry = await self.assistants.catalog.get(thread.subject, run.tenant_id, asset_id)
                    if entry.kind in {"document", "knowledge_item"}:
                        documents.append(asset_id)
                scope["asset_ids"] = documents
            async with captured_call(
                "search",
                self.knowledge_evidence().search,
                thread.subject,
                run.tenant_id,
                question=question,
                **scope,
                limit=min(100, policy.documents.retrieval_top_k),
                answer=policy.documents.answer_mode == "rlm",
            ) as capture:
                assets = list(
                    dict.fromkeys(
                        [
                            *(hit["asset_id"] for hit in capture.data.get("hits", [])),
                            *(source.asset_id for source in capture.sources),
                        ]
                    )
                )
                view = await evidence("search", capture, assets)
                if observed is not None:
                    observed.add("search_knowledge")
                return view

        async def dataset_scope(dataset_id: str):
            run, thread, _, _ = await self.authority(run_id, worker_id)
            if "asset_ids" in run.scope and dataset_id not in run.scope["asset_ids"]:
                raise AccessDenied("This dataset is outside the conversation scope", code="SCOPE_DENIED")
            await self.assistants.validate_scope(
                thread.subject, run.tenant_id, {"asset_ids": [dataset_id]}, run.scope
            )
            entry = await self.assistants.catalog.get(thread.subject, run.tenant_id, dataset_id)
            if entry.kind != "dataset":
                raise AccessDenied("Choose a dataset in the current knowledge scope", code="SCOPE_DENIED")
            return run, thread

        @agent_tool(
            name="inspect_schema",
            description="Read a selected dataset's table and column definitions.",
            auto_register=False,
        )
        @tracked_tool(self.queue, self.authority, run_id, worker_id, "inspect_schema")
        async def inspect_schema(dataset_id: str) -> dict:
            run, thread = await dataset_scope(dataset_id)
            async with captured_call(
                "schema",
                self.knowledge_evidence().schema,
                thread.subject,
                run.tenant_id,
                dataset_id,
                assets=[dataset_id],
            ) as capture:
                view = await evidence("schema", capture, [dataset_id])
                if observed is not None:
                    observed.add("inspect_schema")
                return view

        @agent_tool(
            name="query_dataset",
            description="Ask a question about a selected dataset using its governed query pipeline.",
            auto_register=False,
        )
        @tracked_tool(self.queue, self.authority, run_id, worker_id, "query_dataset")
        async def query_dataset(dataset_id: str, question: str) -> dict:
            run, thread = await dataset_scope(dataset_id)
            await self.assistants.catalog.authorize(
                thread.subject,
                run.tenant_id,
                "query:execute",
                (await self.assistants.catalog.get(thread.subject, run.tenant_id, dataset_id)).workspace_id,
            )
            async with captured_call(
                "query",
                self.knowledge_evidence().query,
                thread.subject,
                run.tenant_id,
                dataset_id=dataset_id,
                question=question,
                assets=[dataset_id],
            ) as capture:
                view = await evidence("query", capture, [dataset_id])
                if observed is not None:
                    observed.add("query_dataset")
                return view

        @agent_tool(
            name="propose_catalog_update",
            description=(
                "Propose a selected document or dataset name/description for explicit user review. "
                "Never applies it."
            ),
            auto_register=False,
        )
        @tracked_tool(self.queue, self.authority, run_id, worker_id, "propose_catalog_update")
        async def propose_catalog_update(
            asset_id: str, name: str | None = None, description: str | None = None
        ) -> dict:
            from koinon.assistants.proposals import CatalogProposals

            await self.authority(run_id, worker_id)
            changes = {
                key: value
                for key, value in {"name": name, "description": description}.items()
                if value is not None
            }
            proposal = await self.container.resolve(CatalogProposals).propose(
                run_id, worker_id, asset_id, changes
            )
            if observed is not None:
                observed.add("propose_catalog_update")
            return {
                "evidence_id": proposal.id,
                "proposal": proposal.model_dump(mode="json"),
                "requires_user_confirmation": True,
            }

        @agent_tool(
            name="search_private_attachments",
            description="Search selected private files; excerpts are not complete files.",
            auto_register=False,
        )
        @tracked_tool(self.queue, self.authority, run_id, worker_id, "search_private_attachments")
        async def search_private_attachments(question: str) -> dict:
            nonlocal remaining
            run, thread, _, _ = await self.authority(run_id, worker_id)
            access = self.assistants._attachment_access()
            if access is None or not attachment_refs:
                raise AccessDenied(
                    "Select a private file for this answer", code="ATTACHMENT_SELECTION_REQUIRED"
                )

            async def fits(value: str) -> bool:
                return ConservativeTokenEstimator().estimate(value) + 512 <= remaining

            value = await prepare_attachment_input(
                access,
                subject=thread.subject,
                tenant_id=run.tenant_id,
                thread_id=thread.id,
                refs=tuple(ref for ref in attachment_refs if ref.kind != "image"),
                question=question,
                fits_text=fits,
                input_modalities=["text"],
            )
            await self.authority(run_id, worker_id)
            await access.authorize_evidence(thread.subject, run.tenant_id, thread.id, attachment_refs)
            result_id = await self.queue.evidence(run.id, worker_id, "attachment", value.evidence, [])
            view = {"evidence_id": result_id, "text": value.text, **value.evidence}
            cost = ConservativeTokenEstimator().estimate(json.dumps(view, ensure_ascii=False))
            if cost > remaining:
                raise InvalidRequestException(
                    "Narrow the private file question to fit the tool evidence budget",
                    code="ATTACHMENT_CONTEXT_BUDGET_EXCEEDED",
                )
            remaining -= cost
            if grounded is not None:
                grounded.add(result_id)
            if observed is not None:
                observed.add("search_private_attachments")
            return view

        available = {
            "search_knowledge": search_knowledge,
            "inspect_schema": inspect_schema,
            "query_dataset": query_dataset,
            "propose_catalog_update": propose_catalog_update,
        }
        selected = [] if attachment_refs else [available[name] for name in enabled if name in available]
        if private_search_enabled and any(ref.kind != "image" for ref in attachment_refs):
            selected.append(search_private_attachments)
        return selected

    async def history(
        self,
        run: ChatRun,
        *,
        token_budget: int | None = None,
        attachment_refs: tuple[AttachmentRef, ...] = (),
    ) -> list:
        budget = self.assistants.settings.max_history_tokens if token_budget is None else token_budget
        if budget <= 0:
            return []
        memory = ConversationMemory(max_tokens=budget, estimator=ConservativeTokenEstimator())
        thread = await self.assistants.threads.find_by_id(run.thread_id)
        previous = await self.assistants.runs.find_all(thread_id=run.thread_id, status="completed")
        eligible = sorted(
            (row for row in previous if row.scope == run.scope and row.created_at < run.created_at),
            key=lambda row: row.created_at,
        )
        access = self.assistants._attachment_access()
        for old in eligible[-max(1, self.assistants.settings.max_history_messages // 2) :]:
            if access is not None:
                try:
                    previous_refs = await access.for_run(thread.subject, run.tenant_id, run.thread_id, old.id)
                except (AccessDenied, InvalidRequestException, ConflictException):
                    continue
                if previous_refs != attachment_refs:
                    continue
            await self.assistants.authorize_results(thread.subject, run.tenant_id, old.id)
            user = await self.assistants.message_repository.find_by_id(old.user_message_id)
            answer = await self.assistants.message_repository.find_by_id(old.message_id)
            policy = getattr(answer, "answer_policy", {}) or {}
            if policy.get("outcome") in {"refused", "review_required"}:
                code = (
                    "REVIEW_REQUIRED"
                    if policy["outcome"] == "review_required"
                    else policy.get("code", "KNOWLEDGE_ONLY")
                )
                previous_text = refusal_message("en-US", code)
            else:
                previous_text = (
                    "Previous answer omitted. Retrieve the selected sources again before answering."
                )
            memory.add_turn(
                run.thread_id,
                user.text,
                previous_text,
                [
                    ModelRequest(parts=[UserPromptPart(user.text)]),
                    ModelResponse(parts=[TextPart(previous_text)]),
                ],
            )
        return memory.get_message_history(run.thread_id)

    async def suggest_title(self, run_id: str, worker_id: str, *, timeout: float) -> None:
        from koinon.assistants.history.service import ChatHistoryService
        from koinon.assistants.title_service import TitleService

        if timeout <= 0 or not all(
            self.container.contains_type(kind) for kind in (ChatHistoryService, TitleService)
        ):
            return
        try:
            async with asyncio.timeout(timeout):
                run, thread, agent, _ = await self.authority(run_id, worker_id)
                if thread.title_source != "default":
                    return
                proposed = await self.container.resolve(TitleService).propose(
                    thread.subject, run.tenant_id, thread.id, agent.id, expected_revision=thread.revision
                )
                await self.authority(run_id, worker_id)
                await self.container.resolve(ChatHistoryService).apply_generated_title(
                    thread.subject,
                    run.tenant_id,
                    thread.id,
                    proposed.title,
                    expected_revision=proposed.based_on_revision,
                )
        except Exception:
            logger.info("Optional conversation title was unavailable")

    async def generate(self, run_id: str, worker_id: str):
        started = asyncio.get_running_loop().time()
        run, thread, agent_config, provider = await self.authority(run_id, worker_id)
        from koinon.profiles.service import ProfileService

        preferences = {"locale": "en-US", "time_zone": "UTC", "response_language": "auto"}
        if self.container.contains_type(ProfileService):
            profile = await self.container.resolve(ProfileService).get(thread.subject)
            preferences = {key: profile[key] for key in preferences}
        await self.queue.presentation(run_id, worker_id, preferences)
        self.assistants.provider_address(provider.kind, provider.base_url)
        if agent_config.model_id not in provider.model_ids:
            raise ServiceUnavailableException(
                "Choose an available model for this agent", code="AGENT_MODEL_UNAVAILABLE"
            )
        state = provider_state(provider)
        if not state["discovered"]:
            raise ServiceUnavailableException(
                "Validate the provider before using this agent", code="PROVIDER_NOT_VALIDATED"
            )
        capability = next(
            (c for c in state["model_capabilities"] if c["model_id"] == agent_config.model_id), None
        )
        if capability and (
            capability["chat"]["supported"] is False
            or (agent_config.tools and capability["tools"]["supported"] is False)
        ):
            raise ServiceUnavailableException(
                "The selected model does not support this conversational agent",
                code="AGENT_MODEL_UNSUPPORTED",
            )
        secret = (
            self.assistants.secrets.decrypt(run.tenant_id, provider.id, provider.secret_ciphertext)
            if provider.secret_ciphertext
            else None
        )
        if provider.kind != "ollama" and not secret:
            raise ServiceUnavailableException(
                "Configure the provider credential", code="PROVIDER_CREDENTIAL_REQUIRED"
            )
        # Explicit keyless credentials prevent ambient host credentials from entering an organizational run.
        resolver = self.assistants.configuration_service.connections
        spec = resolver.spec(provider, agent_config.model_id, agent_config.model_options)
        attachments = self.assistants._attachment_access()
        refs = (
            await attachments.for_run(thread.subject, run.tenant_id, thread.id, run.id) if attachments else ()
        )
        observed_tools: set[str] = set()
        grounded_results: set[str] = set()
        async with self.models.build_with_secret(spec, secret or "unused") as model:
            binding_output_mode = output_mode_for(provider.kind, agent_config.model_options)
            if agent_config.model_options.get("output_mode") is not None:
                try:
                    binding_output_mode = resolver.output_mode(
                        provider, agent_config.model_id, agent_config.model_options, model
                    )
                except ValueError as error:
                    raise ServiceUnavailableException(
                        str(error), code="AGENT_MODEL_OUTPUT_MODE_UNSUPPORTED"
                    ) from error
            with bind_model(
                run.tenant_id,
                thread.subject,
                BorrowedModel(
                    model,
                    resolver.settings_for(spec),
                    provider.kind,
                    state["api"],
                    binding_output_mode,
                    agent_id=agent_config.id,
                    agent_revision=agent_config.revision,
                    provider_id=provider.id,
                    provider_revision=provider.revision,
                    model_id=agent_config.model_id,
                    options_sha256=options_fingerprint(state["api"], agent_config.model_options),
                ),
            ):
                user_message = await self.assistants.message_repository.find_by_id(run.user_message_id)
                prompt = self.prompt.render(
                    instructions=agent_config.instructions, question=user_message.text, **preferences
                )
                factory = self.container.resolve(AgentFactory)
                tools = await self.tools(
                    run.id,
                    worker_id,
                    agent_config.tools,
                    observed_tools,
                    grounded_results,
                    attachment_refs=refs,
                    private_search_enabled=not capability or capability["tools"]["supported"] is not False,
                )
                budget = history_budget(
                    self.assistants.settings,
                    system=prompt.system,
                    question=prompt.user,
                    tools=tools,
                    output_tokens=(spec.options.max_tokens or 4096) if spec.options else 4096,
                )
                user_prompt = prompt.user
                if refs:
                    assert attachments is not None
                    binary_budget = None

                    async def fits_text(value):
                        try:
                            history_budget(
                                self.assistants.settings,
                                system=prompt.system,
                                question=value,
                                tools=tools,
                                output_tokens=spec.options.max_tokens if spec.options else 4096,
                            )
                            return True
                        except InvalidRequestException:
                            return False

                    async def fits_binary(value):
                        nonlocal binary_budget
                        await self.authority(run_id, worker_id)
                        await attachments.authorize_evidence(thread.subject, run.tenant_id, thread.id, refs)
                        try:
                            usage = await model.count_tokens(
                                [
                                    ModelRequest(
                                        parts=[SystemPromptPart(prompt.system), UserPromptPart(value)]
                                    )
                                ],
                                resolver.settings_for(spec),
                                ModelRequestParameters(
                                    function_tools=[
                                        PydanticTool(
                                            tool.pydantic_handler(),
                                            name=tool.name,
                                            description=tool.description,
                                        ).tool_def
                                        for tool in tools
                                    ]
                                ),
                            )
                        except NotImplementedError:
                            return False
                        reserved = (
                            usage.input_tokens
                            + (spec.options.max_tokens if spec.options else 4096)
                            + self.assistants.settings.tool_result_tokens
                            + 512
                        )
                        binary_budget = self.assistants.settings.max_context_tokens - reserved
                        return binary_budget >= 0

                    private = await prepare_attachment_input(
                        attachments,
                        subject=thread.subject,
                        tenant_id=run.tenant_id,
                        thread_id=thread.id,
                        refs=refs,
                        question=prompt.user,
                        fits_text=fits_text,
                        input_modalities=input_modalities(capability),
                        fits_binary=fits_binary,
                    )
                    user_prompt = private.prompt
                    budget = history_budget(
                        self.assistants.settings,
                        system=prompt.system,
                        question=private.text,
                        tools=tools,
                        output_tokens=spec.options.max_tokens if spec.options else 4096,
                    )
                    if binary_budget is not None:
                        budget = min(budget, binary_budget)
                    await self.authority(run_id, worker_id)
                    await attachments.authorize_evidence(thread.subject, run.tenant_id, thread.id, refs)
                    evidence_id = await self.queue.evidence(
                        run_id, worker_id, "attachment", private.evidence, []
                    )
                    grounded_results.add(evidence_id)
                agent = factory.create(
                    name=f"koinon-chat-{run.id}",
                    model=model,
                    instructions=prompt.system,
                    output_type=str,
                    tools=tools,
                    auto_register=False,
                    memory=None,
                    model_settings=resolver.settings_for(spec),
                    model_options=spec.options,
                    config=factory.runtime.config.model_copy(update={"default_temperature": None}),
                    retries=1,
                )
                history = await self.history(run, token_budget=budget, attachment_refs=refs)
                await self.queue.begin_generation(
                    run_id,
                    worker_id,
                    model_id=agent_config.model_id,
                    model_class=spec.model_class,
                    api=state["api"],
                    binding_output_mode=binding_output_mode,
                    model_options_sha256=options_fingerprint(state["api"], agent_config.model_options),
                )
                pending = ""
                citation_labels = PrivateCitationLabels(refs)
                await self.authority(run_id, worker_id)
                async with await agent.run_stream(
                    user_prompt,
                    message_history=history,
                    usage_limits=UsageLimits(
                        request_limit=12,
                        tool_calls_limit=12,
                        input_tokens_limit=self.assistants.settings.max_context_tokens,
                    ),
                ) as stream:
                    async for delta in stream.stream_text(delta=True, debounce_by=0.05):
                        await self.authority(run_id, worker_id)
                        if delta:
                            pending += citation_labels.feed(delta)
                            if len(pending) > 256000:
                                raise InvalidRequestException(
                                    "Answer exceeds the supported size", code="ANSWER_TOO_LARGE"
                                )
                            if grounded_results and pending:
                                await self.assistants.authorize_results(thread.subject, run.tenant_id, run.id)
                                await self.queue.append(run_id, worker_id, "message_delta", {"text": pending})
                                pending = ""
                pending += citation_labels.finish()
                if grounded_results:
                    await self.authority(run_id, worker_id)
                    await self.assistants.authorize_results(thread.subject, run.tenant_id, run.id)
                    if pending:
                        await self.queue.append(run_id, worker_id, "message_delta", {"text": pending})
                    await self.queue.policy(run_id, worker_id, {"outcome": "grounded"})
                    remaining = (
                        self.assistants.settings.run_timeout_seconds
                        - (asyncio.get_running_loop().time() - started)
                        - 2
                    )
                    await self.suggest_title(run_id, worker_id, timeout=min(15.0, remaining))
                else:
                    language = preferences["response_language"]
                    code = (
                        "REVIEW_REQUIRED"
                        if "propose_catalog_update" in observed_tools
                        else "NO_MATCHING_EVIDENCE"
                        if observed_tools & {"search_knowledge", "query_dataset"}
                        else "FACTUAL_EVIDENCE_REQUIRED"
                        if "inspect_schema" in observed_tools
                        else "KNOWLEDGE_ONLY"
                    )
                    text = refusal_message(preferences["locale"] if language == "auto" else language, code)
                    await self.queue.policy(
                        run_id,
                        worker_id,
                        {
                            "outcome": "review_required" if code == "REVIEW_REQUIRED" else "refused",
                            "code": code,
                            "reason": text,
                        },
                    )
                    await self.queue.append(run_id, worker_id, "message_delta", {"text": text})
        await self.authority(run_id, worker_id)
        await self.assistants.configuration_service.record_runtime_qualification(
            run.tenant_id,
            provider.id,
            provider.revision,
            agent_config.model_id,
            sorted(observed_tools),
            spec.options.model_dump(mode="json", exclude_none=True) if spec.options else {},
        )
        await self.queue.citations(run_id, worker_id)
        await self.queue.finish(run_id, worker_id)

    async def execute(self, run_id: str, worker_id: str):
        run = await self.assistants.runs.find_by_id(run_id)
        if run is None:
            return
        thread = await self.assistants.threads.find_by_id(run.thread_id)
        issuer, _, subject = thread.subject.partition("|")
        attributes = {"iss": issuer, "sub": subject}
        if run.access_token_id:
            attributes["koinon_token_id"] = run.access_token_id
        with SecurityContextHolder.using(SecurityContext(user_id=subject, attributes=attributes)):
            await self._execute(run_id, worker_id)

    async def _execute(self, run_id: str, worker_id: str):
        async def heartbeat():
            while True:
                await asyncio.sleep(max(1, self.assistants.settings.lease_seconds // 3))
                await self.authority(run_id, worker_id)
                await self.queue.heartbeat(run_id, worker_id)

        generation = asyncio.create_task(self.generate(run_id, worker_id))
        renewal = asyncio.create_task(heartbeat())
        try:
            async with asyncio.timeout(self.assistants.settings.run_timeout_seconds):
                done, _ = await asyncio.wait({generation, renewal}, return_when=asyncio.FIRST_COMPLETED)
                for task in done:
                    task.result()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            code = getattr(exc, "code", None) or (
                "RUN_TIMEOUT" if isinstance(exc, TimeoutError) else "GENERATION_FAILED"
            )
            cause = exc
            for _ in range(12):
                cause_code = getattr(cause, "code", None)
                if cause_code in _NATIVE_POLICY_REFUSALS:
                    code = cause_code
                    break
                if getattr(cause, "code", None) == "EVIDENCE_BUDGET_EXCEEDED":
                    code = "EVIDENCE_BUDGET_EXCEEDED"
                    break
                if getattr(cause, "code", None) in {
                    "EVIDENCE_PROVENANCE_REQUIRED",
                    "EVIDENCE_UNAVAILABLE",
                    "KNOWLEDGE_CAPTURE_UNAVAILABLE",
                }:
                    code = (
                        "EVIDENCE_UNAVAILABLE"
                        if getattr(cause, "denied", False)
                        else "EVIDENCE_PROVENANCE_REQUIRED"
                    )
                    break
                nested = cause.__cause__ or cause.__context__
                if nested is None or nested is cause:
                    break
                cause = nested
            with suppress(ConflictException):
                if code in _NATIVE_POLICY_REFUSALS or code in {
                    "EVIDENCE_PROVENANCE_REQUIRED",
                    "EVIDENCE_UNAVAILABLE",
                    "EVIDENCE_BUDGET_EXCEEDED",
                }:
                    await self.queue.provenance_failure(run_id, worker_id, code)
                else:
                    await self.queue.finish(run_id, worker_id, code=str(code)[:64])
        finally:
            generation.cancel()
            renewal.cancel()
            await asyncio.gather(generation, renewal, return_exceptions=True)
