# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Whole-set reader preference snapshots with operation replay and revision fencing."""

from datetime import UTC, datetime
from typing import cast

from pyfly.container import repository
from pyfly.data.relational.sqlalchemy import Repository
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from koinon.integrations.content_sources.dtos import Provider
from koinon.integrations.content_sources.entities import PersonalSourceConnection
from koinon.integrations.content_sources.errors import SourceError
from koinon.integrations.content_sources.read_dtos import ReaderSelectionOutput, ReaderSourceSelection
from koinon.integrations.content_sources.reader_entities import (
    SourceReaderSelection,
    SourceReaderSelectionOperation,
    SourceReaderSelectionSet,
)


@repository(name="content_sources.reader_selection_repository")
class SourceReaderSelectionRepository(Repository[SourceReaderSelectionSet, str]):
    async def validate_owned(self, actor, tenant, choices):
        identifiers = {choice.connection_id for choice in choices}
        rows = (
            list(
                await self._require_session().scalars(
                    select(PersonalSourceConnection).where(
                        PersonalSourceConnection.tenant_id == tenant,
                        PersonalSourceConnection.owner == actor,
                        PersonalSourceConnection.id.in_(identifiers),
                    )
                )
            )
            if identifiers
            else []
        )
        available = {row.id: row for row in rows}
        for choice in choices:
            row = available.get(choice.connection_id)
            if (
                row is None
                or row.status != "connected"
                or not row.external_subject
                or (row.provider, row.external_tenant) != (choice.provider, choice.external_tenant)
            ):
                raise SourceError("access_denied")

    async def lock_revision(self, tenant, actor, revision):
        session = self._require_session()
        await session.execute(
            insert(SourceReaderSelectionSet)
            .values(
                tenant_id=tenant,
                owner=actor,
                revision=0,
                updated_at=datetime.now(UTC),
            )
            .on_conflict_do_nothing(index_elements=["tenant_id", "owner"])
        )
        current = await session.scalar(
            select(SourceReaderSelectionSet.revision)
            .where(
                SourceReaderSelectionSet.tenant_id == tenant,
                SourceReaderSelectionSet.owner == actor,
            )
            .with_for_update()
        )
        if current != revision:
            raise SourceError("authority_changed")

    async def snapshot(self, tenant, actor, *, revision=None):
        session = self._require_session()
        if revision is None:
            revision = await session.scalar(
                select(SourceReaderSelectionSet.revision).where(
                    SourceReaderSelectionSet.tenant_id == tenant, SourceReaderSelectionSet.owner == actor
                )
            )
            revision = revision or 0
        rows = await session.scalars(
            select(SourceReaderSelection)
            .where(
                SourceReaderSelection.tenant_id == tenant,
                SourceReaderSelection.owner == actor,
                SourceReaderSelection.set_revision == revision,
            )
            .order_by(SourceReaderSelection.provider, SourceReaderSelection.external_tenant_key)
        )
        return ReaderSelectionOutput(
            revision=revision,
            connections=tuple(
                ReaderSourceSelection(
                    provider=cast(Provider, row.provider),
                    external_tenant=row.external_tenant,
                    connection_id=row.connection_id,
                )
                for row in rows
            ),
        )

    async def replace(self, actor, tenant, request, digest):
        session = self._require_session()
        await session.execute(
            insert(SourceReaderSelectionSet)
            .values(
                tenant_id=tenant,
                owner=actor,
                revision=0,
                updated_at=datetime.now(UTC),
            )
            .on_conflict_do_nothing(index_elements=["tenant_id", "owner"])
        )
        header = await session.scalar(
            select(SourceReaderSelectionSet)
            .where(
                SourceReaderSelectionSet.tenant_id == tenant,
                SourceReaderSelectionSet.owner == actor,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        operation = await session.scalar(
            select(SourceReaderSelectionOperation).where(
                SourceReaderSelectionOperation.tenant_id == tenant,
                SourceReaderSelectionOperation.owner == actor,
                SourceReaderSelectionOperation.operation_id == str(request.operation_id),
            )
        )
        if operation is not None:
            if operation.payload_sha256 != digest:
                raise SourceError("authority_changed")
            return await self.snapshot(tenant, actor, revision=operation.result_revision)
        if header is None or header.revision != request.expected_revision:
            raise SourceError("authority_changed")
        connection_ids = {choice.connection_id for choice in request.connections}
        rows = (
            list(
                await session.scalars(
                    select(PersonalSourceConnection).where(
                        PersonalSourceConnection.tenant_id == tenant,
                        PersonalSourceConnection.owner == actor,
                        PersonalSourceConnection.id.in_(connection_ids),
                    )
                )
            )
            if connection_ids
            else []
        )
        available = {row.id: row for row in rows}
        for choice in request.connections:
            row = available.get(choice.connection_id)
            if (
                row is None
                or row.status != "connected"
                or not row.external_subject
                or (row.provider, row.external_tenant) != (choice.provider, choice.external_tenant)
            ):
                raise SourceError("access_denied")
        revision = header.revision + 1
        session.add_all(
            [
                SourceReaderSelection(
                    tenant_id=tenant,
                    owner=actor,
                    set_revision=revision,
                    provider=choice.provider,
                    external_tenant=choice.external_tenant,
                    external_tenant_key="none:"
                    if choice.external_tenant is None
                    else "value:" + choice.external_tenant,
                    connection_id=choice.connection_id,
                )
                for choice in request.connections
            ]
        )
        session.add(
            SourceReaderSelectionOperation(
                tenant_id=tenant,
                owner=actor,
                operation_id=str(request.operation_id),
                payload_sha256=digest,
                result_revision=revision,
            )
        )
        await session.flush()
        header.revision, header.updated_at = revision, datetime.now(UTC)
        await session.flush()
        return await self.snapshot(tenant, actor, revision=revision)
