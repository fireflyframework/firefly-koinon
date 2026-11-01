# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Owner-selected immutable text snapshots; historical provenance is never guessed."""

import hashlib
import json

from pyfly.container import Provider, service
from pyfly.data import transactional
from pyfly.kernel import InvalidRequestException, ServiceUnavailableException
from pyfly.security.context import SecurityContext
from pyfly.security.context_holder import SecurityContextHolder

from koinon.assistants.lifecycle import timestamp
from koinon.assistants.memory.egress import MemoryEgress
from koinon.assistants.memory.egress_dtos import MemoryConversationSnapshot
from koinon.assistants.memory.projections import MemoryOutputCapture
from koinon.assistants.service import AssistantService
from koinon.catalog.errors import AccessDenied
from koinon.evidence.dtos import ConversationMessage, ConversationSnapshot, Presentation, SourceReference
from koinon.evidence.ports import ConversationOutputPort, ConversationSnapshotPort
from koinon.tokens.repositories import PersonalTokenRepository


def digest(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


@service(name="assistants.snapshots")
class ConversationSnapshots(ConversationSnapshotPort, ConversationOutputPort):
    def __init__(
        self,
        assistants: AssistantService,
        tokens: Provider[PersonalTokenRepository | None],
        egress: Provider[MemoryEgress | None] | None = None,
    ):
        self.assistants, self.tokens = assistants, tokens
        self.egress = egress

    @transactional(read_only=True, read_from_primary=True)
    async def authorize_output(
        self,
        subject: str,
        tenant_id: str,
        thread_id: str,
        message_ids: list[str],
        *,
        snapshot: ConversationSnapshot | None = None,
    ) -> None:
        issuer, _, sub = subject.partition("|")
        # The caller separately checks the transfer reader. This port checks the recorded owner
        # and originating run tokens without treating the recipient's token as the owner's token.
        with SecurityContextHolder.using(
            SecurityContext(user_id=sub, attributes={"iss": issuer, "sub": sub})
        ):
            await self._authorize_output_owner(subject, tenant_id, thread_id, message_ids, snapshot=snapshot)

    async def _authorize_output_owner(self, subject, tenant_id, thread_id, message_ids, *, snapshot):
        from koinon.answers.receipts import legacy_notice, verified_release

        if not 1 <= len(message_ids) <= 200 or len(set(message_ids)) != len(message_ids):
            raise AccessDenied("Conversation output is unavailable", code="EVIDENCE_RELEASE_REQUIRED")
        await self.assistants.thread(subject, tenant_id, thread_id)
        if snapshot is not None and (
            snapshot.thread_id != thread_id
            or snapshot.tenant_id != tenant_id
            or snapshot.owner_subject != subject
            or {message.id for message in snapshot.messages} != set(message_ids)
        ):
            raise AccessDenied("Conversation output changed", code="EVIDENCE_RELEASE_REQUIRED")
        rows = await self.assistants.message_repository.snapshot_messages(thread_id, message_ids)
        if {message.id for message, _ in rows} != set(message_ids):
            raise AccessDenied("Conversation output is unavailable", code="EVIDENCE_RELEASE_REQUIRED")
        saved = {message.id: message for message in snapshot.messages} if snapshot else {}
        for message, run in rows:
            selected = saved.get(message.id)
            if selected is not None and selected.role != message.role:
                raise AccessDenied("Conversation output changed", code="EVIDENCE_RELEASE_REQUIRED")
            if message.role == "user":
                if selected is not None and selected.text != message.text:
                    raise AccessDenied("Conversation output changed", code="EVIDENCE_RELEASE_REQUIRED")
                continue
            if message.role != "assistant" or run is None:
                raise AccessDenied("Conversation output is unavailable", code="EVIDENCE_RELEASE_REQUIRED")
            await self._origin(subject, tenant_id, run)
            release = verified_release(message, await self.assistants.active_results(run))
            masked = (
                selected is not None
                and selected.text in {legacy_notice("en"), legacy_notice("es")}
                and not selected.source_ids
                and not selected.result_ids
            )
            if release is None:
                if masked:
                    continue
                raise AccessDenied(
                    "Generate this response again from verifiable sources before using it",
                    code="EVIDENCE_RELEASE_REQUIRED",
                )
            if selected is not None and (
                selected.text != message.text
                or set(selected.result_ids) != {pin.id for pin in release.result_pins}
                or set(selected.source_ids) != {source.id for source in release.source_refs}
            ):
                raise AccessDenied("Conversation output changed", code="EVIDENCE_RELEASE_REQUIRED")

    async def _origin(self, subject, tenant_id, run):
        await self.assistants.validate_scope(subject, tenant_id, run.scope)
        await self.assistants.authorize_results(subject, tenant_id, run.id)
        if not run.access_token_id:
            return
        repository = self.tokens.get()
        if repository is None:
            raise ServiceUnavailableException(
                "Originating token validation is unavailable", code="TOKEN_AUTHORITY_UNAVAILABLE"
            )
        token = await repository.find_by_id(run.access_token_id)
        if (
            token is None
            or token.subject != subject
            or token.tenant_id != tenant_id
            or token.revoked_at is not None
            or token.expires_at <= timestamp()
        ):
            raise AccessDenied("The originating authority is no longer valid", code="EVIDENCE_UNAVAILABLE")
        if self.assistants.catalog.restriction is None:
            raise ServiceUnavailableException(
                "Originating token restrictions are unavailable", code="TOKEN_AUTHORITY_UNAVAILABLE"
            )
        issuer, _, sub = subject.partition("|")
        with SecurityContextHolder.using(
            SecurityContext(user_id=sub, attributes={"iss": issuer, "sub": sub, "koinon_token_id": token.id})
        ):
            await self.assistants.validate_scope(subject, tenant_id, run.scope)
            await self.assistants.authorize_results(subject, tenant_id, run.id)

    async def _sources(self, subject, tenant_id, run, message):
        from koinon.answers.receipts import verified_release

        references, result_ids, complete = {}, [], True
        release = verified_release(message, await self.assistants.active_results(run))
        selected_ids = {pin.id for pin in release.result_pins} if release else None
        selected_sources = {source.id for source in release.source_refs} if release else None
        identifiers = tuple(
            artifact["id"]
            for artifact in message.artifacts or []
            if artifact.get("kind") == "openui"
            and artifact.get("id")
            and (selected_ids is None or artifact["id"] in selected_ids)
        )
        if len(identifiers) > 100:
            raise InvalidRequestException("Select fewer evidence-bearing messages", code="SNAPSHOT_TOO_LARGE")
        egress = self.egress.get() if self.egress else None
        if egress:
            _, rows = await egress.repository.fixed(subject, tenant_id, (run.id,), identifiers)
        else:
            rows = await self.assistants.results.find_all(run_id=run.id)
        available = {row.id: row for row in rows}
        for artifact in message.artifacts or []:
            identifier = artifact.get("id")
            if selected_ids is not None and identifier not in selected_ids:
                continue
            if artifact.get("kind") != "openui" or not identifier:
                complete = False
                continue
            result = available.get(identifier)
            if result is None or result.run_id != run.id or artifact.get("run_id") != run.id:
                raise AccessDenied("Conversation evidence is unavailable", code="EVIDENCE_UNAVAILABLE")
            result_ids.append(identifier)
            assets = set(result.payload.get("asset_ids", []))
            if assets:
                await self.assistants.validate_scope(
                    subject, tenant_id, {"asset_ids": sorted(assets)}, run.scope
                )
            manifest = result.payload.get("source_manifest")
            if (
                isinstance(manifest, dict)
                and manifest.get("version") == 1
                and manifest.get("complete") is True
            ):
                try:
                    values = tuple(
                        SourceReference.model_validate(value) for value in manifest.get("sources", [])
                    )
                except ValueError as exc:
                    raise AccessDenied(
                        "Source provenance is unavailable", code="EVIDENCE_UNAVAILABLE"
                    ) from exc
                if {value.asset_id for value in values} != assets:
                    raise AccessDenied(
                        "Source provenance exceeds the recorded scope", code="EVIDENCE_UNAVAILABLE"
                    )
                for value in values:
                    if selected_sources is not None and value.id not in selected_sources:
                        continue
                    await self.assistants.catalog.get(subject, tenant_id, value.asset_id)
                    if value.used_revision is None:
                        complete = False
                    references[value.id] = value
                continue
            complete = False
            data = result.payload.get("data", {})
            for asset_id in sorted(assets):
                entry = await self.assistants.catalog.get(subject, tenant_id, asset_id)
                if entry.kind not in {"document", "dataset"}:
                    continue
                hits = [hit for hit in data.get("hits", []) if hit.get("asset_id") == asset_id] or [{}]
                for hit in hits:
                    values = {
                        "asset_id": asset_id,
                        "source_id": hit.get("source_id"),
                        "title": str(hit.get("title") or "Not recorded")[:255],
                        "kind": entry.kind,
                        "query_id": data.get("query_id") if result.kind == "query" else None,
                        "chunk_id": hit.get("id") if result.kind == "search" else None,
                        "quote": str(hit["text"])[:8000] if hit.get("text") else None,
                    }
                    reference = SourceReference(id=digest(values), **values)
                    references[reference.id] = reference
        if len(references) > 500 or len(result_ids) > 100:
            raise InvalidRequestException("Select fewer evidence-bearing messages", code="SNAPSHOT_TOO_LARGE")
        if message.role == "assistant" and not result_ids:
            complete = message.answer_policy.get("outcome") == "refused"
        return tuple(references[key] for key in sorted(references)), tuple(result_ids), complete

    @transactional(read_only=True, read_from_primary=True)
    async def snapshot(
        self, subject: str, tenant_id: str, thread_id: str, message_ids: list[str]
    ) -> ConversationSnapshot:
        if (
            not isinstance(message_ids, list)
            or not 1 <= len(message_ids) <= 200
            or any(not isinstance(value, str) or not 1 <= len(value) <= 64 for value in message_ids)
            or len(set(message_ids)) != len(message_ids)
        ):
            raise InvalidRequestException(
                "Select from 1 to 200 distinct messages", code="INVALID_MESSAGE_SELECTION"
            )
        thread = await self.assistants.thread(subject, tenant_id, thread_id)
        rows = await self.assistants.message_repository.snapshot_messages(thread_id, message_ids)
        if {row[0].id for row in rows} != set(message_ids):
            raise AccessDenied("Selected conversation messages are unavailable", code="EVIDENCE_UNAVAILABLE")
        private_origin = await self.assistants.message_repository.private_context_origin(thread_id)
        captures = tuple(
            {
                run.id: MemoryOutputCapture(run.id, "sequence", run.sequence)
                for message, run in rows
                if run is not None and message.role == "assistant"
            }.values()
        )
        messages, sources, tokens, complete, checked = [], {}, set(), True, set()
        selections = {}
        for message, run in rows:
            if message.role not in {"user", "assistant"} or message.status not in {
                "completed",
                "failed",
                "cancelled",
            }:
                raise InvalidRequestException(
                    "Select final user or assistant messages", code="MESSAGE_NOT_FINAL"
                )
            if run is not None and (run.thread_id != thread_id or run.tenant_id != tenant_id):
                raise AccessDenied("Conversation origin is unavailable", code="EVIDENCE_UNAVAILABLE")
            if run is not None and run.id not in checked:
                await self._origin(subject, tenant_id, run)
                checked.add(run.id)
                if run.access_token_id:
                    tokens.add(run.access_token_id)
            refs, results, qualified = (
                await self._sources(subject, tenant_id, run, message)
                if run is not None
                else ((), (), message.role == "user")
            )
            from koinon.answers.receipts import legacy_notice, message_language, verified_release

            released = (
                message.role != "assistant"
                or run is not None
                and verified_release(message, await self.assistants.active_results(run)) is not None
            )
            if not released:
                refs, results, qualified = (), (), False
            sources.update({value.id: value for value in refs})
            if run is not None and message.role == "assistant":
                selections.setdefault(run.id, set()).update(results)
            complete = complete and qualified
            private = private_origin is not None and message.created_at >= private_origin
            material = {
                "id": message.id,
                "role": message.role,
                "text": message.text if released else legacy_notice(message_language(message)),
                "status": message.status,
                "private_derived": private,
                "source_ids": tuple(value.id for value in refs),
                "result_ids": results,
                "created_at": message.created_at.isoformat(),
                "presentation": message.presentation or None,
            }
            messages.append(
                ConversationMessage(
                    **{
                        **material,
                        "created_at": message.created_at,
                        "presentation": Presentation.model_validate(message.presentation)
                        if message.presentation
                        else None,
                    },
                    revision=digest(material),
                )
            )
        if len(sources) > 500:
            raise InvalidRequestException("Select fewer source-bearing messages", code="SNAPSHOT_TOO_LARGE")
        ordered_sources = tuple(sources[key] for key in sorted(sources))
        material = {
            "thread_id": thread.id,
            "tenant_id": tenant_id,
            "owner_subject": subject,
            "title": thread.title,
            "messages": [value.model_dump(mode="json") for value in messages],
            "sources": [value.model_dump(mode="json") for value in ordered_sources],
            "source_manifest_complete": complete,
            "originating_token_ids": sorted(tokens),
        }
        if len(json.dumps(material, ensure_ascii=False).encode()) > 5 * 1024 * 1024:
            raise InvalidRequestException("Select fewer messages for the snapshot", code="SNAPSHOT_TOO_LARGE")
        egress = self.egress.get() if self.egress else None
        bindings = (
            await egress.bind(
                subject,
                tenant_id,
                tuple(
                    (run_id, tuple(sorted(identifiers))) for run_id, identifiers in sorted(selections.items())
                ),
            )
            if egress
            else ()
        )
        result = MemoryConversationSnapshot(
            **{
                **material,
                "messages": tuple(messages),
                "sources": ordered_sources,
                "originating_token_ids": tuple(sorted(tokens)),
            },
            revision=digest(material),
            memory_bindings=bindings,
        )
        if egress:
            await egress.authorize(subject, tenant_id, bindings, captures=captures)
        return result
