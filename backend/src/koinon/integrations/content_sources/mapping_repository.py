# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Short database fences; external observations must precede entry to this unit."""

from datetime import UTC, datetime
from typing import Literal

from pyfly.container import repository
from pyfly.data.relational.sqlalchemy import Repository
from sqlalchemy import or_, select

from koinon.integrations.content_sources.dtos import Account
from koinon.integrations.content_sources.entities import PersonalSourceConnection
from koinon.integrations.content_sources.errors import SourceError
from koinon.integrations.content_sources.mapping_dtos import MappingCandidate
from koinon.integrations.content_sources.mapping_entities import SourceMapping, SourceObject

ObservationState = Literal["pending", "deleted", "removed", "excluded"]


@repository(name="content_sources.mapping_repository")
class SourceMappingRepository(Repository[SourceMapping, str]):
    async def review_candidates(
        self, tenant: str, account: Account, drive_id: str, *, at: datetime
    ) -> tuple[MappingCandidate, ...]:
        # Callers hold canonical tenant authority while admitting or revalidating this inventory.
        statement = (
            select(SourceMapping)
            .where(
                SourceMapping.tenant_id == tenant,
                SourceMapping.provider == account.provider,
                SourceMapping.external_subject == account.subject,
                SourceMapping.external_tenant == account.tenant_id,
                SourceMapping.drive_id == drive_id,
                SourceMapping.status != "retired",
                or_(
                    SourceMapping.status != "reviewed",
                    SourceMapping.reviewed_expires_at.is_(None),
                    SourceMapping.reviewed_expires_at > at,
                ),
            )
            .order_by(SourceMapping.id)
            .limit(100)
            .execution_options(populate_existing=True)
        )
        rows = list((await self._require_session().scalars(statement)).all())
        # Leave one slot for the proposed root. Never silently truncate overlap candidates.
        if len(rows) >= 100:
            raise SourceError("size_exceeded")
        candidates = []
        for row in rows:
            recursive = row.request_json.get("recursive")
            if not isinstance(recursive, bool):
                raise SourceError("scope_mismatch")
            candidates.append(
                MappingCandidate(row.id, row.revision, row.root_id, row.request_sha256, recursive, row.status)
            )
        return tuple(candidates)

    async def owned(self, tenant: str, owner: str, identifier: str) -> SourceMapping | None:
        return await self._require_session().scalar(
            select(SourceMapping).where(
                SourceMapping.id == identifier,
                SourceMapping.tenant_id == tenant,
                SourceMapping.owner == owner,
            )
        )

    async def lock_active(
        self, tenant: str, identifier: str, revision: int, connection_revision: int
    ) -> SourceMapping | None:
        session = self._require_session()
        # Connection first: disconnect/rotation cannot commit between this check and the object fence.
        connection = await session.scalar(
            select(PersonalSourceConnection)
            .join(SourceMapping, SourceMapping.connection_id == PersonalSourceConnection.id)
            .where(
                SourceMapping.id == identifier,
                SourceMapping.tenant_id == tenant,
                PersonalSourceConnection.tenant_id == tenant,
                PersonalSourceConnection.owner == SourceMapping.owner,
            )
            .with_for_update(of=PersonalSourceConnection)
            .execution_options(populate_existing=True)
        )
        if connection is None:
            return None
        mapping = await session.scalar(
            select(SourceMapping)
            .where(SourceMapping.id == identifier, SourceMapping.tenant_id == tenant)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if (
            mapping is None
            or mapping.status != "active"
            or mapping.revision != revision
            or connection.tenant_id != tenant
            or connection.owner != mapping.owner
            or connection.id != mapping.connection_id
            or connection.provider != mapping.provider
            or connection.external_subject != mapping.external_subject
            or connection.external_tenant != mapping.external_tenant
            or connection.issuer != mapping.issuer
            or connection.config_fingerprint != mapping.config_fingerprint
            or connection.status != "connected"
            or connection.secret_ciphertext is None
            or connection.refresh_operation is not None
            or connection.revision != connection_revision
        ):
            return None
        return mapping

    async def observe(
        self,
        tenant: str,
        mapping_id: str,
        mapping_revision: int,
        object_id: str,
        generation: int,
        *,
        connection_revision: int,
        version: str | None,
        state: ObservationState,
    ) -> bool:
        if state not in {"pending", "deleted", "removed", "excluded"}:
            raise ValueError("Invalid source observation state")
        if state == "pending" and not version:
            raise ValueError("A pending source observation requires a remote version")
        if await self.lock_active(tenant, mapping_id, mapping_revision, connection_revision) is None:
            return False
        session = self._require_session()
        item = await session.scalar(
            select(SourceObject)
            .where(
                SourceObject.id == object_id,
                SourceObject.tenant_id == tenant,
                SourceObject.mapping_id == mapping_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if item is None or item.generation != generation or item.state == "excluded":
            return False
        if (
            item.remote_version == version
            and (item.state == state or (state == "pending" and item.state in {"imported", "failed"}))
            and item.mapping_revision == mapping_revision
        ):
            return True
        if item.generation >= 2147483647:
            return False
        item.generation += 1
        item.mapping_revision = mapping_revision
        item.remote_version = version
        item.state = state
        item.updated_at = datetime.now(UTC)
        await session.flush()
        return True
