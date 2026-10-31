# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from contextlib import nullcontext

from pyfly.container import Provider, service
from pyfly.data import transactional
from pyfly.kernel import ServiceUnavailableException
from pyfly.security.context import SecurityContext
from pyfly.security.context_holder import SecurityContextHolder

from koinon.assistants.audit_dtos import AnswerAudit, GenerationReceipt, PrivateFileReceipt
from koinon.assistants.lifecycle import timestamp
from koinon.assistants.memory.projections import MemoryOutputCapture
from koinon.assistants.service import AssistantService
from koinon.catalog.errors import AccessDenied
from koinon.evidence.dtos import SourceReference
from koinon.evidence.ports import SourceResolverPort
from koinon.organization_knowledge.runtime import snapshot_for_run
from koinon.tokens.repositories import PersonalTokenRepository


@service(name="assistants.answer_audits")
class AnswerAudits:
    def __init__(
        self,
        assistants: AssistantService,
        sources: Provider[SourceResolverPort | None],
        tokens: Provider[PersonalTokenRepository | None],
    ):
        self.assistants, self.sources, self.tokens = assistants, sources, tokens

    async def origin(self, subject, tenant_id, run, token_id):
        context = nullcontext()
        if token_id:
            repository = self.tokens.get()
            if repository is None or self.assistants.catalog.restriction is None:
                raise ServiceUnavailableException(
                    "Originating token checks are unavailable", code="TOKEN_AUTHORITY_UNAVAILABLE"
                )
            token = await repository.find_by_id(token_id)
            if (
                token is None
                or token.subject != subject
                or token.tenant_id != tenant_id
                or token.revoked_at is not None
                or token.expires_at <= timestamp()
            ):
                raise AccessDenied(
                    "The originating authority is no longer valid", code="EVIDENCE_UNAVAILABLE"
                )
            issuer, _, sub = subject.partition("|")
            context = SecurityContextHolder.using(
                SecurityContext(
                    user_id=sub, attributes={"iss": issuer, "sub": sub, "koinon_token_id": token_id}
                )
            )
        with context:
            await self.assistants.thread(subject, tenant_id, run.thread_id)
            await self.assistants.validate_scope(subject, tenant_id, run.scope)
            await self.assistants.authorize_results(subject, tenant_id, run.id)

    @transactional(read_only=True, read_from_primary=True)
    async def get(self, subject, tenant_id, run_id):
        run = await self.assistants.owned_run(subject, tenant_id, run_id, require_attachment_use=False)
        rows = sorted(
            await self.assistants.results.find_all(run_id=run.id), key=lambda row: (row.created_at, row.id)
        )
        rows = await self.assistants.active_results(run, rows)
        generation_rows = [row for row in rows if row.kind == "generation"]
        for token_id in {
            run.access_token_id,
            *(row.payload.get("origin_token_id") for row in rows),
        }:
            await self.origin(subject, tenant_id, run, token_id)
        generations = [GenerationReceipt.model_validate(row.payload["generation"]) for row in generation_rows]
        references, native_reads, attempts, private = {}, [], [], {}
        tools = None
        captured = []
        access = self.assistants._attachment_access()
        summaries = (
            {
                row.id: row
                for row in await access.summaries_for_message(
                    subject, tenant_id, run.thread_id, run.user_message_id
                )
            }
            if access
            else {}
        )
        for row in rows:
            payload = row.payload
            if row.kind in {"search", "schema", "query", "observation"}:
                manifest = payload.get("source_manifest")
                complete = (
                    isinstance(manifest, dict)
                    and manifest.get("version") == 1
                    and manifest.get("complete") is True
                )
                captured.append(complete)
                if isinstance(manifest, dict):
                    for value in manifest.get("sources", []):
                        source = SourceReference.model_validate(value)
                        references[source.id] = source
                native_reads.extend(payload.get("native_reads", []))
                attempts.extend(payload.get("sql_attempts", []))
                if payload.get("rlm_tools") is not None:
                    tools = [*(tools or []), *payload["rlm_tools"]]
            if row.kind == "attachment":
                values = payload.get("data", {}).get("attachments", [])
                captured.append(bool(values))
                for value in values:
                    summary = summaries.get(value["id"])
                    state = "unavailable"
                    if summary:
                        state = (
                            summary.status
                            if summary.status in {"expired", "deleted"}
                            else "available"
                            if summary.available
                            and summary.sha256 == value["sha256"]
                            and summary.revision == value["revision"]
                            else "changed"
                        )
                    private[value["id"]] = PrivateFileReceipt(
                        id=value["id"],
                        filename=value["filename"],
                        media_type=value["media_type"],
                        sha256=value["sha256"],
                        used_revision=value["revision"],
                        availability=state,
                    )
        sources = tuple(references.values())
        if sources:
            resolver = self.sources.get()
            if resolver is None:
                raise ServiceUnavailableException(
                    "Source verification is unavailable", code="SOURCE_RESOLVER_UNAVAILABLE"
                )
            resolved = await resolver.resolve(subject, tenant_id, sources)
            if len(resolved) != len(sources) or {row.id for row in resolved} != {row.id for row in sources}:
                raise AccessDenied("Source verification is incomplete", code="EVIDENCE_UNAVAILABLE")
            indexed = {row.id: row for row in resolved}
            sources = tuple(
                row.model_copy(
                    update={
                        "availability": indexed[row.id].availability,
                        "current_revision": indexed[row.id].current_revision,
                    }
                )
                for row in sources
            )
        for token_id in {
            run.access_token_id,
            *(row.payload.get("origin_token_id") for row in rows),
        }:
            await self.origin(subject, tenant_id, run, token_id)
        memory_access = self.assistants.memory.get() if self.assistants.memory is not None else None
        memory = (
            await memory_access.authorize(
                subject, tenant_id, run.id, captures=(MemoryOutputCapture(run.id, "sequence", run.sequence),)
            )
            if memory_access is not None
            else None
        )
        return AnswerAudit(
            run_id=run.id,
            memory=memory,
            knowledge_settings_snapshot=snapshot_for_run(run),
            provenance_status="recorded"
            if generations or references or private or native_reads or attempts
            else "not_recorded",
            source_provenance_complete=all(captured) if captured else None,
            generations=generations,
            sources=list(sources),
            private_files=list(private.values()),
            native_reads=native_reads,
            sql_attempts=attempts,
            rlm_tools=tools,
        ).model_dump(mode="json", by_alias=True)
