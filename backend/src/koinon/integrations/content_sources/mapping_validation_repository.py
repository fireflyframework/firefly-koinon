# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Tenant-serialized transient preparation and fenced, bounded payload reclamation."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from pyfly.container import repository
from pyfly.data.relational.sqlalchemy import Repository
from pyfly.kernel import RateLimitException
from sqlalchemy import delete, exists, func, or_, select, text

from koinon.catalog.entities import Tenant
from koinon.integrations.content_sources.errors import SourceError
from koinon.integrations.content_sources.mapping_validation_entities import (
    SourceMappingValidation as Validation,
)
from koinon.integrations.content_sources.mapping_validation_entities import (
    SourceMappingValidationEntry as Entry,
)
from koinon.integrations.content_sources.sync_controls import _conflict


@dataclass(frozen=True, slots=True)
class ValidationCleanupClaim:
    """Private maintenance capability, returned only by a successful claim transaction."""

    tenant: str
    validation_id: UUID
    token: UUID
    expires_at: datetime


@repository(name="content_sources.mapping_validations")
class SourceMappingValidationRepository(Repository[Validation, UUID]):
    async def database_time(self) -> datetime:
        value = await self._require_session().scalar(select(func.clock_timestamp()))
        if not isinstance(value, datetime) or value.utcoffset() is None:
            raise SourceError("unavailable")
        return value.astimezone(UTC)

    async def tenant_lock(self, tenant: str) -> None:
        if (
            await self._require_session().scalar(
                select(Tenant.id).where(Tenant.id == tenant).with_for_update()
            )
            is None
        ):
            raise SourceError("access_denied")

    async def owned(self, tenant, actor, identifier, *, lock=False):
        statement = (
            select(Validation)
            .where(Validation.tenant_id == tenant, Validation.owner == actor, Validation.id == identifier)
            .execution_options(populate_existing=True)
        )
        if lock:
            await self.tenant_lock(tenant)
            statement = statement.with_for_update()
        return await self._require_session().scalar(statement)

    async def operation(self, tenant, actor, operation):
        return await self._require_session().scalar(
            select(Validation)
            .where(
                Validation.tenant_id == tenant,
                Validation.owner == actor,
                Validation.operation_id == operation,
            )
            .execution_options(populate_existing=True)
        )

    async def admit(self, row: Validation) -> Validation:
        await self.tenant_lock(row.tenant_id)
        previous = await self.operation(row.tenant_id, row.owner, row.operation_id)
        if previous is not None:
            if (
                previous.request_sha256,
                previous.session_hash,
                previous.mapping_id,
                previous.expected_revision,
            ) != (row.request_sha256, row.session_hash, row.mapping_id, row.expected_revision):
                raise _conflict("IDEMPOTENCY_CONFLICT")
            return previous
        headers = (
            await self._require_session().execute(
                select(Validation.owner, Validation.reserved_bytes, Validation.payload_released_at)
                .where(Validation.tenant_id == row.tenant_id)
                .limit(1001)
            )
        ).all()
        active = [header for header in headers if header.payload_released_at is None]
        if (
            len(headers) >= row.max_records_per_tenant
            or len(active) >= row.max_active_per_tenant
            or sum(header.owner == row.owner for header in active) >= row.max_active_per_owner
            or sum(header.reserved_bytes for header in headers) + row.reserved_bytes
            > row.max_retained_bytes_per_tenant
        ):
            # No inventory or protected occupancy from another owner reaches this exception.
            raise RateLimitException(
                "Preparation capacity is occupied; inspect your preparations.",
                code="SOURCE_VALIDATION_CAPACITY",
            )
        self._require_session().add(row)
        await self._require_session().flush()
        return row

    async def entries(self, row, *, after=-1, limit=100):
        if not 1 <= limit <= 1000:
            raise ValueError("Preparation reads must be bounded")
        return list(
            (
                await self._require_session().scalars(
                    select(Entry)
                    .where(
                        Entry.tenant_id == row.tenant_id,
                        Entry.validation_id == row.id,
                        Entry.sequence > after,
                    )
                    .order_by(Entry.sequence)
                    .limit(limit)
                )
            ).all()
        )

    async def entry(self, row, item):
        return await self._require_session().get(Entry, (row.tenant_id, row.id, item))

    async def append(self, row, values):
        """Caller holds tenant/header locks; exact duplicates still consume raw work upstream."""
        added = 0
        for entry in values:
            previous = await self.entry(row, entry.item_id)
            if previous is not None:
                if previous.fingerprint_sha256 != entry.fingerprint_sha256:
                    raise _conflict("SOURCE_CHANGED")
                continue
            entry.sequence = row.eligible_count + added
            if entry.sequence >= row.scan_max_items:
                raise _conflict("SOURCE_SCAN_LIMIT_EXCEEDED")
            self._require_session().add(entry)
            await self._require_session().flush()
            added += 1
        return added

    async def source_collision(self, row):
        return (
            await self._require_session().scalar(
                select(Entry.destination_key_sha256)
                .where(Entry.tenant_id == row.tenant_id, Entry.validation_id == row.id)
                .group_by(Entry.destination_key_sha256)
                .having(func.count() > 1)
                .limit(1)
            )
            is not None
        )

    async def collision_keys(self, row, keys):
        if len(keys) > 100:
            raise ValueError("Collision presentation must be bounded")
        if not keys:
            return set()
        return set(
            (
                await self._require_session().scalars(
                    select(Entry.destination_key_sha256)
                    .where(
                        Entry.tenant_id == row.tenant_id,
                        Entry.validation_id == row.id,
                        Entry.destination_key_sha256.in_(keys),
                    )
                    .group_by(Entry.destination_key_sha256)
                    .having(func.count() > 1)
                )
            ).all()
        )

    async def mark_verified(self, row, items):
        for identifier in items:
            entry = await self.entry(row, identifier)
            if entry is None:
                raise _conflict("SOURCE_VALIDATION_CHANGED")
            entry.verified = True
        await self._require_session().flush()

    @staticmethod
    def start_cleanup(row, now, reason="abandoned"):
        if row.state in {"cleaning", "abandoned", "expired"}:
            return
        row.state, row.cleanup_reason = "cleaning", reason
        row.request_ciphertext = row.root_proof_ciphertext = None
        row.walk_ciphertext = row.checkpoint_ciphertext = None
        row.last_continuation_sha256 = row.last_continuation_result_revision = None
        row.updated_at, row.revision = now, row.revision + 1

    async def cleanup_candidate(self, now):
        """Select one identity only; lock tenant before touching its header."""
        return (
            await self._require_session().execute(
                select(Validation.tenant_id, Validation.id)
                .where(
                    or_(Validation.state == "cleaning", Validation.expires_at <= now),
                    or_(Validation.cleanup_claim_until.is_(None), Validation.cleanup_claim_until <= now),
                )
                .order_by(
                    Validation.cleanup_last_attempt_at.asc().nulls_first(),
                    Validation.tenant_id,
                    Validation.id,
                )
                .limit(1)
            )
        ).first()

    async def _maintenance_timeout(self):
        if self._require_session().get_bind().dialect.name == "postgresql":
            await self._require_session().execute(text("SET LOCAL lock_timeout='1s'"))
            await self._require_session().execute(text("SET LOCAL statement_timeout='1s'"))

    async def claim_cleanup(self, tenant, identifier, now) -> ValidationCleanupClaim | None:
        await self._maintenance_timeout()
        await self.tenant_lock(tenant)
        row = await self._require_session().scalar(
            select(Validation)
            .where(Validation.tenant_id == tenant, Validation.id == identifier)
            .with_for_update(skip_locked=True)
            .execution_options(populate_existing=True)
        )
        if row is None or row.cleanup_claim_until is not None and row.cleanup_claim_until > now:
            return None
        if row.payload_released_at is not None:
            if row.expires_at <= now:
                await self._require_session().delete(row)
            return None
        if row.expires_at <= now:
            self.start_cleanup(row, now, "expired")
        if row.state != "cleaning":
            return None
        token, until = uuid4(), now + timedelta(seconds=10)
        row.cleanup_claim_token, row.cleanup_claim_until = token, until
        row.cleanup_last_attempt_at = now
        await self._require_session().flush()
        return ValidationCleanupClaim(tenant, identifier, token, until)

    async def cleanup_batch(self, claim: ValidationCleanupClaim, now, *, limit=1000):
        if not isinstance(claim, ValidationCleanupClaim) or not 1 <= limit <= 1000:
            raise SourceError("access_denied")
        await self._maintenance_timeout()
        await self.tenant_lock(claim.tenant)
        row = await self._require_session().scalar(
            select(Validation)
            .where(Validation.tenant_id == claim.tenant, Validation.id == claim.validation_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        # A stored live claim is insufficient: the caller must supply the exact unexpired capability.
        if (
            row is None
            or row.state != "cleaning"
            or row.cleanup_claim_token != claim.token
            or row.cleanup_claim_until != claim.expires_at
            or claim.expires_at <= now
        ):
            raise SourceError("access_denied")
        ids = (
            select(Entry.item_id)
            .where(Entry.tenant_id == claim.tenant, Entry.validation_id == claim.validation_id)
            .order_by(Entry.sequence)
            .limit(limit)
        )
        removed = (
            await self._require_session().execute(
                delete(Entry)
                .where(
                    Entry.tenant_id == claim.tenant,
                    Entry.validation_id == claim.validation_id,
                    Entry.item_id.in_(ids),
                )
                .returning(Entry.sequence)
            )
        ).all()
        remaining = await self._require_session().scalar(
            select(
                exists().where(Entry.tenant_id == claim.tenant, Entry.validation_id == claim.validation_id)
            )
        )
        row.cleanup_position += len(removed)
        row.cleanup_claim_token = row.cleanup_claim_until = None
        row.updated_at, row.revision = now, row.revision + 1
        if not remaining:
            if any(
                value is not None
                for value in (
                    row.request_ciphertext,
                    row.root_proof_ciphertext,
                    row.walk_ciphertext,
                    row.checkpoint_ciphertext,
                )
            ):
                raise _conflict("SOURCE_VALIDATION_CHANGED")
            row.state = "expired" if row.cleanup_reason == "expired" else "abandoned"
            row.payload_released_at = now
        await self._require_session().flush()
        return bool(remaining)
