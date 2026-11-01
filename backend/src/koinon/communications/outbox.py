# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Short native claims; uncertain transport is never converted into a repeatable failure."""

import re
from dataclasses import dataclass, field
from datetime import timedelta

from pyfly.container import service
from pyfly.data.relational.sqlalchemy import transactional
from sqlalchemy import and_, or_, select, update

from koinon.communications.entities import OutboxRecord
from koinon.communications.repositories import OutboxRepository
from koinon.communications.settings import CommunicationsSettings


@dataclass(frozen=True, slots=True)
class DeliveryTicket:
    id: str
    generation: int
    owner: str
    payload_ciphertext: str | None = field(default=None, repr=False)
    payload_hash: str | None = None


@service(name="communications.outbox_state")
class CommunicationOutbox:
    def __init__(self, outbox: OutboxRepository, settings: CommunicationsSettings):
        self.outbox, self.settings = outbox, settings

    @transactional
    async def claim(self, owner):
        if not isinstance(owner, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", owner):
            raise ValueError("Use a bounded internal delivery worker identifier")
        session = self.outbox._require_session()
        now = await self.outbox.clock()
        uncertain = list(
            await session.scalars(
                select(OutboxRecord)
                .where(OutboxRecord.status == "sending", OutboxRecord.lease_until <= now)
                .order_by(OutboxRecord.lease_until, OutboxRecord.id)
                .limit(32)
                .with_for_update(skip_locked=True)
            )
        )
        for row in uncertain:
            row.status, row.failure_code, row.completed_at = "unknown", "SEND_OUTCOME_UNKNOWN", now
            row.generation += 1
            row.lease_owner = row.lease_until = None
            await self.outbox.save(row)
        exhausted = list(
            await session.scalars(
                select(OutboxRecord)
                .where(
                    or_(
                        and_(OutboxRecord.status == "preparing", OutboxRecord.lease_until <= now),
                        and_(
                            OutboxRecord.status.in_(("queued", "deferred")),
                            OutboxRecord.next_attempt_at <= now,
                        ),
                    ),
                    OutboxRecord.attempt_count >= self.settings.max_attempts,
                )
                .order_by(OutboxRecord.lease_until, OutboxRecord.id)
                .limit(32)
                .with_for_update(skip_locked=True)
            )
        )
        for row in exhausted:
            row.status, row.failure_code, row.completed_at = "failed", "PREPARATION_ATTEMPTS_EXHAUSTED", now
            row.generation += 1
            row.lease_owner = row.lease_until = None
            await self.outbox.save(row)
        ready = or_(
            and_(OutboxRecord.status.in_(("queued", "deferred")), OutboxRecord.next_attempt_at <= now),
            and_(OutboxRecord.status == "preparing", OutboxRecord.lease_until <= now),
        )
        row = await session.scalar(
            select(OutboxRecord)
            .where(ready, OutboxRecord.attempt_count < self.settings.max_attempts)
            .order_by(OutboxRecord.next_attempt_at, OutboxRecord.id)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        if row is None:
            return None
        now = await self.outbox.clock()
        row.status, row.lease_owner = "preparing", owner
        row.lease_until = now + timedelta(seconds=self.settings.lease_seconds)
        row.generation += 1
        row.attempt_count += 1
        row.last_attempt_at = now
        row.completed_at = None
        await self.outbox.save(row)
        return DeliveryTicket(row.id, row.generation, owner, row.payload_ciphertext, row.payload_hash)

    def _match(self, ticket, status):
        return (
            OutboxRecord.id == ticket.id,
            OutboxRecord.generation == ticket.generation,
            OutboxRecord.lease_owner == ticket.owner,
            OutboxRecord.status == status,
            OutboxRecord.lease_until > self.outbox.clock_expression(),
        )

    async def _change(self, predicates, **values):
        session = self.outbox._require_session()
        return (
            await session.execute(
                update(OutboxRecord).where(*predicates).values(**values).returning(OutboxRecord.id)
            )
        ).scalar_one_or_none() is not None

    @transactional
    async def write_payload(self, ticket, ciphertext, payload_hash):
        if (
            not isinstance(ciphertext, str)
            or not 1 <= len(ciphertext) <= 2097152
            or not isinstance(payload_hash, str)
            or not re.fullmatch(r"[0-9a-f]{64}", payload_hash)
        ):
            raise ValueError("Use a bounded encrypted payload and SHA256 digest")
        first = (
            *self._match(ticket, "preparing"),
            OutboxRecord.payload_hash.is_(None),
            OutboxRecord.payload_ciphertext.is_(None),
        )
        if await self._change(first, payload_ciphertext=ciphertext, payload_hash=payload_hash):
            return True
        existing = await self.outbox._require_session().scalar(
            select(OutboxRecord.id).where(
                *self._match(ticket, "preparing"),
                OutboxRecord.payload_hash == payload_hash,
                OutboxRecord.payload_ciphertext.is_not(None),
            )
        )
        return existing is not None

    @transactional
    async def begin_send(self, ticket):
        return await self._change(
            (
                *self._match(ticket, "preparing"),
                OutboxRecord.payload_hash.is_not(None),
                OutboxRecord.payload_ciphertext.is_not(None),
            ),
            status="sending",
        )

    @transactional
    async def stop_preparation(self, ticket, status, *, failure_code):
        if status not in {"failed", "suppressed", "cancelled", "deferred"}:
            raise ValueError("Use a known pre-transport outcome")
        now = await self.outbox.clock()
        self._code(failure_code)
        return await self._change(
            self._match(ticket, "preparing"),
            status=status,
            failure_code=failure_code,
            completed_at=now if status != "deferred" else None,
            next_attempt_at=now + timedelta(seconds=60),
            lease_owner=None,
            lease_until=None,
        )

    @staticmethod
    def _code(value):
        if value is not None and (
            not isinstance(value, str) or not re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", value)
        ):
            raise ValueError("Use a redacted delivery outcome code")

    @transactional
    async def complete(self, ticket, status, *, failure_code=None, provider_reference=None):
        if status not in {"sent", "failed", "suppressed", "unknown"}:
            raise ValueError("Use a supported transport observation")
        self._code(failure_code)
        if provider_reference is not None and not re.fullmatch(r"[0-9a-f]{64}", provider_reference):
            raise ValueError("Retain only a provider correlation digest")
        return await self._change(
            self._match(ticket, "sending"),
            status=status,
            failure_code=failure_code,
            provider_reference=provider_reference,
            completed_at=await self.outbox.clock(),
            lease_owner=None,
            lease_until=None,
        )
