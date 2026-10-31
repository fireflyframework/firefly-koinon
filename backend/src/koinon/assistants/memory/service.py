# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Generation-bound personal context with immutable, flattened authorization dependencies."""

import json
from collections import OrderedDict
from dataclasses import asdict, replace

from pydantic_ai.messages import ModelRequest, ModelResponse, TextPart, UserPromptPart
from pyfly.agentic.memory import ConversationMemory
from pyfly.container import Provider, service
from pyfly.data.relational.sqlalchemy import transactional
from pyfly.data.transaction import Isolation, Propagation
from pyfly.kernel import ConflictException, InvalidRequestException
from pyfly.security.context_holder import SecurityContextHolder

from koinon import __version__
from koinon.assistants.context_budget import ConservativeTokenEstimator
from koinon.assistants.lifecycle import identifier, timestamp
from koinon.assistants.memory.authority_mappers import MemoryAuthorityStamp
from koinon.assistants.memory.authority_repository import ChatMemoryAuthorityRepository
from koinon.assistants.memory.dtos import MemoryDependency, MemoryManifest, MemoryReceipt, MemoryResultPin
from koinon.assistants.memory.entities import ChatMemoryManifest
from koinon.assistants.memory.mappers import digest, historical_text, normalized_scope, receipt, text_digest
from koinon.assistants.memory.ports import ChatMemoryAccess
from koinon.assistants.memory.projections import MemoryCurrentEvidence
from koinon.assistants.memory.repositories import ChatMemoryRepository
from koinon.assistants.service import AssistantService
from koinon.assistants.settings import AssistantSettings
from koinon.catalog.errors import AccessDenied
from koinon.catalog.service import ROLE_PERMISSIONS, CatalogService
from koinon.evidence.dtos import SourceReference
from koinon.evidence.ports import SourceResolverPort
from koinon.organization_chat.memory_policy import effective_memory_policy
from koinon.security.authority import PRIMARY_POLICY_UNIT


def unavailable():
    return AccessDenied(
        "Personal conversation memory changed or is no longer available", code="MEMORY_UNAVAILABLE"
    )


@service(name="assistants.personal_memory")
class PersonalConversationMemory(ChatMemoryAccess):
    def __init__(
        self,
        repository: ChatMemoryRepository,
        authority: ChatMemoryAuthorityRepository,
        assistants: Provider[AssistantService],
        catalog: CatalogService,
        settings: AssistantSettings,
        sources: Provider[SourceResolverPort | None],
    ):
        self.repository, self.authority_repository = repository, authority
        self.assistants, self.catalog, self.settings, self.sources = assistants, catalog, settings, sources
        self._current_admissions: OrderedDict[tuple[str, str, str | None, str], None] = OrderedDict()

    def deployment_digest(self):
        return digest(
            [
                __version__,
                1,
                self.settings.max_history_messages,
                self.settings.max_history_tokens,
                {key: sorted(value) for key, value in ROLE_PERMISSIONS.items()},
            ]
        )

    async def context(self, subject, tenant_id, thread_id):
        current = await self.repository.context(subject, tenant_id, thread_id)
        if current is None or current[0].deleted_at is not None or current[0].archived_at is not None:
            raise unavailable()
        thread, folder, organization = current
        if thread.folder_id and (
            folder is None or folder.subject != subject or folder.tenant_id != tenant_id
        ):
            raise unavailable()
        policy = effective_memory_policy(
            organization.memory_policy_json if organization else None, self.settings
        )
        return thread, folder, policy, organization.revision if organization else 0

    async def observe(self, value: MemoryManifest, asset_ids: tuple[str, ...]) -> MemoryAuthorityStamp:
        context = SecurityContextHolder.get_context()
        token_id = context.attributes.get("koinon_token_id") if context else None
        stamps = await self.authority_repository.observe_many(
            (value,),
            self.catalog.effective_membership_rows(),
            token_id,
            self.deployment_digest(),
        )
        return stamps[value.generation_id]

    @staticmethod
    def decode(row: ChatMemoryManifest) -> MemoryManifest:
        if digest(row.manifest_json) != row.manifest_sha256:
            raise unavailable()
        value = MemoryManifest.model_validate_json(json.dumps(row.manifest_json))
        if (
            value.generation_id,
            value.run_id,
            value.tenant_id,
            value.subject,
            value.thread_id,
            value.folder_id,
            value.scope_sha256,
            value.policy_version,
        ) != (
            row.generation_id,
            row.run_id,
            row.tenant_id,
            row.subject,
            row.thread_id,
            row.folder_id,
            row.scope_sha256,
            row.policy_version,
        ):
            raise unavailable()
        return value

    async def result_window(self, run):
        rows = await self.repository.result_window(run.id)
        return None if rows is None else await self.assistants.get().active_results(run, rows)

    async def assets(self, references, tenant_id) -> tuple[str, ...]:
        assistants = self.assistants.get()
        ids = set()
        for ref in references:
            await assistants.scoped(assistants.runs, tenant_id, ref.run_id)
            for result in await self.repository.pinned_results(tuple(pin.id for pin in ref.result_pins)):
                ids.update(result.payload.get("asset_ids", []))
                ids.update(
                    source["asset_id"]
                    for source in result.payload.get("source_manifest", {}).get("sources", [])
                )
        if len(ids) > 128:
            raise AccessDenied("Narrow personal memory to fewer sources", code="MEMORY_SCOPE_TOO_WIDE")
        return tuple(sorted(ids))

    @transactional(
        datasource="primary", propagation=Propagation.REQUIRED, read_only=True, read_from_primary=True
    )
    async def validate_sources(self, value: MemoryManifest) -> None:
        assistants = self.assistants.get()
        thread, folder, policy, revision = await self.context(value.subject, value.tenant_id, value.thread_id)
        if (
            thread.folder_id != value.folder_id
            or (folder.revision if folder else None) != value.folder_revision
            or revision != value.organization_policy_revision
            or policy != value.effective_policy
        ):
            raise unavailable()
        if value.mode == "personal_project" and (
            folder is None or not folder.memory_enabled or not policy.allow_project_memory
        ):
            raise unavailable()
        await assistants.validate_scope(
            value.subject, value.tenant_id, (await assistants.runs.find_by_id(value.run_id)).scope
        )
        selected = {
            item.run_id: item
            for item in await self.repository.selected(
                value.subject, value.tenant_id, tuple(ref.run_id for ref in value.dependencies)
            )
        }
        for ref in value.dependencies:
            candidate = selected.get(ref.run_id)
            if (
                candidate is None
                or candidate.thread_id != ref.thread_id
                or normalized_scope(candidate.scope)
                != normalized_scope((await assistants.runs.find_by_id(value.run_id)).scope)
            ):
                raise unavailable()
            if candidate.thread_id != value.thread_id and (
                value.mode != "personal_project"
                or candidate.folder_id != value.folder_id
                or candidate.private_thread
            ):
                raise unavailable()
            if (
                candidate.user_message_id,
                text_digest(candidate.user_text),
                candidate.answer_message_id,
                text_digest(candidate.answer_text),
                digest(normalized_scope(candidate.scope)),
            ) != (
                ref.user_message_id,
                ref.user_sha256,
                ref.answer_message_id,
                ref.answer_sha256,
                ref.scope_sha256,
            ):
                raise unavailable()
            await assistants.validate_scope(value.subject, value.tenant_id, candidate.scope)
            run = await assistants.scoped(assistants.runs, value.tenant_id, ref.run_id)
            rows = await self.result_window(run)
            if rows is None:
                raise unavailable()
            await assistants.authorize_results(
                value.subject, value.tenant_id, ref.run_id, require_memory=False, result_rows=rows
            )
            if (
                len(rows) > 128
                or tuple(
                    MemoryResultPin(id=row.id, sha256=digest({"kind": row.kind, "payload": row.payload}))
                    for row in sorted(rows, key=lambda item: item.id)
                )
                != ref.result_pins
            ):
                raise unavailable()
            generation = await self.repository.generation(ref.run_id)
            if (generation.id if generation else None) != ref.generation_id:
                raise unavailable()
            access = assistants._attachment_access()
            refs = (
                await access.for_run(value.subject, value.tenant_id, ref.thread_id, ref.run_id)
                if access
                else ()
            )
            if digest([asdict(item) for item in refs]) != ref.attachment_sha256:
                raise unavailable()
            if ref.source_manifest_sha256 and ref.answer_included:
                source = await self.repository.for_generation(ref.generation_id)
                if source is None or source.manifest_sha256 != ref.source_manifest_sha256:
                    raise unavailable()
            if ref.answer_included and not refs:
                evidence_rows = [
                    row for row in rows if row.kind in {"search", "query", "schema", "observation"}
                ]
                if not evidence_rows or any(
                    not isinstance(row.payload.get("source_manifest"), dict)
                    or row.payload["source_manifest"].get("complete") is not True
                    for row in evidence_rows
                ):
                    raise unavailable()
                references = tuple(
                    {
                        source["id"]: SourceReference.model_validate(source)
                        for row in evidence_rows
                        for source in row.payload["source_manifest"].get("sources", [])
                    }.values()
                )
                resolver = self.sources.get()
                if not references or resolver is None:
                    raise unavailable()
                verified = await resolver.resolve(value.subject, value.tenant_id, references)
                if {item.id for item in verified} != {item.id for item in references} or any(
                    item.availability == "unverified" for item in verified
                ):
                    raise unavailable()

    async def answer_proven(self, subject, tenant_id, rows, refs) -> bool:
        if refs:
            captured = [
                item
                for row in rows
                if row.kind == "attachment"
                for item in row.payload.get("data", {}).get("attachments", [])
            ]
            return bool(captured) and {
                (item["id"], item["sha256"], item["revision"]) for item in captured
            } == {(item.id, item.sha256, item.revision) for item in refs}
        evidence = [row for row in rows if row.kind in {"search", "schema", "query", "observation"}]
        if not evidence or any(
            not isinstance(row.payload.get("source_manifest"), dict)
            or row.payload["source_manifest"].get("complete") is not True
            for row in evidence
        ):
            return False
        sources = tuple(
            {
                item["id"]: SourceReference.model_validate(item)
                for row in evidence
                for item in row.payload["source_manifest"].get("sources", [])
            }.values()
        )
        resolver = self.sources.get()
        if not sources or resolver is None:
            return False
        try:
            resolved = await resolver.resolve(subject, tenant_id, sources)
        except (AccessDenied, InvalidRequestException, ConflictException):
            return False
        return {item.id for item in resolved} == {item.id for item in sources} and all(
            item.availability != "unverified" for item in resolved
        )

    async def authorize(self, subject: str, tenant_id: str, run_id: str, *, captures=()):
        return (await self.authorize_many(subject, tenant_id, (run_id,), captures=captures))[run_id]

    async def query_context(self, subject: str, tenant_id: str, run_id: str) -> dict:
        generation = await self.repository.generation(run_id)
        if generation is None:
            raise unavailable()
        row = await self.repository.for_generation(generation.id)
        if row is not None:
            value = self.decode(row)
            if (value.subject, value.tenant_id, value.run_id) != (subject, tenant_id, run_id):
                raise unavailable()
        return {
            "kind": "koinon_generation",
            "subject": subject,
            "tenant_id": tenant_id,
            "binding": {
                "run_id": run_id,
                "generation_id": generation.id,
                "manifest_sha256": row.manifest_sha256 if row else None,
                "results": [],
            },
        }

    async def inheritance_valid(self, value, target_thread_id, folder_id, project) -> bool:
        # Reuse exactly the sealed dependencies, never recursively reconstruct earlier manifests.
        if not value.dependencies:
            return True
        before = await self.observe(value, value.asset_ids)
        if any(state != "available" for state in before.availability.values()):
            return False
        states = await self.repository.availability(value.dependencies, folder_id=folder_id)
        indexed = {thread.id: thread for thread, _ in states}
        for reference in value.dependencies:
            thread = indexed.get(reference.thread_id)
            if thread is None or thread.subject != value.subject or thread.tenant_id != value.tenant_id:
                return False
            if thread.deleted_at is not None or thread.archived_at is not None:
                return False
            if project and thread.folder_id != folder_id or not project and thread.id != target_thread_id:
                return False
        try:
            authorized = await self.authorize_fixed(
                value.subject, value.tenant_id, (value,), (), historical=(value.generation_id,)
            )
        except (AccessDenied, InvalidRequestException, ConflictException):
            return False
        after = await self.observe(value, value.asset_ids)
        return before == authorized[value.generation_id] == after and all(
            state == "available" for state in after.availability.values()
        )

    async def build(self, run, *, generation_id=None, token_budget=None, attachment_refs=()):
        assistants = self.assistants.get()
        thread = await assistants.threads.find_by_id(run.thread_id)
        if thread is None or thread.tenant_id != run.tenant_id:
            raise unavailable()
        subject = thread.subject
        thread, folder, policy, revision = await self.context(subject, run.tenant_id, run.thread_id)
        budget = min(
            policy.max_history_tokens, token_budget if token_budget is not None else policy.max_history_tokens
        )
        project = bool(
            folder
            and folder.memory_enabled
            and policy.allow_project_memory
            and policy.max_project_memory_messages > 0
            and budget > 0
            and policy.max_history_messages > 0
            and not attachment_refs
        )
        candidates = (
            ()
            if budget <= 0 or policy.max_history_messages == 0
            else await self.repository.candidates(
                subject,
                run.tenant_id,
                run,
                folder_id=folder.id if folder else None,
                project_enabled=project,
                limit=80,
            )
        )
        selected = []
        dependencies = {}
        project_turns = 0
        access = assistants._attachment_access()
        for candidate in candidates:
            if len(selected) >= min(20, policy.max_history_messages // 2):
                break
            cross = candidate.thread_id != thread.id
            if normalized_scope(candidate.scope) != normalized_scope(run.scope) or (
                cross and candidate.private_thread
            ):
                continue
            if cross and project_turns >= policy.max_project_memory_messages // 2:
                continue
            try:
                await assistants.validate_scope(subject, run.tenant_id, candidate.scope)
                try:
                    refs = (
                        await access.for_run(subject, run.tenant_id, candidate.thread_id, candidate.run_id)
                        if access
                        else ()
                    )
                except (AccessDenied, InvalidRequestException, ConflictException):
                    continue
                if refs != attachment_refs or candidate.private_thread and access is None:
                    continue
                old = await assistants.scoped(assistants.runs, run.tenant_id, candidate.run_id)
                rows = await self.result_window(old)
                if rows is None:
                    continue
                await assistants.authorize_results(
                    subject, run.tenant_id, candidate.run_id, require_memory=False, result_rows=rows
                )
                generation = await self.repository.generation(candidate.run_id)
                source_row = await self.repository.for_generation(generation.id) if generation else None
                inherited = self.decode(source_row) if source_row else None
                included = bool(
                    inherited
                    and candidate.answer_policy.get("outcome") == "grounded"
                    and await self.answer_proven(subject, run.tenant_id, rows, refs)
                )
                extra = tuple(inherited.dependencies) if inherited is not None and included else ()
                if (
                    inherited
                    and included
                    and (
                        inherited.scope_sha256 != digest(normalized_scope(run.scope))
                        or not await self.inheritance_valid(
                            inherited, run.thread_id, folder.id if folder else None, project
                        )
                    )
                ):
                    included, extra = False, ()
                if len(set(dependencies) | {item.run_id for item in extra} | {candidate.run_id}) > 128:
                    included, extra = False, ()
                ref = MemoryDependency(
                    run_id=candidate.run_id,
                    generation_id=generation.id if generation else None,
                    thread_id=candidate.thread_id,
                    conversation_title=candidate.conversation_title,
                    user_created_at=candidate.user_created_at,
                    user_message_id=candidate.user_message_id,
                    user_sha256=text_digest(candidate.user_text),
                    answer_message_id=candidate.answer_message_id,
                    answer_sha256=text_digest(candidate.answer_text),
                    answer_included=included,
                    scope_sha256=digest(normalized_scope(candidate.scope)),
                    source_manifest_sha256=source_row.manifest_sha256 if source_row else None,
                    result_pins=tuple(
                        MemoryResultPin(
                            id=item.id, sha256=digest({"kind": item.kind, "payload": item.payload})
                        )
                        for item in sorted(rows, key=lambda item: item.id)
                    ),
                    attachment_sha256=digest([asdict(item) for item in refs]),
                    origin_token_id=old.access_token_id,
                )
                prospective = {**dependencies, **{item.run_id: item for item in extra}, ref.run_id: ref}
                if not await self.repository.pins_fit(
                    tuple(sorted({pin.id for item in prospective.values() for pin in item.result_pins})),
                    message_ids=tuple(
                        sorted(
                            {
                                key
                                for item in prospective.values()
                                for key in (item.user_message_id, item.answer_message_id)
                            }
                        )
                    ),
                ):
                    continue
                selected.append((candidate, ref, extra))
                dependencies.update({item.run_id: item for item in extra})
                dependencies[ref.run_id] = ref
                project_turns += cross
            except (AccessDenied, InvalidRequestException, ConflictException):
                if not cross:
                    raise
                continue
        memory = ConversationMemory(max_tokens=max(0, budget), estimator=ConservativeTokenEstimator())
        entries = {}
        for candidate, ref, extra in reversed(selected):
            user_text, answer_text = historical_text(ref, candidate.user_text, candidate.answer_text)
            messages = [
                ModelRequest(parts=[UserPromptPart(user_text)]),
                ModelResponse(parts=[TextPart(answer_text)]),
            ]
            turn = memory.add_turn(
                run.thread_id, user_text, answer_text, messages, metadata={"run_id": ref.run_id}
            )
            entries[ref.run_id] = (ref, extra, turn)
        messages = memory.get_message_history(run.thread_id)
        retained = [
            (ref, extra, turn)
            for ref, extra, turn in entries.values()
            if all(message in messages for message in turn.raw_messages)
        ]
        flattened = {}
        for ref, extra, _ in retained:
            flattened.update({item.run_id: item for item in extra})
            flattened[ref.run_id] = ref
        if generation_id is not None:
            value = MemoryManifest(
                generation_id=generation_id,
                run_id=run.id,
                tenant_id=run.tenant_id,
                subject=subject,
                thread_id=run.thread_id,
                mode="personal_project" if project else "current_thread",
                folder_id=thread.folder_id,
                folder_revision=folder.revision if folder else None,
                organization_policy_revision=revision,
                effective_policy=policy,
                scope_sha256=digest(normalized_scope(run.scope)),
                turns=tuple(item[0] for item in retained),
                dependencies=tuple(flattened[key] for key in sorted(flattened)),
                input_sha256=digest([(turn.user_prompt, turn.assistant_response) for _, _, turn in retained]),
                private_context=bool(attachment_refs),
                origin_token_id=run.access_token_id,
                knowledge_scope=normalized_scope(run.scope),
                created_at=timestamp(),
            )
            assets = await self.assets(value.dependencies, value.tenant_id)
            value = value.model_copy(update={"asset_ids": assets})
            before = await self.observe(value, assets)
            authorized = await self.authorize_fixed(
                value.subject, value.tenant_id, (value,), (), checks=(value.generation_id,)
            )
            after = await self.observe(value, assets)
            if before != authorized[value.generation_id] or authorized[value.generation_id] != after:
                raise unavailable()
            value = value.model_copy(
                update={"authority_sha256": after.origin_sha256 if value.turns else None}
            )
            generation = await assistants.results.find_by_id(generation_id)
            if generation is None or generation.run_id != run.id or generation.kind != "generation":
                raise unavailable()
            await self.repository.insert_manifest(
                ChatMemoryManifest(
                    id=identifier(),
                    generation_id=generation_id,
                    run_id=run.id,
                    tenant_id=run.tenant_id,
                    subject=subject,
                    thread_id=run.thread_id,
                    folder_id=value.folder_id,
                    policy_version=1,
                    start_sequence=generation.payload["generation"]["start_sequence"],
                    scope_sha256=value.scope_sha256,
                    manifest_json=value.model_dump(mode="json"),
                    manifest_sha256=digest(value.model_dump(mode="json")),
                    created_at=value.created_at,
                )
            )
        return messages

    @transactional(
        datasource="primary", propagation=Propagation.REQUIRED, read_only=True, read_from_primary=True
    )
    async def validate_replay(self, value: MemoryManifest) -> None:
        """Read stored answers under current source bounds, independent of future-memory consent."""
        from types import SimpleNamespace

        assistants = self.assistants.get()
        await assistants.validate_scope(value.subject, value.tenant_id, value.knowledge_scope)
        identifiers = tuple(sorted({pin.id for ref in value.dependencies for pin in ref.result_pins}))
        if len(identifiers) > 1024:
            raise AccessDenied("Request a smaller conversation page", code="MEMORY_PAGE_TOO_WIDE")
        indexed = {row.id: row for row in await self.repository.pinned_results(identifiers)}
        for ref in value.dependencies:
            rows = []
            for pin in ref.result_pins:
                result = indexed.get(pin.id)
                if (
                    result is None
                    or result.run_id != ref.run_id
                    or digest({"kind": result.kind, "payload": result.payload}) != pin.sha256
                ):
                    raise unavailable()
                rows.append(result)
            origin = SimpleNamespace(access_token_id=ref.origin_token_id, scope=value.knowledge_scope)
            await assistants.origin_authority(value.subject, value.tenant_id, origin, rows)
            for row in rows:
                for asset_id in row.payload.get("asset_ids", []):
                    await self.catalog.get(value.subject, value.tenant_id, asset_id)
            sources = tuple(
                {
                    source["id"]: SourceReference.model_validate(source)
                    for row in rows
                    for source in row.payload.get("source_manifest", {}).get("sources", [])
                }.values()
            )
            if sources:
                resolver = self.sources.get()
                if resolver is None:
                    raise unavailable()
                resolved = await resolver.resolve(value.subject, value.tenant_id, sources)
                if {item.id for item in resolved} != {item.id for item in sources} or any(
                    item.availability == "unverified" for item in resolved
                ):
                    raise unavailable()

    @transactional(
        datasource="primary", propagation=Propagation.REQUIRED, read_only=True, read_from_primary=True
    )
    async def validate_result_current(self, subject, tenant_id, evidence):
        from types import SimpleNamespace

        assistants = self.assistants.get()
        await assistants.thread(subject, tenant_id, evidence.thread_id)
        await assistants.validate_scope(subject, tenant_id, evidence.scope)
        for row in evidence.results:
            for asset_id in row.payload.get("asset_ids", []):
                await self.catalog.get(subject, tenant_id, asset_id)
        origin = SimpleNamespace(access_token_id=evidence.origin_token_id, scope=evidence.scope)
        await assistants.origin_authority(subject, tenant_id, origin, evidence.results, include_run=False)

    async def authorize_result(self, subject, tenant_id, run_id, result_id, expected_sha256):
        from koinon.assistants.memory.projections import MemoryCurrentResult

        record = await self.repository.result_context(subject, tenant_id, run_id, result_id)
        if record is None:
            raise unavailable()
        scope, origin_token_id, thread_id, result = record
        if digest({"kind": result.kind, "payload": result.payload}) != expected_sha256:
            raise unavailable()
        generation_id = result.payload.get("generation_id")
        value = None
        historical = True
        if generation_id is not None:
            generation = await self.assistants.get().results.find_by_id(generation_id)
            if generation is None or generation.run_id != run_id or generation.kind != "generation":
                raise unavailable()
            row = await self.repository.for_generation(generation_id)
            if row is not None:
                value = self.decode(row)
                if (value.subject, value.tenant_id, value.run_id) != (subject, tenant_id, run_id):
                    raise unavailable()
                scope = value.knowledge_scope
                active = await self.repository.generation(run_id)
                historical = (
                    active is None
                    or active.id != generation_id
                    or generation.payload["generation"]["status"] != "started"
                )
        payload = {
            "asset_ids": result.payload.get("asset_ids", []),
            "origin_token_id": result.payload.get("origin_token_id", origin_token_id),
        }
        fixed = MemoryCurrentResult(result.id, run_id, result.kind, payload, result.created_at)
        assets = set(payload["asset_ids"]) | set(scope.get("asset_ids", []))
        assets.update(scope[key] for key in ("workspace_id", "project_id", "collection_id") if scope.get(key))
        evidence = (
            MemoryCurrentEvidence(
                run_id,
                thread_id,
                subject,
                tenant_id,
                scope,
                payload["origin_token_id"],
                (fixed,),
                tuple(sorted(assets)),
            ),
        )
        context = SecurityContextHolder.get_context()
        caller = context.attributes.get("koinon_token_id") if context else None
        values = (value,) if value else ()
        before = await self.authority_repository.observe_many(
            values, self.catalog.effective_membership_rows(), caller, self.deployment_digest(), evidence
        )
        if value is not None and value.turns:
            stamp = before[value.generation_id]
            if not historical and stamp.origin_sha256 != value.authority_sha256:
                raise unavailable()
        authorized = await self.authorize_fixed(
            subject,
            tenant_id,
            values,
            evidence,
            historical=(value.generation_id,) if value is not None and historical else (),
            result=True,
        )
        after = await self.authority_repository.observe_many(
            values, self.catalog.effective_membership_rows(), caller, self.deployment_digest(), evidence
        )
        if before != authorized or authorized != after:
            raise unavailable()

    @transactional(
        name=PRIMARY_POLICY_UNIT,
        datasource="primary",
        propagation=Propagation.REQUIRES_NEW,
        isolation=Isolation.SERIALIZABLE,
        read_only=True,
        read_from_primary=True,
    )
    async def authorize_fixed(
        self,
        subject,
        tenant_id,
        values,
        evidence,
        *,
        historical=(),
        result=False,
        validate=None,
        captures=(),
        observation=None,
        checks=None,
    ):
        # Every policy participant joins this fresh primary Session; a replica or an
        # independent transaction must not split current and remembered authority.
        context = SecurityContextHolder.get_context()
        caller = context.attributes.get("koinon_token_id") if context else None

        async def observe():
            return await self.authority_repository.observe_bound(
                values,
                self.catalog.effective_membership_rows(),
                caller,
                self.deployment_digest(),
                evidence,
                captures,
                **(observation or {}),
            )

        if validate is not None:
            await validate()
        else:
            if result:
                for item in evidence:
                    await self.validate_result_current(subject, tenant_id, item)
            else:
                await self.validate_current(subject, tenant_id, evidence)
            for value in values:
                if (checks is None and value.turns) or (checks is not None and value.generation_id in checks):
                    if value.generation_id in historical:
                        await self.validate_replay(value)
                    else:
                        await self.validate_sources(value)
        return await observe()

    @transactional(
        datasource="primary", propagation=Propagation.REQUIRED, read_only=True, read_from_primary=True
    )
    async def validate_current(self, subject, tenant_id, values):
        assistants = self.assistants.get()
        for value in values:
            await assistants.thread(subject, tenant_id, value.thread_id)
            await assistants.validate_scope(subject, tenant_id, value.scope)
            await assistants.authorize_results(
                subject, tenant_id, value.run_id, require_memory=False, result_rows=value.results
            )

    async def current_evidence(self, subject, tenant_id, identifiers):
        assistants = self.assistants.get()
        values = await self.repository.current_evidence(subject, tenant_id, identifiers)
        output = []
        for value in values:
            run = await assistants.scoped(assistants.runs, tenant_id, value.run_id)
            rows = tuple(await assistants.active_results(run, value.results))
            assets = set(value.scope.get("asset_ids", []))
            assets.update(
                value.scope[key]
                for key in ("workspace_id", "project_id", "collection_id")
                if value.scope.get(key)
            )
            assets.update(key for row in rows for key in row.payload.get("asset_ids", []))
            output.append(replace(value, results=rows, asset_ids=tuple(sorted(assets))))
        return tuple(output)

    async def authorize_many(self, subject: str, tenant_id: str, run_ids: tuple[str, ...], *, captures=()):
        identifiers = tuple(dict.fromkeys(run_ids))
        if not identifiers:
            return {}
        if len(identifiers) > 51:
            raise AccessDenied("Request a smaller conversation page", code="MEMORY_PAGE_TOO_WIDE")
        rows = await self.repository.active_manifests(subject, tenant_id, identifiers)
        if {row[0] for row in rows} != set(identifiers):
            raise unavailable()
        output: dict[str, MemoryReceipt | None] = {key: None for key in identifiers}
        values, stored = [], {}
        for run_id, status, generation, row in rows:
            if row is None:
                continue
            value = self.decode(row)
            if (value.subject, value.tenant_id, value.run_id) != (subject, tenant_id, run_id):
                raise unavailable()
            historical = (
                status in {"completed", "failed", "cancelled"}
                and generation.payload["generation"]["status"] != "started"
            )
            values.append(value)
            stored[value.generation_id] = (row.manifest_sha256, historical)
        evidence = await self.current_evidence(subject, tenant_id, identifiers)
        context = SecurityContextHolder.get_context()
        caller = context.attributes.get("koinon_token_id") if context else None
        before = await self.authority_repository.observe_many(
            tuple(values),
            self.catalog.effective_membership_rows(),
            caller,
            self.deployment_digest(),
            evidence,
            captures,
        )
        current_sha256 = before["__current__"].current_sha256
        if current_sha256 is None:
            raise unavailable()
        admission = (subject, tenant_id, caller, current_sha256)
        admitted = admission in self._current_admissions
        validations, historical_ids = [], []
        for value in values:
            _, historical = stored[value.generation_id]
            stamp = before[value.generation_id]
            different_reader = caller is not None and caller != value.origin_token_id
            if value.turns and (stamp.origin_sha256 != value.authority_sha256 or different_reader):
                if not historical and stamp.origin_sha256 != value.authority_sha256:
                    raise unavailable()
                validations.append(value)
                if historical:
                    historical_ids.append(value.generation_id)
        changed = not admitted or bool(validations)
        if changed:
            authorized = await self.authorize_fixed(
                subject,
                tenant_id,
                tuple(values),
                evidence,
                historical=tuple(historical_ids),
                captures=captures,
                checks=tuple(value.generation_id for value in validations),
            )
            if authorized != before:
                raise unavailable()
        current = before
        if changed:
            current = await self.authority_repository.observe_many(
                tuple(values),
                self.catalog.effective_membership_rows(),
                caller,
                self.deployment_digest(),
                evidence,
                captures,
            )
            if current["__current__"].current_sha256 != before["__current__"].current_sha256:
                raise unavailable()
            if any(
                current[key].origin_sha256 != before[key].origin_sha256
                or current[key].caller_sha256 != before[key].caller_sha256
                for key in current
            ):
                raise unavailable()
        # A memo hit still requires a fresh observation of every authority input.
        self._current_admissions[admission] = None
        self._current_admissions.move_to_end(admission)
        if len(self._current_admissions) > 128:
            self._current_admissions.popitem(last=False)
        # No awaited work after this whole-page cut: captured labels and hashes remain immutable.
        for value in values:
            sha256, historical = stored[value.generation_id]
            output[value.run_id] = receipt(
                value,
                sha256,
                historical=historical,
                availability=current[value.generation_id].availability if historical else None,
            )
        return output
