# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from pydantic import TypeAdapter
from pyfly.container import service
from pyfly.data.relational.sqlalchemy import LockMode, transactional
from pyfly.kernel import ConflictException, SecurityException
from pyfly.security.context import SecurityContext

from koinon.catalog.errors import AccessDenied
from koinon.corporate_identity.broker import CorporateBrokerPolicy
from koinon.corporate_identity.directory import NativeCorporateDirectory
from koinon.corporate_identity.dtos import IdentityValidation, ProviderSettings
from koinon.corporate_identity.entities import CorporateValidation
from koinon.corporate_identity.policy import IdentityPolicy, verified_identity
from koinon.corporate_identity.repositories import CorporateValidationRepository
from koinon.corporate_identity.service import CorporateIdentityService
from koinon.security.authority import primary_authority


def policy(provider):
    settings = provider.settings_json
    return IdentityPolicy(
        provider.id,
        provider.kind,
        provider.canonical_issuer,
        provider.broker_alias,
        str(settings.get("tenant_id", "")),
        tuple(settings.get("hosted_domains", ())),
    )


def validation_dto(row, *, authorize=False):
    return IdentityValidation(
        id=row.id,
        candidate_revision=row.revision,
        expires_at=row.expires_at,
        status=row.status,
        checks=row.checks_json,
        authorization_url=f"/oauth2/authorization/koinon?identity_test={row.id}"
        if authorize and row.status == "pending"
        else None,
    )


@service(name="identity.challenges")
class CorporateLoginChallenges:
    def __init__(
        self,
        identities: CorporateIdentityService,
        validations: CorporateValidationRepository,
        directory: NativeCorporateDirectory,
        broker: CorporateBrokerPolicy,
    ):
        self.identities, self.validations, self.directory, self.broker = (
            identities,
            validations,
            directory,
            broker,
        )

    @transactional
    async def create(self, actor: str, tenant_id: str, provider_id: str, expected_revision: int):
        await self.identities.catalog._lock_tenant(tenant_id)
        await self.identities.catalog.authorize(actor, tenant_id, "identity:manage")
        provider = await self.identities._row(tenant_id, provider_id, lock=True)
        if provider.revision != expected_revision:
            raise ConflictException(
                "Reload this corporate connection before testing.", code="IDENTITY_PROVIDER_CONFLICT"
            )
        now = datetime.now(UTC)
        row = CorporateValidation(
            id=str(uuid4()),
            tenant_id=tenant_id,
            provider_id=provider_id,
            requested_by=actor,
            revision=provider.revision,
            policy_revision=provider.policy_revision,
            status="pending",
            checks_json=[],
            issued_at=now,
            expires_at=now + timedelta(minutes=5),
        )
        await self.validations.save(row)
        await self.identities.catalog._audit(
            actor, tenant_id, "identity.test.created", provider_id, {"validation_id": row.id}
        )
        return validation_dto(row, authorize=True)

    @primary_authority()
    async def get(self, actor, tenant_id, provider_id, identifier):
        await self.identities.catalog.authorize(actor, tenant_id, "identity:manage")
        row = await self.validations.find_by_id(identifier)
        if (
            row is None
            or row.tenant_id != tenant_id
            or row.provider_id != provider_id
            or row.requested_by != actor
        ):
            raise AccessDenied("Sign-in test is unavailable.", code="ACCESS_DENIED")
        return validation_dto(row)

    async def _pending(self, identifier, *, lock=False):
        row = await self.validations.find_by_id(identifier, lock=LockMode.PESSIMISTIC_WRITE if lock else None)
        if row is None or row.status != "pending" or row.expires_at <= datetime.now(UTC):
            raise SecurityException(
                "Sign-in test expired or is unavailable.", code="IDENTITY_TEST_UNAVAILABLE"
            )
        provider = await self.identities._row(row.tenant_id, row.provider_id)
        if provider.revision != row.revision or provider.policy_revision != row.policy_revision:
            raise SecurityException(
                "Corporate connection changed. Start a new sign-in test.", code="IDENTITY_TEST_STALE"
            )
        await self.identities.catalog.authorize(row.requested_by, row.tenant_id, "identity:manage")
        return row, provider

    @transactional
    async def begin_authorization(self, identifier: str, subject: str):
        row, provider = await self._pending(identifier, lock=True)
        if row.requested_by != subject or row.started_at is not None:
            raise SecurityException(
                "Start the test from the administrator who requested it.", code="IDENTITY_TEST_UNAVAILABLE"
            )
        row.started_at = datetime.now(UTC)
        await self.validations.save(row)
        return provider

    @transactional
    async def complete(self, identifier: str, context: SecurityContext):
        row, provider = await self._pending(identifier, lock=True)
        claims = context.attributes
        identity = verified_identity(policy(provider), claims)
        auth_time = claims.get("auth_time")
        now = datetime.now(UTC)
        if row.started_at is None:
            raise SecurityException(
                "Start a new sign-in test from this application.", code="IDENTITY_TEST_NOT_STARTED"
            )
        if identity.subject != row.requested_by or context.user_id != claims.get("sub"):
            raise SecurityException(
                "Sign in with the same verified administrator account.", code="IDENTITY_TEST_ACCOUNT_MISMATCH"
            )
        if type(auth_time) is not int:
            raise SecurityException(
                "The identity provider must include a verified numeric auth_time claim.",
                code="IDENTITY_AUTH_TIME_REQUIRED",
            )
        if auth_time < row.started_at.timestamp() - 3 or auth_time > now.timestamp() + 30:
            raise SecurityException(
                "Use a fresh sign-in with the same verified administrator account.",
                code="IDENTITY_FRESH_SIGN_IN_REQUIRED",
            )
        settings = TypeAdapter(ProviderSettings).validate_python(provider.settings_json)
        credential = (
            self.identities.credentials.decrypt(row.tenant_id, provider.id, provider.secret_ciphertext)
            if provider.secret_ciphertext
            else None
        )
        token = await self.directory.acquire(settings, credential)
        await self.directory.observe(settings, token, identity.external_subject)
        row.status, row.completed_at = "verified", now
        row.checks_json = [
            {
                "id": "fresh_sso",
                "status": "passed",
                "verified": True,
                "available": True,
                "message": (
                    "A fresh sign-in preserved the canonical account and matched this corporate source."
                ),
            },
            {
                "id": "directory",
                "status": "passed",
                "verified": True,
                "available": True,
                "message": "A complete directory membership observation was obtained.",
            },
            await self.broker.check(provider),
        ]
        await self.validations.save(row)
        provider.checks_json, provider.observed_at = row.checks_json, now
        await self.identities.providers.save(provider)
        await self.identities.catalog._audit(
            identity.subject,
            row.tenant_id,
            "identity.test.completed",
            provider.id,
            {"validation_id": row.id, "policy_revision": row.policy_revision},
        )
