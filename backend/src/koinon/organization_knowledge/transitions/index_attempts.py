# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Captured activation identity is retained independently of a reusable index row."""

from hashlib import sha256
from json import dumps

from pyfly.container import repository
from pyfly.data.relational.sqlalchemy import Repository
from pyfly.data.transaction import current_unit_of_work
from pyfly.kernel import ConflictException
from sqlalchemy import select, update

from koinon.organization_knowledge.transitions.entities import (
    KnowledgeModeIndexAttempt,
    KnowledgeModeIndexResolution,
    now,
)


@repository(name="organization_knowledge.mode_index_attempts")
class ModeIndexAttemptRepository(Repository[KnowledgeModeIndexAttempt, str]):
    @staticmethod
    def require_write():
        unit = current_unit_of_work("primary")
        if unit is None or unit.completed or unit.read_only or not unit.read_from_primary:
            raise RuntimeError("Activation evidence requires its primary admission transaction")

    async def capture(self, tenant_id, parent_id, index):
        self.require_write()
        if index.tenant_id != tenant_id:
            raise ConflictException("The index activation scope changed", code="INDEX_MODE_RECEIPT_CHANGED")
        identifier = sha256(dumps([tenant_id, parent_id, index.id, index.revision]).encode()).hexdigest()
        existing = await self._require_session().get(KnowledgeModeIndexAttempt, identifier)
        values = {
            key: getattr(index, key)
            for key in (
                "workspace_id",
                "native_workspace_id",
                "native_id",
                "job_id",
                "provider_id",
                "provider_revision",
                "model_id",
                "dimensions",
                "storage_dimensions",
                "embedding_fingerprint",
            )
        }
        values.update(
            index_id=index.id,
            attempt_revision=index.revision,
            actor=index.transition.get("activation_actor", index.updated_by),
            access_token_id=index.transition.get("activation_token_id", index.access_token_id),
            request=index.transition["request"],
            previous_native_id=index.transition.get("previous_native_id"),
        )
        if existing is not None:
            if any(getattr(existing, key) != value for key, value in values.items()):
                raise ConflictException(
                    "The captured activation identity changed", code="INDEX_MODE_RECEIPT_CHANGED"
                )
            return identifier
        self._require_session().add(
            KnowledgeModeIndexAttempt(
                id=identifier,
                tenant_id=tenant_id,
                transition_id=parent_id,
                **values,
            )
        )
        await self._require_session().flush()
        self._require_session().add(KnowledgeModeIndexResolution(id=identifier, tenant_id=tenant_id))
        await self._require_session().flush()
        return identifier

    async def resolve(self, tenant_id, parent_id, identifier, index, outcome, *, expected_revision):
        self.require_write()
        if outcome not in {"finished", "restored", "aborted"}:
            raise ValueError("Select a terminal activation outcome")
        attempt = await self._require_session().scalar(
            select(KnowledgeModeIndexAttempt).where(
                KnowledgeModeIndexAttempt.tenant_id == tenant_id,
                KnowledgeModeIndexAttempt.transition_id == parent_id,
                KnowledgeModeIndexAttempt.id == identifier,
            )
        )
        if (
            attempt is None
            or index.tenant_id != tenant_id
            or attempt.index_id != index.id
            or index.transition.get("mode_activation_attempt_id") != attempt.id
            or index.transition.get("mode_activation_attempt_revision") != attempt.attempt_revision
            or index.revision <= attempt.attempt_revision
            or any(
                getattr(attempt, key) != getattr(index, key)
                for key in (
                    "workspace_id",
                    "native_workspace_id",
                    "native_id",
                    "job_id",
                    "provider_id",
                    "provider_revision",
                    "dimensions",
                    "storage_dimensions",
                    "model_id",
                    "embedding_fingerprint",
                )
            )
        ):
            raise ConflictException("Reload the exact activation receipt", code="INDEX_MODE_RECEIPT_CHANGED")
        resolution = KnowledgeModeIndexResolution
        result = await self._require_session().execute(
            update(resolution)
            .where(
                resolution.tenant_id == tenant_id,
                resolution.id == identifier,
                resolution.status == "pending",
                resolution.revision == expected_revision,
            )
            .values(status=outcome, revision=expected_revision + 1, updated_at=now())
            .returning(resolution.id)
        )
        if result.scalar_one_or_none() is None:
            current = await self._require_session().get(resolution, identifier, populate_existing=True)
            if current is None or current.status != outcome or current.revision != expected_revision + 1:
                raise ConflictException("Reload the activation resolution", code="INDEX_MODE_RECEIPT_CHANGED")

    async def page(self, tenant_id, parent_id, *, after=None, limit=100):
        if type(limit) is not int or not 1 <= limit <= 101:
            raise ValueError("Select a bounded activation receipt page")
        row = KnowledgeModeIndexAttempt
        query = select(row).where(row.tenant_id == tenant_id, row.transition_id == parent_id)
        if after is not None:
            query = query.where(row.id > after)
        return list(await self._require_session().scalars(query.order_by(row.id).limit(limit)))

    async def resolutions(self, tenant_id, identifiers):
        if len(identifiers) > 100:
            raise ValueError("Resolution lookup requires a bounded receipt page")
        row = KnowledgeModeIndexResolution
        values = await self._require_session().scalars(
            select(row)
            .where(
                row.tenant_id == tenant_id,
                row.id.in_(identifiers),
            )
            .execution_options(populate_existing=True)
        )
        return {value.id: value for value in values}
