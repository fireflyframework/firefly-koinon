# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""A native tool proposes metadata; explicit owner confirmation applies it."""

import hashlib
import json
from contextlib import contextmanager

from pyfly.container import service
from pyfly.data.relational.sqlalchemy import LockMode, transactional
from pyfly.kernel import ConflictException, InvalidRequestException, ServiceUnavailableException
from pyfly.security.context import SecurityContext
from pyfly.security.context_holder import SecurityContextHolder

from koinon.assistants.entities import ToolResult
from koinon.assistants.lifecycle import identifier, timestamp
from koinon.assistants.proposal_dtos import (
    CatalogProposal,
    CatalogProposalBefore,
    CatalogProposalPatch,
    ProposalConfirmation,
)
from koinon.assistants.queue import AssistantQueue
from koinon.assistants.service import AssistantService
from koinon.catalog.errors import AccessDenied
from koinon.catalog.mappers import entry_dto


def catalog_digest(entry):
    value = json.dumps(
        entry_dto(entry), sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    )
    return hashlib.sha256(value.encode()).hexdigest()


@service(name="assistants.proposals")
class CatalogProposals:
    def __init__(self, assistants: AssistantService, queue: AssistantQueue):
        self.assistants, self.queue = assistants, queue

    @contextmanager
    def origin(self, run, subject):
        if not run.access_token_id:
            yield
            return
        if self.assistants.catalog.restriction is None:
            raise ServiceUnavailableException(
                "Originating authority is unavailable", code="TOKEN_AUTHORITY_UNAVAILABLE"
            )
        issuer, _, sub = subject.partition("|")
        with SecurityContextHolder.using(
            SecurityContext(
                user_id=sub, attributes={"iss": issuer, "sub": sub, "koinon_token_id": run.access_token_id}
            )
        ):
            yield

    async def target(self, subject, run, asset_id, *, write):
        entry = await self.assistants.catalog.get(subject, run.tenant_id, asset_id)
        if entry.kind not in {"document", "dataset"} or entry.status == "archived":
            raise InvalidRequestException(
                "Choose an active document or dataset", code="PROPOSAL_TARGET_UNSUPPORTED"
            )
        await self.assistants.validate_scope(subject, run.tenant_id, {"asset_ids": [asset_id]}, run.scope)
        if write:
            await self.assistants.catalog.authorize(
                subject, run.tenant_id, "catalog:write", entry.workspace_id
            )
            if self.assistants.catalog.restriction:
                await self.assistants.catalog.restriction.resource(subject, entry, write=True)
        return entry

    async def load(self, subject, tenant_id, run_id, proposal_id, *, write=False, lock=False):
        run = await self.assistants.owned_run(subject, tenant_id, run_id, lock=lock)
        row = await self.assistants.results.find_by_id(
            proposal_id, lock=LockMode.PESSIMISTIC_WRITE if lock else None
        )
        if row is None or row.run_id != run_id or row.kind != "proposal":
            raise AccessDenied("Proposal is unavailable in this answer", code="PROPOSAL_UNAVAILABLE")
        value = CatalogProposal.model_validate(row.payload["data"])
        message = await self.assistants.message_repository.find_by_id(run.message_id)
        active = any(
            value.get("id") == row.id and value.get("run_id") == run.id for value in message.artifacts or []
        )
        if row.payload.get("attempt") != run.attempts or not active:
            raise ConflictException("The proposal belongs to an earlier attempt", code="PROPOSAL_SUPERSEDED")
        await self.target(subject, run, value.asset_id, write=write)
        with self.origin(run, subject):
            await self.target(subject, run, value.asset_id, write=write)
        return run, row, value

    @transactional
    async def propose(self, run_id: str, worker_id: str, asset_id: str, changes: dict) -> CatalogProposal:
        patch = CatalogProposalPatch.model_validate(changes)
        run = await self.queue.locked(run_id, worker_id)
        thread = await self.assistants.threads.find_by_id(run.thread_id)
        await self.assistants.owned_run(thread.subject, run.tenant_id, run_id)
        entry = await self.target(thread.subject, run, asset_id, write=True)
        with self.origin(run, thread.subject):
            await self.target(thread.subject, run, asset_id, write=True)
        fields = patch.model_dump(exclude_unset=True)
        if all(getattr(entry, key) == value for key, value in fields.items()):
            raise InvalidRequestException("The proposed fields already match", code="PROPOSAL_NO_CHANGES")
        digest = catalog_digest(entry)
        previous = await self.assistants.results.find_all(run_id=run_id, kind="proposal")
        for row in previous:
            old = CatalogProposal.model_validate(row.payload["data"])
            if (
                row.payload.get("attempt") == run.attempts
                and old.status == "pending"
                and old.asset_id == asset_id
                and old.expected_catalog_digest == digest
                and old.changes == patch
            ):
                return old
        if len(previous) >= 10:
            raise InvalidRequestException("Review the existing proposals first", code="PROPOSAL_LIMIT")
        value = CatalogProposal(
            id=identifier(),
            run_id=run_id,
            status="pending",
            revision=1,
            asset_id=asset_id,
            before=CatalogProposalBefore(name=entry.name, description=entry.description),
            changes=patch,
            expected_catalog_digest=digest,
            created_at=timestamp(),
        )
        await self.assistants.results.save(
            ToolResult(
                id=value.id,
                run_id=run_id,
                kind="proposal",
                payload={
                    "data": value.model_dump(mode="json"),
                    "asset_ids": [asset_id],
                    "attempt": run.attempts,
                    "origin_token_id": run.access_token_id,
                },
            )
        )
        artifact = {
            "id": value.id,
            "kind": "openui",
            "run_id": run_id,
            "complete": True,
            "language": f'root = KnowledgeAnswer([item])\nitem = Evidence("{value.id}", "proposal")',
        }
        message = await self.assistants.message_repository.find_by_id(run.message_id)
        message.artifacts = [*message.artifacts, artifact]
        await self.assistants.message_repository.save(message)
        await self.assistants.record_event(run, "openui_delta", {"artifact": artifact})
        return value

    @transactional(read_only=True)
    async def get(self, subject, tenant_id, run_id, proposal_id) -> CatalogProposal:
        return (await self.load(subject, tenant_id, run_id, proposal_id))[2]

    @transactional
    async def confirm(
        self, subject, tenant_id, run_id, proposal_id, confirmation: ProposalConfirmation
    ) -> CatalogProposal:
        run, row, value = await self.load(subject, tenant_id, run_id, proposal_id, write=True, lock=True)
        if (
            value.status == "applied"
            and row.payload.get("applied_from_revision") == confirmation.expected_revision
        ):
            return value
        if value.status != "pending" or value.revision != confirmation.expected_revision:
            raise ConflictException(
                "Refresh the proposal before confirming", code="PROPOSAL_REVISION_CONFLICT"
            )
        if run.status != "completed":
            raise ConflictException(
                "Wait for a completed answer before confirming", code="PROPOSAL_RUN_NOT_COMPLETED"
            )
        entry = await self.assistants.catalog._scoped_entry(tenant_id, value.asset_id, lock=True)
        if catalog_digest(entry) != value.expected_catalog_digest:
            raise ConflictException(
                "Knowledge changed after this proposal; request a new one", code="PROPOSAL_RESOURCE_CHANGED"
            )
        with self.origin(run, subject):
            await self.target(subject, run, value.asset_id, write=True)
            await self.assistants.catalog.update(
                subject, tenant_id, value.asset_id, value.changes.model_dump(exclude_unset=True)
            )
        updated = value.model_copy(
            update={"status": "applied", "revision": value.revision + 1, "applied_at": timestamp()}
        )
        row.payload = {
            **row.payload,
            "data": updated.model_dump(mode="json"),
            "applied_from_revision": value.revision,
        }
        await self.assistants.results.save(row)
        await self.assistants.record_event(
            run,
            "proposal_updated",
            {"proposal_update": {"id": value.id, "status": "applied", "revision": updated.revision}},
        )
        return updated

    @transactional
    async def cancel(
        self, subject, tenant_id, run_id, proposal_id, *, expected_revision: int
    ) -> CatalogProposal:
        run, row, value = await self.load(subject, tenant_id, run_id, proposal_id, lock=True)
        if value.status == "cancelled" and row.payload.get("cancelled_from_revision") == expected_revision:
            return value
        if value.status != "pending" or value.revision != expected_revision:
            raise ConflictException(
                "Refresh the proposal before cancelling", code="PROPOSAL_REVISION_CONFLICT"
            )
        updated = value.model_copy(
            update={"status": "cancelled", "revision": value.revision + 1, "cancelled_at": timestamp()}
        )
        row.payload = {
            **row.payload,
            "data": updated.model_dump(mode="json"),
            "cancelled_from_revision": value.revision,
        }
        await self.assistants.results.save(row)
        await self.assistants.record_event(
            run,
            "proposal_updated",
            {"proposal_update": {"id": value.id, "status": "cancelled", "revision": updated.revision}},
        )
        return updated
