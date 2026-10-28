# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from pydantic import TypeAdapter
from pyfly.container import service
from pyfly.data.relational.sqlalchemy import LockMode, Propagation, transactional

from koinon.catalog.entities import AuditEvent
from koinon.catalog.repositories import AuditRepository
from koinon.corporate_identity.challenges import policy
from koinon.corporate_identity.directory import NativeCorporateDirectory
from koinon.corporate_identity.dtos import ProviderSettings
from koinon.corporate_identity.entities import CorporateGrant
from koinon.corporate_identity.policy import MappingRule, planned_grants, verified_identity
from koinon.corporate_identity.repositories import (
    CorporateGrantRepository,
    CorporateMappingRepository,
    CorporateProviderRepository,
)
from koinon.corporate_identity.settings import IdentityCredentialStore
from koinon.security.settings import OidcSettings


@service(name="identity.refresh")
class CorporateAccessRefresh:
    def __init__(
        self,
        providers: CorporateProviderRepository,
        mappings: CorporateMappingRepository,
        grants: CorporateGrantRepository,
        directory: NativeCorporateDirectory,
        credentials: IdentityCredentialStore,
        audit: AuditRepository,
        oidc: OidcSettings,
    ):
        self.providers, self.mappings, self.grants = providers, mappings, grants
        self.directory, self.credentials, self.audit, self.oidc = directory, credentials, audit, oidc

    async def login(self, context):
        claims = context.attributes
        alias = claims.get("koinon_identity_provider")
        rows = await self.providers.find_all(
            canonical_issuer=self.oidc.issuer, broker_alias=alias, status="active"
        )
        for provider in rows:
            identity = verified_identity(policy(provider), claims)
            await self.observe(provider.id, identity.subject, identity.external_subject)

    async def subject(self, subject):
        rows = await self.grants.find_all(subject=subject)
        for provider_id in dict.fromkeys(row.provider_id for row in rows):
            provider_rows = [row for row in rows if row.provider_id == provider_id]
            provider = await self.providers.find_by_id(provider_id)
            if provider is None or provider.status != "active":
                continue
            if all(
                row.expires_at > datetime.now(UTC) and row.policy_revision == provider.policy_revision
                for row in provider_rows
            ):
                continue
            external_subjects = {row.external_subject for row in provider_rows}
            if len(external_subjects) == 1:
                await self.observe(provider_id, subject, external_subjects.pop())

    # Policy observations must persist independently of a caller's read-only or rolled-back business unit.
    @transactional(propagation=Propagation.REQUIRES_NEW)
    async def observe(self, provider_id, subject, external_subject):
        provider = await self.providers.find_by_id(provider_id, lock=LockMode.PESSIMISTIC_WRITE)
        if provider is None or provider.status != "active" or provider.canonical_issuer != self.oidc.issuer:
            return
        mappings = await self.mappings.find_all(provider_id=provider.id, tenant_id=provider.tenant_id)
        existing = await self.grants.find_all(
            provider_id=provider.id, tenant_id=provider.tenant_id, subject=subject
        )
        now = datetime.now(UTC)
        # One provider row serializes competing refreshes; a waiting reader reuses the completed observation.
        if any(
            row.active and row.expires_at > now and row.policy_revision == provider.policy_revision
            for row in existing
        ):
            return
        rules = [
            MappingRule(row.id, row.group_id, row.role, row.workspace_id, row.enabled) for row in mappings
        ]
        try:
            settings = TypeAdapter(ProviderSettings).validate_python(provider.settings_json)
            credential = (
                self.credentials.decrypt(provider.tenant_id, provider.id, provider.secret_ciphertext)
                if provider.secret_ciphertext
                else None
            )
            token = await self.directory.acquire(settings, credential)
            snapshot = await self.directory.observe(settings, token, external_subject)
            selected = planned_grants(
                rules,
                snapshot,
                expected_subject=external_subject,
                now=datetime.now(UTC),
                max_age_seconds=self.credentials.settings.snapshot_ttl_seconds,
            )
        except Exception:
            for row in existing:
                row.active = False
                row.observed_at = datetime.now(UTC)
                row.expires_at = row.observed_at + timedelta(seconds=15)
                row.policy_revision = provider.policy_revision
                await self.grants.save(row)
            await self.audit.save(
                AuditEvent(
                    id=str(uuid4()),
                    tenant_id=provider.tenant_id,
                    subject=subject,
                    action="identity.directory.unavailable",
                    resource_id=provider.id,
                    details={"policy_revision": provider.policy_revision},
                )
            )
            return
        wanted = {rule.id for rule in selected}
        by_mapping = {row.mapping_id: row for row in existing}
        for row in existing:
            if row.mapping_id not in wanted:
                row.active = False
                row.observed_at, row.expires_at = snapshot.observed_at, snapshot.expires_at
                row.policy_revision = provider.policy_revision
                await self.grants.save(row)
        for rule in selected:
            mapping = next(row for row in mappings if row.id == rule.id)
            row = by_mapping.get(rule.id) or CorporateGrant(
                id=str(uuid4()),
                tenant_id=provider.tenant_id,
                provider_id=provider.id,
                mapping_id=rule.id,
                subject=subject,
                external_subject=external_subject,
            )
            row.workspace_id, row.role, row.active = rule.workspace_id, rule.role, True
            row.policy_revision, row.mapping_revision = provider.policy_revision, mapping.revision
            row.observed_at, row.expires_at = snapshot.observed_at, snapshot.expires_at
            await self.grants.save(row)
        await self.audit.save(
            AuditEvent(
                id=str(uuid4()),
                tenant_id=provider.tenant_id,
                subject=subject,
                action="identity.grants.refreshed",
                resource_id=provider.id,
                details={"active_grants": len(selected), "policy_revision": provider.policy_revision},
            )
        )
