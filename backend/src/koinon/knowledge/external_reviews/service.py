# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import hashlib
import secrets
from datetime import UTC, datetime

from pyfly.container import service
from pyfly.data.relational.sqlalchemy import LockMode, transactional
from pyfly.kernel import ConflictException, InvalidRequestException

from koinon.catalog.errors import AccessDenied
from koinon.knowledge.curated.authority import digest
from koinon.knowledge.curated.dtos import KnowledgeCommitOutcome, KnowledgeConfirmation
from koinon.knowledge.curated.intents import KnowledgeIntents
from koinon.knowledge.external_reviews.approval import admitted_approval
from koinon.knowledge.external_reviews.dtos import (
    ExternalReviewChallenge,
    ExternalReviewDecision,
    ExternalReviewInput,
    ExternalReviewView,
)
from koinon.knowledge.external_reviews.entities import ExternalReviewRow
from koinon.knowledge.external_reviews.repositories import ExternalReviewRepository
from koinon.tokens.authorization import TokenRestriction
from koinon.tokens.entities import PersonalToken


def fingerprint(grant: PersonalToken) -> str:
    return digest(
        {
            name: getattr(grant, name)
            for name in (
                "id",
                "subject",
                "tenant_id",
                "purpose",
                "authorized_application_id",
                "scopes",
                "workspace_ids",
                "asset_ids",
                "resource_ids",
            )
        }
        | {"expires_at": grant.expires_at.isoformat()}
    )


def key(value: object) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= 128 or not value.strip():
        raise InvalidRequestException(
            "Provide an Idempotency-Key of at most 128 characters",
            code="EXTERNAL_REVIEW_IDEMPOTENCY_REQUIRED",
        )
    return value


@service(name="knowledge.external_reviews.service")
class ExternalKnowledgeReviews:
    def __init__(
        self, reviews: ExternalReviewRepository, intents: KnowledgeIntents, tokens: TokenRestriction
    ):
        self.reviews, self.intents, self.tokens = reviews, intents, tokens

    async def grant(self, subject: str, tenant_id: str) -> PersonalToken:
        grant = await self.tokens.grant(subject)
        if grant is None or grant.tenant_id != tenant_id:
            raise AccessDenied("An active external credential is required", code="TOKEN_UNAVAILABLE")
        return grant

    async def load(self, subject: str, tenant_id: str, identifier: str, *, lock=False) -> ExternalReviewRow:
        grant = await self.grant(subject, tenant_id)
        row = await self.reviews.find_by_id(identifier, lock=LockMode.PESSIMISTIC_WRITE if lock else None)
        if row is None or (
            row.subject,
            row.tenant_id,
            row.credential_id,
            row.application_id,
            row.credential_sha256,
        ) != (subject, tenant_id, grant.id, grant.authorized_application_id, fingerprint(grant)):
            raise AccessDenied(
                "This private external review is unavailable", code="EXTERNAL_REVIEW_UNAVAILABLE"
            )
        return row

    async def view(self, subject: str, tenant_id: str, row: ExternalReviewRow) -> ExternalReviewView:
        preview = await self.intents.get(subject, tenant_id, row.id)
        if preview.destination.workspace_id != row.workspace_id:
            raise AccessDenied("The review workspace changed", code="EXTERNAL_REVIEW_UNAVAILABLE")
        return ExternalReviewView(id=row.id, review=preview, status=preview.status, expires_at=row.expires_at)

    @transactional
    async def stage(
        self, subject: str, tenant_id: str, values: object, request_key: str
    ) -> ExternalReviewView:
        request_key = key(request_key)
        request = ExternalReviewInput.model_validate(values)
        intent = request.intent()
        grant = await self.grant(subject, tenant_id)
        request_sha = digest(request.model_dump(mode="json"))
        existing = await self.reviews.find_all(
            tenant_id=tenant_id, subject=subject, credential_id=grant.id, stage_key=request_key
        )
        if existing:
            row = await self.load(subject, tenant_id, existing[0].id, lock=True)
            if row.request_sha256 != request_sha:
                raise ConflictException(
                    "This key already identifies another proposal",
                    code="EXTERNAL_REVIEW_IDEMPOTENCY_CONFLICT",
                )
            return await self.view(subject, tenant_id, row)
        preview = await self.intents.preview(subject, tenant_id, intent.model_dump(mode="json"))
        row = ExternalReviewRow(
            id=preview.id,
            tenant_id=tenant_id,
            subject=subject,
            workspace_id=preview.destination.workspace_id,
            credential_id=grant.id,
            application_id=grant.authorized_application_id,
            credential_sha256=fingerprint(grant),
            stage_key=request_key,
            request_sha256=request_sha,
            revision=preview.revision,
            authorization_digest=preview.authorization_digest,
            status="preview",
            created_at=preview.created_at,
            expires_at=preview.expires_at,
        )
        return await self.view(subject, tenant_id, await self.reviews.save(row))

    async def get(self, subject: str, tenant_id: str, identifier: str) -> ExternalReviewView:
        return await self.view(subject, tenant_id, await self.load(subject, tenant_id, identifier))

    @transactional
    async def challenge(self, subject: str, tenant_id: str, identifier: str) -> ExternalReviewChallenge:
        row = await self.load(subject, tenant_id, identifier, lock=True)
        self.fresh(row)
        view = await self.view(subject, tenant_id, row)
        if view.status != "preview":
            raise ConflictException("Review a fresh proposal", code="EXTERNAL_REVIEW_NOT_PENDING")
        nonce = secrets.token_urlsafe(32)
        row.nonce_sha256 = hashlib.sha256(nonce.encode()).hexdigest()
        await self.reviews.save(row)
        return ExternalReviewChallenge(review=view, nonce=nonce)

    def fresh(self, row: ExternalReviewRow) -> None:
        if row.status != "preview" or row.expires_at <= datetime.now(UTC):
            raise ConflictException("Review a fresh proposal", code="EXTERNAL_REVIEW_EXPIRED")

    def decision(self, row: ExternalReviewRow, values: object) -> ExternalReviewDecision:
        decision = ExternalReviewDecision.model_validate(values)
        if (decision.expected_revision, decision.authorization_digest) != (
            row.revision,
            row.authorization_digest,
        ):
            raise ConflictException("Approve the exact reviewed change", code="EXTERNAL_REVIEW_CHANGED")
        if not row.nonce_sha256 or not secrets.compare_digest(
            row.nonce_sha256, hashlib.sha256(decision.nonce.encode()).hexdigest()
        ):
            raise AccessDenied("Use the private application review", code="EXTERNAL_REVIEW_NONCE_INVALID")
        return decision

    @transactional
    async def admit(self, subject, tenant_id, identifier, values, request_key):
        request_key = key(request_key)
        row = await self.load(subject, tenant_id, identifier, lock=True)
        if row.status not in {"preview", "approved"}:
            self.fresh(row)
        self.decision(row, values)
        if row.status == "approved":
            if row.confirmation_key != request_key:
                raise ConflictException(
                    "Reuse the original approval key", code="EXTERNAL_REVIEW_IDEMPOTENCY_CONFLICT"
                )
        else:
            self.fresh(row)
            row.status, row.confirmation_key = "approved", request_key
            row.decided_at = datetime.now(UTC)
        approval = admitted_approval(row)
        confirmation = KnowledgeConfirmation(
            confirm=True, expected_revision=row.revision, authorization_digest=row.authorization_digest
        )
        await self.intents.admit(
            subject, tenant_id, row.id, confirmation, request_key, _external_approval=approval
        )
        await self.reviews.save(row)
        return approval, confirmation

    async def approve(
        self, subject: str, tenant_id: str, identifier: str, values: object, request_key: str
    ) -> KnowledgeCommitOutcome:
        approval, confirmation = await self.admit(subject, tenant_id, identifier, values, request_key)
        return await self.intents.confirm(
            subject,
            tenant_id,
            identifier,
            confirmation.model_dump(mode="json"),
            request_key,
            _external_approval=approval,
        )

    @transactional
    async def cancel(
        self, subject: str, tenant_id: str, identifier: str, values: object
    ) -> ExternalReviewView:
        row = await self.load(subject, tenant_id, identifier, lock=True)
        self.decision(row, values)
        if row.status == "cancelled":
            return await self.view(subject, tenant_id, row)
        self.fresh(row)
        await self.intents.cancel(
            subject, tenant_id, identifier, row.revision, _external_approval=admitted_approval(row)
        )
        row.status, row.decided_at = "cancelled", datetime.now(UTC)
        await self.reviews.save(row)
        return await self.view(subject, tenant_id, row)
