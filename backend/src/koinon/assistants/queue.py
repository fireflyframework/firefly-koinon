# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import timedelta

from pyfly.container import service
from pyfly.data.relational.sqlalchemy import LockMode, transactional
from pyfly.kernel import ConflictException, InvalidRequestException
from sqlalchemy import and_, or_, select

from koinon.assistants.entities import ChatRun
from koinon.assistants.lifecycle import timestamp
from koinon.assistants.service import AssistantService
from koinon.knowledge.capture_dtos import CapturedEvidence


@service(name="assistants.queue")
class AssistantQueue:
    def __init__(self, assistants: AssistantService):
        self.assistants = assistants

    @transactional
    async def claim(self, worker_id: str) -> ChatRun | None:
        if not worker_id or len(worker_id) > 64:
            raise InvalidRequestException("A worker identity is required", code="INVALID_WORKER")
        service = self.assistants
        session = service.runs._require_session()
        now = timestamp()
        expired = and_(ChatRun.status == "running", ChatRun.lease_until < now)
        run = await session.scalar(
            select(ChatRun)
            .where(
                or_(
                    and_(ChatRun.status == "queued", ChatRun.available_at <= now),
                    expired,
                )
            )
            .order_by(ChatRun.created_at, ChatRun.id)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        if run is None:
            return None
        message = await service.message_repository.find_by_id(run.message_id)
        if run.attempts >= 2:
            run.status, run.error_code, message.status = "failed", "WORKER_LEASE_EXPIRED", "failed"
            run.lease_until, run.worker_id = None, None
            await service.message_repository.save(message)
            await service.record_event(
                run,
                "failed",
                {
                    "status": "failed",
                    "code": run.error_code,
                    "message": "The worker stopped before completing this answer. Try again.",
                },
            )
            return None
        run.status, run.worker_id = "running", worker_id
        run.attempts += 1
        run.lease_until = now + timedelta(seconds=service.settings.lease_seconds)
        message.status = "running"
        if run.attempts > 1:
            message.text, message.citations, message.artifacts = "", [], []
            message.answer_policy = {}
            await service.record_event(run, "message_reset", {"message_id": message.id, "status": "running"})
        await service.message_repository.save(message)
        await service.record_event(
            run, "tool_activity", {"stage": "starting", "message": "Preparing your answer"}
        )
        return run

    async def locked(self, run_id: str, worker_id: str) -> ChatRun:
        run = await self.assistants.runs.find_by_id(run_id, lock=LockMode.PESSIMISTIC_WRITE)
        if (
            run is None
            or run.status != "running"
            or run.worker_id != worker_id
            or run.lease_until is None
            or run.lease_until <= timestamp()
        ):
            raise ConflictException("Worker no longer owns this answer", code="RUN_LEASE_LOST")
        return run

    @transactional
    async def begin_generation(
        self, run_id, worker_id, *, model_id, model_class, api,
        binding_output_mode=None, model_options_sha256=None,
    ):
        from koinon.assistants.audit_dtos import GenerationReceipt
        from koinon.assistants.entities import ToolResult
        from koinon.assistants.lifecycle import identifier

        run = await self.locked(run_id, worker_id)
        agent = await self.assistants.scoped(self.assistants.agents, run.tenant_id, run.agent_id)
        provider = await self.assistants.scoped(self.assistants.providers, run.tenant_id, agent.provider_id)
        if agent.revision != run.agent_revision or provider.revision != run.provider_revision:
            raise ConflictException("Agent configuration changed", code="CONFIGURATION_CHANGED")
        value = GenerationReceipt(
            id=identifier(),
            start_sequence=run.sequence,
            agent_id=agent.id,
            agent_revision=run.agent_revision,
            provider_id=provider.id,
            provider_revision=run.provider_revision,
            provider_kind=provider.kind,
            model_id=model_id,
            model_class=model_class,
            api=api,
            binding_output_mode=binding_output_mode,
            model_options_sha256=model_options_sha256,
            started_at=timestamp(),
        )
        await self.assistants.results.save(
            ToolResult(
                id=value.id,
                run_id=run.id,
                kind="generation",
                payload={
                    "generation": value.model_dump(mode="json"),
                    "origin_token_id": run.access_token_id,
                    "worker_id": worker_id,
                },
            )
        )
        return value.id

    @transactional
    async def heartbeat(self, run_id: str, worker_id: str) -> None:
        run = await self.locked(run_id, worker_id)
        run.lease_until = timestamp() + timedelta(seconds=self.assistants.settings.lease_seconds)
        await self.assistants.runs.save(run)

    @transactional
    async def append(self, run_id: str, worker_id: str, event_type: str, data: dict):
        run = await self.locked(run_id, worker_id)
        if event_type not in {"message_delta", "tool_activity", "openui_delta", "citation"}:
            raise InvalidRequestException("Unsupported generation event", code="INVALID_EVENT")
        if event_type == "message_delta":
            message = await self.assistants.message_repository.find_by_id(run.message_id)
            text = data.get("text")
            if not isinstance(text, str) or len(message.text) + len(text) > 256000:
                raise InvalidRequestException("Answer exceeds the supported size", code="ANSWER_TOO_LARGE")
            message.text += text
            await self.assistants.message_repository.save(message)
        return await self.assistants.record_event(run, event_type, data)

    @transactional
    async def tool_activity(self, run_id: str, worker_id: str, attempt: int, activity):
        from koinon.assistants.tool_activity import ToolActivity

        value = ToolActivity.model_validate(activity).model_dump(exclude_none=True)
        run = await self.assistants.runs.find_by_id(run_id, lock=LockMode.PESSIMISTIC_WRITE)
        cancelled = value["status"] == "cancelled" and run is not None and run.status == "cancelled"
        if (
            run is None
            or run.attempts != attempt
            or (
                not cancelled
                and (
                    run.worker_id != worker_id
                    or run.status != "running"
                    or run.lease_until is None
                    or run.lease_until <= timestamp()
                )
            )
        ):
            raise ConflictException("Worker no longer owns this tool invocation", code="RUN_LEASE_LOST")
        if value.get("result_id"):
            result = await self.assistants.results.find_by_id(value["result_id"])
            if result is None or result.run_id != run_id:
                raise InvalidRequestException("Tool result is outside this answer", code="EVIDENCE_DENIED")
        return await self.assistants.record_event(run, "tool_activity", {"tool_activity": value})

    @transactional
    async def provenance_failure(self, run_id, worker_id, code):
        from koinon.assistants.grounding import refusal_message

        run = await self.locked(run_id, worker_id)
        message = await self.assistants.message_repository.find_by_id(run.message_id)
        preferences = message.presentation or {}
        language = preferences.get("response_language", "auto")
        text = refusal_message(preferences.get("locale", "en-US") if language == "auto" else language, code)
        await self.policy(run_id, worker_id, {"outcome": "refused", "code": code, "reason": text})
        if not message.text:
            await self.append(run_id, worker_id, "message_delta", {"text": text})
        await self.finish(run_id, worker_id, code=code)

    @transactional
    async def finish(self, run_id: str, worker_id: str, *, code: str | None = None):
        run = await self.locked(run_id, worker_id)
        generations = [
            row
            for row in await self.assistants.results.find_all(run_id=run_id)
            if row.kind == "generation" and row.payload.get("worker_id") == worker_id
        ]
        result = (
            max(generations, key=lambda row: (row.payload["generation"]["start_sequence"], row.created_at))
            if generations
            else None
        )
        if result is not None and result.payload["generation"].get("finished_at") is None:
            value = dict(result.payload["generation"])
            value.update(finished_at=timestamp().isoformat(), status="failed" if code else "completed")
            result.payload = {**result.payload, "generation": value}
            await self.assistants.results.save(result)
        run.status, run.error_code = ("failed", code) if code else ("completed", None)
        run.worker_id, run.lease_until = None, None
        message = await self.assistants.message_repository.find_by_id(run.message_id)
        message.status = run.status
        await self.assistants.message_repository.save(message)
        await self.assistants.record_event(
            run,
            "failed" if code else "completed",
            {
                "status": run.status,
                "code": code,
                "message": "The answer could not be completed. Check the agent settings and try again."
                if code
                else "Answer complete",
            },
        )

    async def capture_manifest(self, run, kind, data, assets, capture):
        import json
        from contextlib import nullcontext

        from pyfly.kernel import ServiceUnavailableException
        from pyfly.security.context import SecurityContext
        from pyfly.security.context_holder import SecurityContextHolder

        from koinon.evidence.dtos import SourceReference

        def invalid():
            return InvalidRequestException(
                "Native source capture does not match this evidence", code="EVIDENCE_CAPTURE_INVALID"
            )

        if (
            not isinstance(capture, CapturedEvidence)
            or kind not in {"search", "query", "schema"}
            or type(capture.complete) is not bool
        ):
            raise invalid()

        if not capture.complete:
            raise ServiceUnavailableException(
                "Exact source provenance is required before using this evidence",
                code="EVIDENCE_PROVENANCE_REQUIRED",
            )

        def canonical(value):
            return json.dumps(
                value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":")
            )

        try:
            if canonical(capture.data) != canonical(data):
                raise invalid()
            sources = tuple(
                SourceReference.model_validate(value.model_dump(mode="json")) for value in capture.sources
            )
        except (AttributeError, TypeError, ValueError) as error:
            raise invalid() from error
        ids = {value.id for value in sources}
        covered = {value.asset_id for value in sources}
        if (
            len(sources) > 500
            or len(ids) != len(sources)
            or covered - set(assets)
            or (
                capture.complete
                and (covered != set(assets) or any(value.used_revision is None for value in sources))
            )
        ):
            raise invalid()
        thread = await self.assistants.threads.find_by_id(run.thread_id)
        context = nullcontext()
        if run.access_token_id:
            if self.assistants.catalog.restriction is None:
                raise ServiceUnavailableException(
                    "Originating authority is unavailable", code="TOKEN_AUTHORITY_UNAVAILABLE"
                )
            issuer, _, sub = thread.subject.partition("|")
            context = SecurityContextHolder.using(
                SecurityContext(
                    user_id=sub,
                    attributes={"iss": issuer, "sub": sub, "koinon_token_id": run.access_token_id},
                )
            )
        with context:
            await self.assistants.validate_scope(thread.subject, run.tenant_id, run.scope)
            for offset in range(0, len(assets), 128):
                await self.assistants.validate_scope(
                    thread.subject, run.tenant_id, {"asset_ids": assets[offset : offset + 128]}, run.scope
                )
            admitted = {}
            for asset_id in assets:
                entry = await self.assistants.catalog.get(thread.subject, run.tenant_id, asset_id)
                if entry.kind not in ({"document", "knowledge_item"} if kind == "search" else {"dataset"}):
                    raise invalid()
                await self.assistants.catalog.authorize(
                    thread.subject,
                    run.tenant_id,
                    "knowledge:search"
                    if kind == "search"
                    else "query:execute"
                    if kind == "query"
                    else "catalog:read",
                    entry.workspace_id,
                )
                admitted[asset_id] = entry
            for source in sources:
                entry = admitted[source.asset_id]
                if (
                    "knowledge_item" if source.kind == "knowledge_version" else source.kind
                ) != entry.kind or (source.source_id is not None and source.source_id != entry.parent_id):
                    raise invalid()
        return {
            "version": 1,
            "complete": capture.complete,
            "sources": [value.model_dump(mode="json") for value in sources],
        }

    async def native_receipts(self, run, assets, capture, result_id, generation_id, *, authorized=True):
        values = {}
        from dataclasses import asdict

        from koinon.assistants.audit_dtos import NativeReadReceipt, RlmToolReceipt, SqlAttemptReceipt

        try:
            reads = [
                NativeReadReceipt(result_id=result_id, generation_id=generation_id, **asdict(row))
                for row in capture.native_reads
            ]
            attempts = [
                SqlAttemptReceipt(result_id=result_id, generation_id=generation_id, **asdict(row))
                for row in capture.sql_attempts
            ]
            tools = [RlmToolReceipt(result_id=result_id, generation_id=generation_id,
                                    **row.model_dump(mode="json")) for row in capture.rlm_tools or ()]
            if (
                len(reads) > 512
                or len(attempts) > 128
                or len(tools) > 256
                or any(row.tenant_id != run.tenant_id for row in tools)
                or any(not set(row.source_ids) <= {
                    source for read in reads for source in read.source_ids
                } for row in tools)
                or any(row.tenant_id != run.tenant_id for row in reads)
                or len({row.ordinal for row in attempts}) != len(attempts)
            ):
                raise ValueError("Invalid native receipt scope")
            thread = await self.assistants.threads.find_by_id(run.thread_id)
            entries = {}
            for read in reads:
                if read.entity_id not in entries:
                    entries[read.entity_id] = (
                        await self.assistants.catalog.get(thread.subject, run.tenant_id, read.entity_id)
                        if authorized
                        else await self.assistants.catalog.catalog_repository.find_by_id(read.entity_id)
                    )
                entry = entries[read.entity_id]
                if (
                    entry is None
                    or entry.tenant_id != run.tenant_id
                    or entry.workspace_id != read.workspace_id
                    or read.entity_id not in assets
                ):
                    raise ValueError("Invalid native receipt resource")
            values["native_reads"] = [row.model_dump(mode="json", by_alias=True) for row in reads]
            values["sql_attempts"] = [row.model_dump(mode="json", by_alias=True) for row in attempts]
            if capture.rlm_tools is not None:
                values["rlm_tools"] = [row.model_dump(mode="json") for row in tools]
        except (TypeError, ValueError) as error:
            raise InvalidRequestException(
                "Native read receipt is invalid", code="EVIDENCE_CAPTURE_INVALID"
            ) from error
        return values

    @transactional
    async def capture_limits(self, run_id, worker_id, kind):
        from pyfly.kernel import ServiceUnavailableException

        from koinon.knowledge.capture_dtos import NativeCaptureLimits

        run = await self.locked(run_id, worker_id)
        rows = await self.assistants.active_results(run)
        reads = 1000 - sum(len(row.payload.get("native_reads", [])) for row in rows)
        attempts = 1000 - sum(len(row.payload.get("sql_attempts", [])) for row in rows)
        tools = 1000 - sum(len(row.payload.get("rlm_tools") or []) for row in rows)
        sources = {
            value["id"] for row in rows for value in row.payload.get("source_manifest", {}).get("sources", [])
        }
        if reads <= 0 or len(sources) >= 500 or kind == "query" and attempts <= 0:
            raise ServiceUnavailableException(
                "This answer reached its source audit budget. Narrow the question.",
                code="EVIDENCE_BUDGET_EXCEEDED",
            )
        return NativeCaptureLimits(
            reads=min(512, reads),
            attempts=min(128, max(0, attempts)),
            sources=500 - len(sources),
            receipt_bytes=524288,
            ids_per_read=500,
            tools=min(256, max(0, tools)),
        )

    async def check_audit_budget(self, run, payload):
        from pyfly.kernel import ServiceUnavailableException

        rows = await self.assistants.active_results(run)
        values = [row.payload for row in rows] + [payload]
        sources = {
            row["id"] for value in values for row in value.get("source_manifest", {}).get("sources", [])
        }
        if (
            sum(len(row.get("native_reads", [])) for row in values) > 1000
            or sum(len(row.get("sql_attempts", [])) for row in values) > 1000
            or sum(len(row.get("rlm_tools") or []) for row in values) > 1000
            or len(sources) > 500
        ):
            raise ServiceUnavailableException(
                "This answer reached its source audit budget. Narrow the question.",
                code="EVIDENCE_BUDGET_EXCEEDED",
            )

    @transactional
    async def observation(self, run_id, worker_id, kind, assets, *, capture):
        import json

        from koinon.assistants.entities import ToolResult
        from koinon.assistants.lifecycle import identifier
        from koinon.evidence.dtos import SourceReference

        run = await self.locked(run_id, worker_id)
        if not isinstance(capture, CapturedEvidence) or kind not in {"search", "query", "schema"}:
            raise InvalidRequestException("Invalid audit receipt", code="EVIDENCE_CAPTURE_INVALID")
        admitted = {}
        for asset_id in assets:
            entry = await self.assistants.catalog.catalog_repository.find_by_id(asset_id)
            if (
                entry is None
                or entry.tenant_id != run.tenant_id
                or entry.kind not in {"document", "dataset", "knowledge_item"}
                or "asset_ids" in run.scope
                and asset_id not in run.scope["asset_ids"]
                or run.scope.get("workspace_id")
                and entry.workspace_id != run.scope["workspace_id"]
                or run.scope.get("project_id")
                and entry.project_id != run.scope["project_id"]
            ):
                raise InvalidRequestException(
                    "Audit receipt exceeds admitted scope", code="EVIDENCE_CAPTURE_INVALID"
                )
            admitted[asset_id] = entry
        sources = [SourceReference.model_validate(row.model_dump(mode="json")) for row in capture.sources]
        if len(sources) > 500 or any(
            row.asset_id not in admitted or row.kind != admitted[row.asset_id].kind for row in sources
        ):
            raise InvalidRequestException(
                "Audit receipt exceeds admitted scope", code="EVIDENCE_CAPTURE_INVALID"
            )
        result_id = identifier()
        generations = [
            row
            for row in await self.assistants.results.find_all(run_id=run_id)
            if row.kind == "generation"
            and row.payload.get("worker_id") == worker_id
            and row.payload["generation"].get("finished_at") is None
        ]
        generation_id = (
            max(generations, key=lambda row: (row.payload["generation"]["start_sequence"], row.created_at)).id
            if generations
            else None
        )
        payload = {
            "asset_ids": assets,
            "origin_token_id": run.access_token_id,
            "generation_id": generation_id,
            "source_manifest": {
                "version": 1,
                "complete": False,
                "sources": [row.model_dump(mode="json") for row in sources],
            },
        }
        # Retain work admitted before revocation; audit reads still enforce current/original authority.
        payload.update(
            await self.native_receipts(run, assets, capture, result_id, generation_id, authorized=False)
        )
        if len(json.dumps(payload, ensure_ascii=False, allow_nan=False).encode()) > 524288:
            raise InvalidRequestException("Audit receipt is too large", code="EVIDENCE_TOO_LARGE")
        await self.check_audit_budget(run, payload)
        await self.assistants.results.save(
            ToolResult(id=result_id, run_id=run.id, kind="observation", payload=payload)
        )
        return result_id

    @transactional
    async def evidence(
        self,
        run_id: str,
        worker_id: str,
        kind: str,
        data: dict,
        assets: list[str],
        *,
        capture: CapturedEvidence | None = None,
    ) -> str:
        import json

        from koinon.assistants.entities import ToolResult
        from koinon.assistants.lifecycle import identifier

        if (
            kind not in {"search", "query", "schema", "lineage", "attachment"}
            or len(json.dumps(data)) > 524288
        ):
            raise InvalidRequestException("Evidence exceeds the supported size", code="EVIDENCE_TOO_LARGE")
        if kind in {"search", "query", "schema"} and capture is None:
            from pyfly.kernel import ServiceUnavailableException

            raise ServiceUnavailableException(
                "A trusted native source receipt is required", code="EVIDENCE_PROVENANCE_REQUIRED"
            )
        run = await self.locked(run_id, worker_id)
        payload = {"data": data, "asset_ids": assets, "origin_token_id": run.access_token_id}
        if capture is not None:
            payload["source_manifest"] = await self.capture_manifest(run, kind, data, assets, capture)
            await self.locked(run_id, worker_id)
        if len(json.dumps(payload, ensure_ascii=False, allow_nan=False).encode()) > 524288:
            raise InvalidRequestException("Evidence exceeds the supported size", code="EVIDENCE_TOO_LARGE")
        result_id = identifier()
        generations = [
            row
            for row in await self.assistants.results.find_all(run_id=run_id)
            if row.kind == "generation"
            and row.payload.get("worker_id") == worker_id
            and row.payload["generation"].get("finished_at") is None
        ]
        generation_id = (
            max(generations, key=lambda row: (row.payload["generation"]["start_sequence"], row.created_at)).id
            if generations
            else None
        )
        if generation_id:
            payload["generation_id"] = generation_id
        if capture is not None:
            payload.update(await self.native_receipts(run, assets, capture, result_id, generation_id))
        if len(json.dumps(payload, ensure_ascii=False, allow_nan=False).encode()) > 524288:
            raise InvalidRequestException("Evidence exceeds the supported size", code="EVIDENCE_TOO_LARGE")
        await self.check_audit_budget(run, payload)
        result = await self.assistants.results.save(
            ToolResult(id=result_id, run_id=run_id, kind=kind, payload=payload)
        )
        language = f'root = KnowledgeAnswer([item])\nitem = Evidence("{result.id}", "auto")'
        artifact = {
            "id": result.id,
            "kind": "openui",
            "language": language,
            "complete": True,
            "run_id": run_id,
        }
        message = await self.assistants.message_repository.find_by_id(run.message_id)
        message.artifacts = [*message.artifacts, artifact]
        await self.assistants.message_repository.save(message)
        await self.assistants.record_event(run, "openui_delta", {"artifact": artifact})
        return result.id

    @transactional
    async def citations(self, run_id: str, worker_id: str):
        import re

        run = await self.locked(run_id, worker_id)
        message = await self.assistants.message_repository.find_by_id(run.message_id)
        admitted = {}
        for result in await self.assistants.results.find_all(run_id=run_id):
            if result.kind == "search":
                for hit in result.payload["data"].get("hits", []):
                    admitted[hit["asset_id"]] = {
                        "asset_id": hit["asset_id"],
                        "source_id": hit.get("source_id"),
                        "title": hit.get("title"),
                        "text": hit.get("text"),
                    }
        referenced = list(dict.fromkeys(re.findall(r"\[source:([^\]\s]+)\]", message.text)))
        if set(referenced) - admitted.keys():
            raise InvalidRequestException(
                "The answer referenced an unverified source", code="UNVERIFIED_CITATION"
            )
        message.citations = [admitted[asset_id] for asset_id in referenced]
        await self.assistants.message_repository.save(message)
        for citation in message.citations:
            await self.assistants.record_event(run, "citation", {"citation": citation})

    @transactional
    async def presentation(self, run_id: str, worker_id: str, preferences: dict):
        run = await self.locked(run_id, worker_id)
        message = await self.assistants.message_repository.find_by_id(run.message_id)
        message.presentation = {key: preferences[key] for key in ("locale", "time_zone", "response_language")}
        await self.assistants.message_repository.save(message)
        await self.assistants.record_event(run, "message_metadata", {"presentation": message.presentation})

    @transactional
    async def policy(self, run_id: str, worker_id: str, value):
        from koinon.assistants.policy_dtos import AnswerPolicy

        policy = AnswerPolicy.model_validate(value).model_dump(exclude_none=True)
        run = await self.locked(run_id, worker_id)
        message = await self.assistants.message_repository.find_by_id(run.message_id)
        message.answer_policy = policy
        await self.assistants.message_repository.save(message)
        await self.assistants.record_event(run, "message_metadata", {"answer_policy": policy})
