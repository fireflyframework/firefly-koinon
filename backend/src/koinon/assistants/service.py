# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Owner-scoped conversation lifecycle and durable generation requests."""

import base64
import hashlib
import json
from datetime import datetime

from pyfly.container import Provider, service
from pyfly.data.relational.sqlalchemy import LockMode, transactional
from pyfly.kernel import ConflictException, InvalidRequestException, ServiceUnavailableException
from pyfly.security.context_holder import SecurityContextHolder

from koinon.assistants.configuration_service import AssistantConfigurationService
from koinon.assistants.entities import AgentConfiguration, ChatMessage, ChatRun, ChatThread
from koinon.assistants.lifecycle import identifier, timestamp
from koinon.assistants.mappers import message_dto, thread_dto
from koinon.assistants.probe import ProviderProbe
from koinon.assistants.repositories import (
    AgentRepository,
    ChatEventRepository,
    ChatMessageRepository,
    ChatRunRepository,
    ChatThreadRepository,
    ProviderRepository,
    ToolResultRepository,
)
from koinon.assistants.scope import KnowledgeScopePolicy
from koinon.assistants.settings import AssistantSettings, ProviderSecrets
from koinon.catalog.errors import AccessDenied
from koinon.catalog.service import CatalogService
from koinon.knowledge.attachments.ports import AttachmentRef, ChatAttachmentAccess
from koinon.operations.settings import OperationalSettings
from koinon.organization_knowledge.runtime import snapshot_for_run
from koinon.organization_knowledge.service import OrganizationKnowledgeService


@service(name="assistants.service")
class AssistantService:
    def __init__(
        self,
        catalog: CatalogService,
        providers: ProviderRepository,
        agents: AgentRepository,
        threads: ChatThreadRepository,
        messages: ChatMessageRepository,
        runs: ChatRunRepository,
        events: ChatEventRepository,
        results: ToolResultRepository,
        secrets: ProviderSecrets,
        settings: AssistantSettings,
        probe: ProviderProbe,
        configuration_service: AssistantConfigurationService,
        scope_policy: KnowledgeScopePolicy,
        operations: OperationalSettings | None = None,
        attachments: ChatAttachmentAccess | None = None,
        attachment_provider: Provider[ChatAttachmentAccess | None] | None = None,
        organization_knowledge: OrganizationKnowledgeService | None = None,
    ):
        self.catalog, self.providers, self.agents = catalog, providers, agents
        self.threads, self.message_repository, self.runs, self.events = threads, messages, runs, events
        self.results, self.secrets, self.settings = results, secrets, settings
        self.probe = probe

        self.configuration_service, self.scope_policy = configuration_service, scope_policy
        self.operations = operations or OperationalSettings()
        self.attachments = attachments
        self.attachment_provider = attachment_provider
        self.organization_knowledge = organization_knowledge

    def _attachment_access(self) -> ChatAttachmentAccess | None:
        if self.attachments is not None:
            return self.attachments
        return self.attachment_provider.get() if self.attachment_provider is not None else None

    async def require_queue_capacity(self, subject: str, tenant_id: str) -> None:
        # A tenant row serializes admission across this owner's separate conversations.
        await self.catalog._lock_tenant(tenant_id)
        if (
            await self.runs.count_active_for_subject(tenant_id, subject)
            >= self.operations.max_queued_per_subject
        ):
            raise ConflictException(
                "Your answer queue is full. Wait for an answer or cancel one before trying again.",
                code="QUEUE_LIMIT_REACHED",
            )

    async def thread(self, subject: str, tenant_id: str, thread_id: str, *, lock=False) -> ChatThread:
        row = await self.threads.find_by_id(thread_id, lock=LockMode.PESSIMISTIC_WRITE if lock else None)
        if row is None or row.tenant_id != tenant_id or row.subject != subject:
            raise AccessDenied("Conversation is unavailable", code="ACCESS_DENIED")
        await self.validate_scope(subject, tenant_id, row.scope)
        return row

    async def create_thread(self, subject: str, tenant_id: str, values: dict) -> dict:
        scope = await self.validate_scope(subject, tenant_id, values.get("scope", {}))
        title = str(values.get("title", "New conversation")).strip()
        if not title or len(title) > 160:
            raise InvalidRequestException(
                "Choose a conversation title up to 160 characters", code="INVALID_THREAD"
            )
        return thread_dto(
            await self.threads.save(
                ChatThread(
                    id=identifier(),
                    tenant_id=tenant_id,
                    subject=subject,
                    title=title,
                    scope=scope,
                    title_source="manual" if "title" in values else "default",
                )
            )
        )

    async def list_threads(self, subject: str, tenant_id: str, *, scope: dict | None = None) -> list[dict]:
        if scope is not None:
            await self.validate_scope(subject, tenant_id, scope)
        visible = []
        for row in await self.threads.find_all(subject=subject, tenant_id=tenant_id):
            try:
                await self.validate_scope(subject, tenant_id, row.scope)
            except AccessDenied:
                continue
            visible.append(thread_dto(row))
        if not visible and scope is None:
            await self.catalog.authorize(subject, tenant_id, "chat:use")
        return sorted(visible, key=lambda row: row["updated_at"], reverse=True)

    async def messages(self, subject: str, tenant_id: str, thread_id: str) -> list[dict]:
        return (await self.message_page(subject, tenant_id, thread_id, limit=100))["items"]

    async def message_page(
        self, subject: str, tenant_id: str, thread_id: str, *, before=None, limit=50
    ) -> dict:
        await self.thread(subject, tenant_id, thread_id)
        if not 1 <= limit <= 100:
            raise InvalidRequestException("Choose a message limit from 1 to 100", code="INVALID_PAGE")
        cursor = None
        if before:
            try:
                if len(before) > 512:
                    raise ValueError("Invalid cursor")
                stamp, message_id = json.loads(base64.urlsafe_b64decode(before + "=" * (-len(before) % 4)))
                moment = datetime.fromisoformat(stamp)
                if moment.tzinfo is None or not isinstance(message_id, str):
                    raise ValueError("Invalid cursor")
                cursor = (moment, message_id)
            except (ValueError, TypeError, KeyError) as exc:
                raise InvalidRequestException("Invalid message cursor", code="INVALID_CURSOR") from exc
        rows = await self.message_repository.find_thread_messages(thread_id, before=cursor, limit=limit + 1)
        visible = rows[:limit]
        items = []
        activities = await self.events.activity_previews([row[1] for row in visible if row[1]])
        attachments = self._attachment_access()
        for message, run_id, sequence in reversed(visible):
            if run_id:
                await self.authorize_results(subject, tenant_id, run_id)
            summaries = (
                await attachments.summaries_for_message(subject, tenant_id, thread_id, message.id)
                if attachments is not None
                else ()
            )
            items.append(
                {
                    **message_dto(message),
                    **(
                        {
                            "run_id": run_id,
                            "event_cursor": str(sequence),
                            "tool_activities": activities[run_id]["items"],
                            "tool_activity_count": activities[run_id]["total"],
                            "tool_activity_has_more": activities[run_id]["total"]
                            > len(activities[run_id]["items"]),
                        }
                        if run_id
                        else {}
                    ),
                    **(
                        {"attachments": [item.model_dump(mode="json") for item in summaries]}
                        if summaries
                        else {}
                    ),
                }
            )
        next_cursor = None
        if len(rows) > limit:
            oldest = visible[-1][0]
            next_cursor = (
                base64.urlsafe_b64encode(json.dumps([oldest.created_at.isoformat(), oldest.id]).encode())
                .decode()
                .rstrip("=")
            )
        return {"items": items, "next_cursor": next_cursor}

    @transactional
    async def submit(self, subject: str, tenant_id: str, thread_id: str, values: dict) -> dict:
        # Match metadata mutations: tenant admission lock precedes the conversation lock.
        await self.catalog._lock_tenant(tenant_id)
        thread = await self.thread(subject, tenant_id, thread_id, lock=True)
        if thread.archived_at is not None:
            raise ConflictException(
                "Restore the conversation before sending a message", code="THREAD_ARCHIVED"
            )
        message = str(values.get("message", "")).strip()
        key = values.get("client_request_id", "")
        if not message or len(message) > 32000 or not isinstance(key, str) or not 1 <= len(key) <= 255:
            raise InvalidRequestException(
                "Enter a message and a request identifier", code="INVALID_CHAT_REQUEST"
            )
        agent = await self.scoped(self.agents, tenant_id, values.get("agent_id", ""))
        provider = await self.scoped(self.providers, tenant_id, agent.provider_id)
        if not agent.enabled or not provider.enabled:
            raise ConflictException("The selected agent is disabled", code="AGENT_UNAVAILABLE")
        scope = await self.validate_scope(subject, tenant_id, values.get("scope", {}), thread.scope)
        scope = await self.validate_scope(subject, tenant_id, scope, agent.scope)
        ids = values.get("attachment_ids", [])
        if (
            not isinstance(ids, list)
            or len(ids) > 10
            or any(not isinstance(value, str) or not 1 <= len(value) <= 64 for value in ids)
            or len(set(ids)) != len(ids)
        ):
            raise InvalidRequestException(
                "Choose up to 10 distinct files", code="INVALID_ATTACHMENT_SELECTION"
            )
        refs: tuple[AttachmentRef, ...] = ()
        attachments = self._attachment_access()
        if ids:
            if attachments is None:
                raise ServiceUnavailableException(
                    "File attachments are not enabled in this deployment", code="ATTACHMENTS_UNAVAILABLE"
                )
            refs = await attachments.validate_selection(subject, tenant_id, thread_id, ids)
        payload: list[object] = [agent.id, message, scope]
        # Preserve existing text-only idempotency keys across the additive attachment upgrade.
        if refs:
            payload.append([[ref.id, ref.sha256, ref.revision] for ref in refs])
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        existing = await self.runs.find_all(thread_id=thread_id, client_request_id=key)
        if existing:
            if existing[0].payload_hash != digest:
                raise ConflictException(
                    "Request identifier belongs to another message", code="IDEMPOTENCY_CONFLICT"
                )
            return {"run_id": existing[0].id, "message_id": existing[0].message_id, "event_cursor": "0"}
        if any(row.status in {"queued", "running"} for row in await self.runs.find_all(thread_id=thread_id)):
            raise ConflictException("Wait for or cancel the current answer", code="THREAD_BUSY")
        await self.require_queue_capacity(subject, tenant_id)
        if self.organization_knowledge is None:
            raise ServiceUnavailableException(
                "Organization knowledge settings are unavailable", code="KNOWLEDGE_SETTINGS_UNAVAILABLE"
            )
        knowledge_settings = await self.organization_knowledge.snapshot(subject, tenant_id)
        user = await self.message_repository.save(
            ChatMessage(id=identifier(), thread_id=thread_id, role="user", text=message)
        )
        answer = await self.message_repository.save(
            ChatMessage(id=identifier(), thread_id=thread_id, role="assistant", status="queued")
        )
        active_context = SecurityContextHolder.get_context()
        run = await self.runs.save(
            ChatRun(
                id=identifier(),
                tenant_id=tenant_id,
                thread_id=thread_id,
                user_message_id=user.id,
                message_id=answer.id,
                agent_id=agent.id,
                access_token_id=active_context.attributes.get("koinon_token_id") if active_context else None,
                agent_revision=agent.revision,
                provider_revision=provider.revision,
                knowledge_settings_snapshot=knowledge_settings.model_dump(mode="json"),
                scope=scope,
                client_request_id=key,
                payload_hash=digest,
            )
        )
        if refs and attachments is not None:
            await attachments.pin_selection(
                subject, tenant_id, thread_id, refs, run_id=run.id, message_id=user.id
            )
        thread.updated_at = timestamp()
        await self.threads.save(thread)
        return {"run_id": run.id, "message_id": answer.id, "event_cursor": "0"}

    async def owned_run(
        self,
        subject: str,
        tenant_id: str,
        run_id: str,
        *,
        lock=False,
        require_attachment_use=True,
        require_origin=True,
    ) -> ChatRun:
        run = await self.scoped(self.runs, tenant_id, run_id)
        await self.thread(subject, tenant_id, run.thread_id)
        await self.validate_scope(subject, tenant_id, run.scope)
        await self.authorize_results(subject, tenant_id, run_id, require_origin=require_origin)
        attachments = self._attachment_access()
        if require_attachment_use and attachments is not None:
            await attachments.for_run(subject, tenant_id, run.thread_id, run_id)
        if lock:
            run = await self.runs.find_by_id(run_id, lock=LockMode.PESSIMISTIC_WRITE)
        return run

    async def record_event(self, run: ChatRun, event_type: str, data: dict):
        from koinon.assistants.entities import ChatEvent

        run.sequence += 1
        run.updated_at = timestamp()
        event = await self.events.save(
            ChatEvent(id=identifier(), run_id=run.id, sequence=run.sequence, type=event_type, data=data)
        )
        await self.runs.save(run)
        return event

    async def run_events(self, subject: str, tenant_id: str, run_id: str, after=0) -> list[dict]:
        await self.owned_run(subject, tenant_id, run_id)
        try:
            cursor = int(after)
        except (TypeError, ValueError) as exc:
            raise InvalidRequestException("Invalid event cursor", code="INVALID_CURSOR") from exc
        if cursor < 0:
            raise InvalidRequestException("Invalid event cursor", code="INVALID_CURSOR")
        reset = await self.events.latest_reset(run_id)
        cursor = max(cursor, reset - 1) if reset is not None else cursor
        rows = await self.events.find_after(run_id, cursor)
        return [
            {"id": str(event.sequence), "type": event.type, "data": event.data}
            for event in sorted(rows, key=lambda event: event.sequence)
            if event.sequence > cursor
        ]

    @transactional
    async def cancel(self, subject: str, tenant_id: str, run_id: str) -> dict:
        # An owner must still be able to stop a run after its private input expires.
        run = await self.owned_run(
            subject, tenant_id, run_id, lock=True, require_attachment_use=False, require_origin=False
        )
        if run.status in {"completed", "failed", "cancelled"}:
            raise ConflictException("This answer has already finished", code="RUN_TERMINAL")
        run.status, run.worker_id, run.lease_until = "cancelled", None, None
        message = await self.message_repository.find_by_id(run.message_id)
        message.status = "cancelled"
        await self.message_repository.save(message)
        await self.record_event(run, "cancelled", {"status": "cancelled"})
        return {
            "run_id": run.id,
            "message_id": run.message_id,
            "status": run.status,
            "event_cursor": str(run.sequence),
        }

    @transactional
    async def retry(self, subject: str, tenant_id: str, run_id: str) -> dict:
        await self.catalog._lock_tenant(tenant_id)
        initial = await self.owned_run(subject, tenant_id, run_id, require_origin=False)
        thread = await self.thread(subject, tenant_id, initial.thread_id, lock=True)
        if thread.archived_at is not None:
            raise ConflictException("Restore the conversation before retrying", code="THREAD_ARCHIVED")
        run = await self.runs.find_by_id(run_id, lock=LockMode.PESSIMISTIC_WRITE)
        if run.status not in {"failed", "cancelled"}:
            raise ConflictException(
                "Only a failed or cancelled answer can be retried", code="RUN_NOT_RETRYABLE"
            )
        snapshot_for_run(run)
        if any(
            row.status in {"queued", "running"} for row in await self.runs.find_all(thread_id=run.thread_id)
        ):
            raise ConflictException("Wait for or cancel the current answer", code="THREAD_BUSY")
        agent = await self.scoped(self.agents, tenant_id, run.agent_id)
        provider = await self.scoped(self.providers, tenant_id, agent.provider_id)
        if not agent.enabled or not provider.enabled:
            raise ConflictException("The selected agent is disabled", code="AGENT_UNAVAILABLE")
        await self.require_queue_capacity(subject, tenant_id)
        active_context = SecurityContextHolder.get_context()
        run.access_token_id = active_context.attributes.get("koinon_token_id") if active_context else None
        run.agent_revision, run.provider_revision = agent.revision, provider.revision
        run.scope = await self.validate_scope(subject, tenant_id, run.scope, agent.scope)
        run.status, run.worker_id, run.lease_until, run.error_code = "queued", None, None, None
        run.attempts, run.available_at = 0, timestamp()
        message = await self.message_repository.find_by_id(run.message_id)
        message.text, message.status, message.citations, message.artifacts = "", "queued", [], []
        message.answer_policy = {}
        await self.message_repository.save(message)
        await self.record_event(run, "message_reset", {"status": "queued", "message_id": message.id})
        return {
            "run_id": run.id,
            "message_id": run.message_id,
            "status": run.status,
            "event_cursor": str(run.sequence),
        }

    @transactional(read_only=True)
    async def activity_page(
        self, subject: str, tenant_id: str, run_id: str, *, page: int = 1, page_size: int = 25
    ):
        await self.owned_run(subject, tenant_id, run_id, require_attachment_use=False, require_origin=False)
        if type(page) is not int or type(page_size) is not int or page < 1 or not 1 <= page_size <= 100:
            raise InvalidRequestException(
                "Choose a positive page and a page size from 1 to 100", code="INVALID_PAGE"
            )
        return await self.events.activity_page(run_id, page=page, page_size=page_size)

    async def active_results(self, run, rows=None):
        rows = list(await self.results.find_all(run_id=run.id)) if rows is None else rows
        reset = await self.events.latest_reset(run.id)
        if reset is None:
            return rows
        message = await self.message_repository.find_by_id(run.message_id)
        ids = {
            value["id"]
            for value in message.artifacts or []
            if value.get("run_id") == run.id and value.get("id")
        }
        generations = [
            row
            for row in rows
            if row.kind == "generation" and row.payload["generation"]["start_sequence"] >= reset
        ]
        current = (
            max(generations, key=lambda row: (row.payload["generation"]["start_sequence"], row.created_at))
            if generations
            else None
        )
        return [
            row
            for row in rows
            if row.id in ids
            or current is not None
            and (row.id == current.id or row.payload.get("generation_id") == current.id)
        ]

    async def origin_authority(self, subject, tenant_id, run, rows, *, include_run=True):
        from pyfly.security.context import SecurityContext

        identifiers = {row.payload.get("origin_token_id") for row in rows}
        if include_run or any("origin_token_id" not in row.payload for row in rows):
            identifiers.add(run.access_token_id)
        for token_id in identifiers - {None}:
            if self.catalog.restriction is None:
                raise ServiceUnavailableException(
                    "Originating authority is unavailable", code="TOKEN_AUTHORITY_UNAVAILABLE"
                )
            issuer, _, sub = subject.partition("|")
            with SecurityContextHolder.using(
                SecurityContext(
                    user_id=sub, attributes={"iss": issuer, "sub": sub, "koinon_token_id": token_id}
                )
            ):
                token = await self.catalog.restriction.grant(subject)
                if token is None or token.tenant_id != tenant_id:
                    raise AccessDenied("Originating authority is unavailable", code="EVIDENCE_UNAVAILABLE")
                await self.validate_scope(subject, tenant_id, run.scope)
                for row in rows:
                    for asset_id in row.payload.get("asset_ids", []):
                        await self.catalog.get(subject, tenant_id, asset_id)

    async def authorize_results(self, subject: str, tenant_id: str, run_id: str, *, require_origin=True):
        run = await self.scoped(self.runs, tenant_id, run_id)
        rows = await self.active_results(run)
        for result in rows:
            for asset_id in result.payload.get("asset_ids", []):
                await self.catalog.get(subject, tenant_id, asset_id)
        if require_origin:
            await self.origin_authority(subject, tenant_id, run, rows)

    @transactional(read_only=True)
    async def thread_page(
        self, subject, tenant_id, *, q="", page=1, page_size=25, sort="updated_at", order="desc"
    ):
        from koinon.web.pagination import sql_page

        visible = {row["id"]: row for row in await self.list_threads(subject, tenant_id)}
        result = await sql_page(
            ChatThread,
            [ChatThread.tenant_id == tenant_id, ChatThread.subject == subject, ChatThread.id.in_(visible)],
            page=page,
            page_size=page_size,
            q=q,
            search=("title",),
            sort=sort,
            order=order,
            sorts=("title", "created_at", "updated_at"),
        )
        return {**result, "items": [thread_dto(row) for row in result["items"]]}

    async def _save_validation(
        self, subject: str, tenant_id: str, provider_id: str, revision: int, checks: list[dict]
    ):
        return await self.configuration_service._save_validation(
            subject, tenant_id, provider_id, revision, checks
        )

    async def agent_dto(self, row: AgentConfiguration) -> dict:
        return await self.configuration_service.agent_dto(row)

    async def agent_page(
        self, subject, tenant_id, *, q="", page=1, page_size=25, status=None, sort="name", order="asc"
    ):
        return await self.configuration_service.agent_page(
            subject, tenant_id, q=q, page=page, page_size=page_size, status=status, sort=sort, order=order
        )

    async def configuration(self, subject: str, tenant_id: str) -> dict:
        return await self.configuration_service.configuration(subject, tenant_id)

    async def list_agents(self, subject: str, tenant_id: str) -> list[dict]:
        return await self.configuration_service.list_agents(subject, tenant_id)

    def provider_address(self, kind: str, address: str) -> str:
        return self.configuration_service.provider_address(kind, address)

    async def save_agent(
        self, subject: str, tenant_id: str, values: dict, agent_id: str | None = None
    ) -> dict:
        return await self.configuration_service.save_agent(subject, tenant_id, values, agent_id)

    async def save_provider(
        self, subject: str, tenant_id: str, values: dict, provider_id: str | None = None
    ) -> dict:
        return await self.configuration_service.save_provider(subject, tenant_id, values, provider_id)

    async def scoped(self, repository, tenant_id: str, resource_id: str, *, lock=False):
        return await self.configuration_service.scoped(repository, tenant_id, resource_id, lock=lock)

    async def validate_agent(self, subject: str, tenant_id: str, agent_id: str) -> dict:
        return await self.configuration_service.validate_agent(subject, tenant_id, agent_id)

    async def validate_provider(self, subject: str, tenant_id: str, provider_id: str) -> dict:
        return await self.configuration_service.validate_provider(subject, tenant_id, provider_id)

    async def validate_scope(
        self, subject: str, tenant_id: str, requested: dict, limit: dict | None = None
    ) -> dict:
        return await self.scope_policy.validate_scope(subject, tenant_id, requested, limit)

    async def result(self, subject: str, tenant_id: str, run_id: str, result_id: str) -> dict:
        run = await self.owned_run(subject, tenant_id, run_id, require_origin=False)
        rows = await self.results.find_all(id=result_id, run_id=run_id)
        if not rows or rows[0].kind not in {"search", "query", "schema", "lineage", "attachment"}:
            raise AccessDenied("Evidence is unavailable in this conversation", code="ACCESS_DENIED")
        for asset_id in rows[0].payload.get("asset_ids", []):
            await self.catalog.get(subject, tenant_id, asset_id)
        await self.origin_authority(subject, tenant_id, run, rows, include_run=False)
        return {"id": rows[0].id, "run_id": run_id, "kind": rows[0].kind, "data": rows[0].payload["data"]}
