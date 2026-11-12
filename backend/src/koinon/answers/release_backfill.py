# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Bounded offline integrity projection using isolated maintenance credentials."""

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
from time import monotonic
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from koinon.answers.configuration import AnswerProofProcess, verify_process_role
from koinon.answers.release_proof_dtos import ReleaseProofRequest
from koinon.answers.release_proof_repository import AnswerReleaseProofRepository
from koinon.answers.release_proofs import (
    InvalidRetainedRelease,
    ProjectionUnavailable,
    verify_persisted_release,
)


@dataclass(frozen=True)
class BackfillReport:
    job_id: str
    state: str
    processed: int
    projected: int
    invalid: int
    blocked: int
    elapsed_seconds: float
    retry_after_seconds: int
    classifications: tuple[dict, ...] = ()
    rollout_unprojected: tuple[str, ...] = ()
    rollout_more: bool = False


@dataclass(frozen=True)
class _CompletedAudit:
    """Read-only coverage cursor, deliberately without a reusable mutation claim."""

    job_id: str
    state: str = "complete"


class MaintenanceUnit:
    def __init__(self, session, *, audit=False):
        self.session = session
        self.repository = AnswerReleaseProofRepository(session=session)
        self.audit = audit
        self.classification = None

    async def acquire(self, job_id, tenant_id):
        if self.audit:
            completed = await self.session.scalar(
                text(
                    "SELECT job_id FROM public.koinon_answer_release_projection_jobs "
                    "WHERE job_id=:job AND projection_version=1 AND state='complete' "
                    "AND tenant_id IS NOT DISTINCT FROM :tenant"
                ),
                {"job": job_id, "tenant": tenant_id},
            )
            if completed is not None:
                return _CompletedAudit(completed)
        return await self.repository.claim(job_id, claim_token=uuid4().hex, tenant_id=tenant_id)

    async def candidates(self, claim, *, limit):
        return await self.repository.candidates(claim, limit=limit)

    async def blocked(self, claim, cursor):
        return await self.repository.checkpoint(claim, cursor, outcome="blocked")

    async def rollout_tail(self, claim):
        rows = (
            (
                await self.session.execute(
                    text(
                        "SELECT r.id FROM public.koinon_answer_release_projection_jobs j "
                        "JOIN public.koinon_chat_runs u ON j.tenant_id IS NULL OR u.tenant_id=j.tenant_id "
                        "JOIN public.koinon_chat_tool_results r ON r.run_id=u.id AND r.kind='answer_release' "
                        "WHERE j.job_id=:job AND j.projection_version=1 AND j.state='complete' AND "
                        "(j.high_water_release_id IS NULL OR (r.created_at,r.id)>"
                        "(j.high_water_created_at,j.high_water_release_id)) AND NOT EXISTS("
                        "SELECT FROM public.koinon_answer_release_proofs p WHERE p.release_result_id=r.id "
                        "AND p.projection_version=1) ORDER BY r.created_at,r.id LIMIT 26"
                    ),
                    {"job": claim.job_id},
                )
            )
            .scalars()
            .all()
        )
        return tuple(rows[:25]), len(rows) > 25

    async def process(self, claim, cursor):
        # Restricted preparation locks retained chat parents only. No provider or live access lookup.
        capture = await self.repository.prepare_backfill(claim, cursor.release_result_id)
        try:
            await verify_persisted_release(self.session, capture, release_id=cursor.release_result_id)
        except InvalidRetainedRelease:
            self.classification = "invalid_retained_binding"
            return await self.repository.checkpoint(claim, cursor, outcome="invalid"), "invalid"
        if capture is None:
            raise ProjectionUnavailable()
        already = await self.session.scalar(
            text(
                "SELECT EXISTS(SELECT FROM public.koinon_answer_release_proofs "
                "WHERE release_result_id=:release AND projection_version=1)"
            ),
            {"release": cursor.release_result_id},
        )
        if self.audit:
            header = capture.header
            matches = (
                await self.repository.compare(
                    (
                        ReleaseProofRequest(
                            tenant_id=header.tenant_id,
                            owner_subject=header.owner_subject,
                            thread_id=header.thread_id,
                            run_id=header.run_id,
                            message_id=header.message_id,
                            release_result_id=header.release_result_id,
                        ),
                    )
                )
                if already
                else ()
            )
            if not matches or matches[0].state_sha256 != capture.state_sha256:
                self.classification = "valid_release_missing_current_proof"
                return await self.repository.checkpoint(claim, cursor, outcome="blocked"), "blocked"
            self.classification = "verified" if header.provenance_complete else "provenance_incomplete"
            return await self.repository.checkpoint(
                claim, cursor, outcome="already_present"
            ), "already_present"
        await self.repository.backfill(
            capture, job_id=claim.job_id, claim_token=claim.claim_token, job_revision=claim.revision
        )
        self.classification = "verified" if capture.header.provenance_complete else "provenance_incomplete"
        outcome = "already_present" if already else "projected"
        return await self.repository.checkpoint(claim, cursor, outcome=outcome), outcome


class AnswerReleaseBackfill:
    def __init__(self, unit_factory, *, clock=monotonic, audit=False):
        self.unit_factory = unit_factory
        self.clock = clock
        self.audit = audit

    @classmethod
    def for_database(cls, session_factory, username, *, audit=False):
        @asynccontextmanager
        async def unit():
            async with session_factory() as session, session.begin():
                # SET LOCAL precedes preparation: setting a function-local timeout is too late.
                await session.execute(text("SET LOCAL lock_timeout = '1s'"))
                await session.execute(text("SET LOCAL statement_timeout = '5s'"))
                await verify_process_role(session, AnswerProofProcess("maintenance", username))
                yield MaintenanceUnit(session, audit=audit)

        return cls(unit, audit=audit)

    async def run(self, job_id, *, tenant_id=None):
        start = self.clock()
        async with asyncio.timeout(5):
            async with self.unit_factory() as unit:
                claim = await unit.acquire(job_id, tenant_id)
        processed = projected = invalid = blocked = 0
        classifications = []
        while claim.state != "complete" and processed < 25:
            remaining = 5 - (self.clock() - start)
            if remaining <= 0:
                break
            cursor = None
            try:
                async with asyncio.timeout(remaining):
                    async with self.unit_factory() as unit:
                        candidates = await unit.candidates(claim, limit=1)
                        if not candidates:
                            break
                        cursor = candidates[0]
                        claim, outcome = await unit.process(claim, cursor)
            except TimeoutError:
                # Cancellation rolls back this candidate; its committed cursor remains unchanged.
                break
            except (DBAPIError, ProjectionUnavailable):
                if cursor is None:
                    raise
                # The failed candidate unit has rolled back before its blocked checkpoint.
                remaining = 5 - (self.clock() - start)
                if remaining <= 0:
                    break
                try:
                    async with asyncio.timeout(remaining):
                        async with self.unit_factory() as unit:
                            claim = await unit.blocked(claim, cursor)
                except TimeoutError:
                    break
                outcome = "blocked"
            processed += 1
            projected += outcome == "projected"
            invalid += outcome == "invalid"
            blocked += outcome == "blocked"
            classifications.append(
                {
                    "release_result_id": cursor.release_result_id,
                    "classification": getattr(unit, "classification", None) or outcome,
                }
            )
            if claim.state == "blocked":
                break
        state = claim.state
        tail, more = (), False
        if self.audit and state == "complete":
            remaining = 5 - (self.clock() - start)
            if remaining <= 0:
                state = "coverage_pending"
            else:
                try:
                    async with asyncio.timeout(remaining):
                        async with self.unit_factory() as unit:
                            tail, more = await unit.rollout_tail(claim)
                    if tail or more:
                        state = "rollout_pending"
                except TimeoutError:
                    state = "coverage_pending"
        return BackfillReport(
            job_id,
            state,
            processed,
            projected,
            invalid,
            blocked,
            round(self.clock() - start, 6),
            0 if claim.state in {"complete", "blocked"} else 30,
            tuple(classifications),
            tail,
            more,
        )
