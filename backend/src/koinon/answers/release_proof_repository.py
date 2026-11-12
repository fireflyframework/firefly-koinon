# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Primary-transaction identity projection seam; never a canonical verifier.

The trusted publisher must flush, lock and run the original Python verifier
between capture and publish. These methods neither commit nor open another
connection. A capture grants no authority and contains no protected content.
"""

import json

from pyfly.container import repository
from pyfly.data.relational.sqlalchemy import Repository
from sqlalchemy import text

from koinon.answers.release_proof_dtos import (
    ReleaseProjectionClaim,
    ReleaseProjectionCursor,
    ReleaseProofCapture,
    ReleaseProofIdentity,
    ReleaseProofRequest,
)
from koinon.answers.release_proof_entities import AnswerReleaseProof


@repository(name="answers.release_proofs")
class AnswerReleaseProofRepository(Repository[AnswerReleaseProof, str]):
    async def capture(self, release_id: str) -> ReleaseProofCapture | None:
        value = await self._require_session().scalar(
            text("SELECT public.koinon_capture_release_proof(:release_id)"), {"release_id": release_id}
        )
        return ReleaseProofCapture.model_validate(value) if value is not None else None

    async def publish(
        self, capture: ReleaseProofCapture, *, worker_id: str, attempt: int
    ) -> ReleaseProofIdentity:
        value = await self._require_session().scalar(
            text("SELECT public.koinon_publish_release_proof(:release_id,:expected,:worker,:attempt)"),
            {
                "release_id": capture.header.release_result_id,
                "expected": capture.state_sha256,
                "worker": worker_id,
                "attempt": attempt,
            },
        )
        return ReleaseProofIdentity.model_validate(value)

    async def backfill(
        self, capture: ReleaseProofCapture, *, job_id: str, claim_token: str, job_revision: int
    ) -> ReleaseProofIdentity:
        value = await self._require_session().scalar(
            text("SELECT public.koinon_backfill_release_proof(:release_id,:expected,:job,:claim,:revision)"),
            {
                "release_id": capture.header.release_result_id,
                "expected": capture.state_sha256,
                "job": job_id,
                "claim": claim_token,
                "revision": job_revision,
            },
        )
        return ReleaseProofIdentity.model_validate(value)

    async def prepare_backfill(
        self, claim: ReleaseProjectionClaim, release_id: str
    ) -> ReleaseProofCapture | None:
        """Lock retained state before verification; caller owns fences and timeouts."""
        value = await self._require_session().scalar(
            text("SELECT public.koinon_prepare_release_backfill(:release_id,:job,:claim,:revision)"),
            {
                "release_id": release_id,
                "job": claim.job_id,
                "claim": claim.claim_token,
                "revision": claim.revision,
            },
        )
        return ReleaseProofCapture.model_validate(value) if value is not None else None

    async def compare(self, requests: tuple[ReleaseProofRequest, ...]) -> tuple[ReleaseProofIdentity, ...]:
        if len(requests) > 200 or len({r.release_result_id for r in requests}) != len(requests):
            raise ValueError("proof comparison requires at most 200 distinct releases")
        if not requests:
            return ()
        # One STABLE SQL statement is one MVCC snapshot even at READ COMMITTED.
        result = await self._require_session().execute(
            text("SELECT value FROM public.koinon_compare_release_proofs(CAST(:requests AS jsonb)) value"),
            {"requests": json.dumps([r.model_dump(mode="json") for r in requests])},
        )
        return tuple(ReleaseProofIdentity.model_validate(row[0]) for row in result)

    async def claim(
        self, job_id: str, *, claim_token: str, tenant_id: str | None = None
    ) -> ReleaseProjectionClaim:
        """Acquire in a short transaction and commit before any per-release work."""
        value = await self._require_session().scalar(
            text("SELECT public.koinon_claim_release_projection(:job,:claim,:tenant)"),
            {"job": job_id, "claim": claim_token, "tenant": tenant_id},
        )
        return ReleaseProjectionClaim.model_validate(value)

    async def candidates(
        self, claim: ReleaseProjectionClaim, *, limit: int = 25
    ) -> tuple[ReleaseProjectionCursor, ...]:
        if not 1 <= limit <= 25:
            raise ValueError("maintenance batches contain 1 to 25 releases")
        rows = await self._require_session().execute(
            text(
                "SELECT value FROM "
                "public.koinon_release_projection_candidates(:job,:claim,:revision,:limit) value"
            ),
            {"job": claim.job_id, "claim": claim.claim_token, "revision": claim.revision, "limit": limit},
        )
        return tuple(ReleaseProjectionCursor.model_validate(row[0]) for row in rows)

    async def checkpoint(
        self, claim: ReleaseProjectionClaim, cursor: ReleaseProjectionCursor, *, outcome: str
    ) -> ReleaseProjectionClaim:
        if outcome not in {"projected", "already_present", "invalid", "blocked"}:
            raise ValueError("unknown maintenance outcome")
        value = await self._require_session().scalar(
            text(
                "SELECT "
                "public.koinon_checkpoint_release_projection(:job,:claim,:revision,:release_id,:created_at,:outcome)"
            ),
            {
                "job": claim.job_id,
                "claim": claim.claim_token,
                "revision": claim.revision,
                "release_id": cursor.release_result_id,
                "created_at": cursor.created_at,
                "outcome": outcome,
            },
        )
        return ReleaseProjectionClaim.model_validate(value)
