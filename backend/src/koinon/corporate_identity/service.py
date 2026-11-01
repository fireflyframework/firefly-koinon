# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime
from typing import cast, get_args
from uuid import uuid4

from pyfly.container import service
from pyfly.data.relational.sqlalchemy import LockMode, transactional
from pyfly.kernel import ConflictException, InvalidRequestException, ServiceUnavailableException

from koinon.catalog.dtos import Role
from koinon.catalog.errors import AccessDenied
from koinon.catalog.service import CatalogService
from koinon.corporate_identity.directory import NativeCorporateDirectory
from koinon.corporate_identity.dtos import (
    EntraSettings,
    IdentityProvider,
    IdentityProviderInput,
    IdentityProviderPatch,
    KeycloakSettings,
    ProviderKind,
    ProviderStatus,
)
from koinon.corporate_identity.entities import CorporateGrant, CorporateProvider
from koinon.corporate_identity.mappers import provider_dto
from koinon.corporate_identity.policy import CorporateIdentity, DirectorySnapshot, MappingRule, planned_grants
from koinon.corporate_identity.repositories import (
    CorporateGrantRepository,
    CorporateMappingRepository,
    CorporateProviderRepository,
    CorporateValidationRepository,
)
from koinon.corporate_identity.settings import IdentityCredentialStore
from koinon.security.authority import primary_authority
from koinon.security.settings import OidcSettings


@service(name="identity.service")
class CorporateIdentityService:
    def __init__(
        self,
        providers: CorporateProviderRepository,
        catalog: CatalogService,
        credentials: IdentityCredentialStore,
        oidc: OidcSettings,
        mappings: CorporateMappingRepository,
        grants: CorporateGrantRepository,
        validations: CorporateValidationRepository,
        directory: NativeCorporateDirectory,
    ):
        self.providers, self.catalog, self.credentials, self.oidc = providers, catalog, credentials, oidc
        self.mappings, self.grants, self.validations, self.directory = (
            mappings,
            grants,
            validations,
            directory,
        )

    def _configuration(self, kind, alias, settings):
        if isinstance(settings, EntraSettings) and settings.identity_mode == "direct":
            if (
                kind != "entra"
                or alias is not None
                or self.oidc.issuer != f"https://login.microsoftonline.com/{settings.tenant_id}/v2.0"
                or settings.client_id != self.oidc.client_id
            ):
                raise InvalidRequestException(
                    "Direct Entra must match the native tenant, issuer and client",
                    code="INVALID_IDENTITY_PROVIDER",
                )
            return
        if settings.kind != kind or (
            alias is None
            and (not isinstance(settings, KeycloakSettings) or settings.issuer != self.oidc.issuer)
        ):
            raise InvalidRequestException(
                "The corporate connection must preserve the configured broker issuer.",
                code="INVALID_IDENTITY_PROVIDER",
            )

    async def _row(self, tenant_id, identifier, *, lock=False):
        rows = await self.providers.find_all(id=identifier, tenant_id=tenant_id)
        if not rows:
            raise AccessDenied(
                "Corporate connection is unavailable in this organization.", code="ACCESS_DENIED"
            )
        row = (
            await self.providers.find_by_id(identifier, lock=LockMode.PESSIMISTIC_WRITE) if lock else rows[0]
        )
        if row.canonical_issuer != self.oidc.issuer:
            raise ServiceUnavailableException(
                "Corporate connection no longer matches the deployment issuer.",
                code="IDENTITY_ISSUER_CHANGED",
            )
        return row

    @transactional
    async def create(self, actor: str, tenant_id: str, body: IdentityProviderInput) -> IdentityProvider:
        await self.catalog._lock_tenant(tenant_id)
        await self.catalog.authorize(actor, tenant_id, "identity:manage")
        self._configuration(body.kind, body.broker_alias, body.settings)
        if body.credential_reference:
            raise ServiceUnavailableException(
                "Deployment credential references are not configured.",
                code="IDENTITY_CREDENTIAL_REFERENCE_UNAVAILABLE",
            )
        source = body.broker_alias or "@realm"
        if await self.providers.find_all(tenant_id=tenant_id, source_key=source):
            raise ConflictException(
                "This identity source is already registered in this organization.",
                code="IDENTITY_PROVIDER_EXISTS",
            )
        identifier = str(uuid4())
        now = datetime.now(UTC)
        ciphertext = (
            self.credentials.encrypt(tenant_id, identifier, body.credential) if body.credential else None
        )
        row = CorporateProvider(
            id=identifier,
            tenant_id=tenant_id,
            kind=body.kind,
            name=body.name,
            canonical_issuer=self.oidc.issuer,
            broker_alias=body.broker_alias,
            source_key=source,
            settings_json=body.settings.model_dump(mode="json"),
            secret_ciphertext=ciphertext,
            ownership="deployment" if body.broker_alias is None else "tenant",
            revision=1,
            policy_revision=1,
            status="draft",
            checks_json=[],
            created_by=actor,
            updated_by=actor,
            created_at=now,
            updated_at=now,
        )
        await self.providers.save(row)
        await self.catalog._audit(
            actor, tenant_id, "identity.provider.created", identifier, {"kind": row.kind}
        )
        return provider_dto(row)

    @primary_authority()
    async def get(self, actor: str, tenant_id: str, identifier: str) -> IdentityProvider:
        await self.catalog.authorize(actor, tenant_id, "identity:manage")
        return provider_dto(await self._row(tenant_id, identifier))

    @primary_authority()
    async def page(
        self, actor: str, tenant_id: str, *, q="", kind=None, status=None, page=1, page_size=25
    ) -> dict:
        await self.catalog.authorize(actor, tenant_id, "identity:manage")
        if (
            len(q) > 80
            or page < 1
            or not 1 <= page_size <= 100
            or (kind is not None and kind not in get_args(ProviderKind))
            or (status is not None and status not in get_args(ProviderStatus))
        ):
            raise InvalidRequestException(
                "Choose supported corporate connection filters.", code="INVALID_IDENTITY_FILTER"
            )
        result = await self.providers.page(
            tenant_id, q=q, kind=kind, status=status, page=page, page_size=page_size
        )
        return {**result, "items": [provider_dto(row).model_dump(mode="json") for row in result["items"]]}

    @transactional
    async def update(
        self, actor: str, tenant_id: str, identifier: str, body: IdentityProviderPatch
    ) -> IdentityProvider:
        await self.catalog._lock_tenant(tenant_id)
        await self.catalog.authorize(actor, tenant_id, "identity:manage")
        row = await self._row(tenant_id, identifier, lock=True)
        if row.revision != body.expected_revision:
            raise ConflictException(
                "This corporate connection changed. Reload it before saving.",
                code="IDENTITY_PROVIDER_CONFLICT",
            )
        if body.credential_reference:
            raise ServiceUnavailableException(
                "Deployment credential references are not configured.",
                code="IDENTITY_CREDENTIAL_REFERENCE_UNAVAILABLE",
            )
        fields = body.model_fields_set
        if body.settings is not None:
            self._configuration(row.kind, row.broker_alias, body.settings)
            row.settings_json = body.settings.model_dump(mode="json")
        if body.credential is not None and body.credential.kind != row.kind:
            raise InvalidRequestException(
                "Credentials must match the corporate provider.", code="INVALID_IDENTITY_PROVIDER"
            )
        if "credential" in fields:
            row.secret_ciphertext = (
                self.credentials.encrypt(tenant_id, identifier, body.credential) if body.credential else None
            )
            row.credential_reference = None
        elif "credential_reference" in fields:
            row.credential_reference = None
            row.secret_ciphertext = None
        if body.name is not None:
            row.name = body.name
        if fields & {"settings", "credential", "credential_reference"}:
            row.policy_revision += 1
            row.status = "draft"
            row.checks_json = []
            row.observed_at = None
        row.revision += 1
        row.updated_by, row.updated_at = actor, datetime.now(UTC)
        await self.providers.save(row)
        await self.catalog._audit(
            actor,
            tenant_id,
            "identity.provider.updated",
            identifier,
            {"revision": row.revision, "policy_revision": row.policy_revision},
        )
        return provider_dto(row)

    @transactional
    async def reconcile(
        self,
        provider_id: str,
        identity: CorporateIdentity,
        snapshot: DirectorySnapshot,
        *,
        expected_policy_revision: int,
    ) -> None:
        candidate = await self.providers.find_by_id(provider_id)
        if candidate is None:
            raise AccessDenied("Corporate connection is unavailable.", code="ACCESS_DENIED")
        await self.catalog._lock_tenant(candidate.tenant_id)
        provider = await self._row(candidate.tenant_id, provider_id, lock=True)
        if provider.status != "active" or provider.policy_revision != expected_policy_revision:
            raise ConflictException(
                "Corporate access policy changed. Obtain a fresh observation.", code="IDENTITY_POLICY_CHANGED"
            )
        if not identity.subject.startswith(provider.canonical_issuer + "|"):
            raise AccessDenied(
                "Corporate identity belongs to another issuer.", code="IDENTITY_PROVIDER_MISMATCH"
            )
        mappings = await self.mappings.find_all(provider_id=provider_id, tenant_id=provider.tenant_id)
        rules = [
            MappingRule(row.id, row.group_id, cast(Role, row.role), row.workspace_id, row.enabled)
            for row in mappings
        ]
        selected = planned_grants(
            rules,
            snapshot,
            expected_subject=identity.external_subject,
            now=datetime.now(UTC),
            max_age_seconds=self.credentials.settings.snapshot_ttl_seconds,
        )
        wanted = {rule.id for rule in selected}
        existing = await self.grants.find_all(
            provider_id=provider_id, subject=identity.subject, tenant_id=provider.tenant_id
        )
        by_mapping = {row.mapping_id: row for row in existing}
        for row in existing:
            if row.mapping_id not in wanted and row.active:
                row.active = False
                await self.grants.save(row)
        for rule in selected:
            mapping = next(row for row in mappings if row.id == rule.id)
            row = by_mapping.get(rule.id) or CorporateGrant(
                id=str(uuid4()),
                tenant_id=provider.tenant_id,
                provider_id=provider.id,
                mapping_id=rule.id,
                subject=identity.subject,
                external_subject=identity.external_subject,
            )
            row.workspace_id, row.role = rule.workspace_id, rule.role
            row.policy_revision, row.mapping_revision = provider.policy_revision, mapping.revision
            row.active = True
            row.observed_at, row.expires_at = snapshot.observed_at, snapshot.expires_at
            await self.grants.save(row)
        await self.catalog._audit(
            identity.subject,
            provider.tenant_id,
            "identity.grants.reconciled",
            provider.id,
            {"active_grants": len(wanted), "policy_revision": provider.policy_revision},
        )

    @transactional
    async def disable(
        self, actor: str, tenant_id: str, identifier: str, *, expected_revision: int
    ) -> IdentityProvider:
        await self.catalog._lock_tenant(tenant_id)
        await self.catalog.authorize(actor, tenant_id, "identity:manage")
        row = await self._row(tenant_id, identifier, lock=True)
        if row.revision != expected_revision:
            raise ConflictException(
                "This corporate connection changed. Reload it before disabling.",
                code="IDENTITY_PROVIDER_CONFLICT",
            )
        row.status = "disabled"
        row.revision += 1
        row.policy_revision += 1
        row.updated_by, row.updated_at = actor, datetime.now(UTC)
        await self.providers.save(row)
        await self.catalog._audit(
            actor,
            tenant_id,
            "identity.provider.disabled",
            identifier,
            {"policy_revision": row.policy_revision},
        )
        return provider_dto(row)

    async def _directory_session(self, row):
        from pydantic import TypeAdapter

        from koinon.corporate_identity.dtos import ProviderSettings

        settings = TypeAdapter(ProviderSettings).validate_python(row.settings_json)
        credential = (
            self.credentials.decrypt(row.tenant_id, row.id, row.secret_ciphertext)
            if row.secret_ciphertext
            else None
        )
        return settings, await self.directory.acquire(settings, credential)

    @primary_authority()
    async def groups(self, actor, tenant_id, identifier, *, q="", limit=25, after=""):
        if len(q) > 80 or not 1 <= limit <= 50 or len(after) > 16384:
            raise InvalidRequestException(
                "Choose supported directory filters.", code="INVALID_IDENTITY_FILTER"
            )
        await self.catalog.authorize(actor, tenant_id, "identity:manage")
        row = await self._row(tenant_id, identifier)
        settings, token = await self._directory_session(row)
        page = await self.directory.groups(settings, token, q=q, limit=limit, after=after)
        return {**page, "items": [{**group, "provider_id": row.id} for group in page["items"]]}

    @primary_authority()
    async def list_mappings(
        self, actor, tenant_id, identifier, *, q="", status="all", workspace_id=None, page=1, page_size=25
    ):
        if (
            len(q) > 80
            or status not in {"all", "enabled", "disabled"}
            or page < 1
            or not 1 <= page_size <= 100
        ):
            raise InvalidRequestException(
                "Choose supported access mapping filters.", code="INVALID_IDENTITY_FILTER"
            )
        await self.catalog.authorize(actor, tenant_id, "identity:manage")
        await self._row(tenant_id, identifier)
        await self.catalog._validate_workspace(tenant_id, workspace_id)
        result = await self.mappings.page(
            tenant_id,
            identifier,
            q=q,
            status=status,
            workspace_id=workspace_id,
            page=page,
            page_size=page_size,
        )
        return {**result, "items": [self._mapping_dto(row) for row in result["items"]]}

    @staticmethod
    def _mapping_dto(row):
        from koinon.corporate_identity.dtos import IdentityMapping

        return IdentityMapping.model_validate(
            {field: getattr(row, field) for field in IdentityMapping.model_fields}
        ).model_dump(mode="json")

    @transactional
    async def save_mapping(self, actor, tenant_id, identifier, body, mapping_id=None):
        from koinon.corporate_identity.entities import CorporateMapping

        await self.catalog._lock_tenant(tenant_id)
        await self.catalog.authorize(actor, tenant_id, "identity:manage")
        provider = await self._row(tenant_id, identifier, lock=True)
        await self.catalog._validate_workspace(tenant_id, body.workspace_id)
        existing = await self.mappings.find_all(provider_id=identifier, tenant_id=tenant_id)
        row = next((row for row in existing if row.id == mapping_id), None)
        if mapping_id is not None and (row is None or row.revision != body.expected_revision):
            raise ConflictException(
                "This access mapping changed. Reload it before saving.", code="IDENTITY_MAPPING_CONFLICT"
            )
        if any(
            row.id != mapping_id and row.group_id == body.group_id and row.workspace_id == body.workspace_id
            for row in existing
        ):
            raise ConflictException(
                "This group already has a mapping in this scope.", code="IDENTITY_MAPPING_EXISTS"
            )
        if row is None and len(existing) >= 100:
            raise InvalidRequestException(
                "A corporate connection supports up to 100 explicit access mappings.",
                code="IDENTITY_MAPPING_LIMIT",
            )
        settings, token = await self._directory_session(provider)
        group = await self.directory.group(settings, token, body.group_id)
        row = row or CorporateMapping(
            id=str(uuid4()), tenant_id=tenant_id, provider_id=identifier, revision=0
        )
        row.group_id, row.group_name = group["id"], group["name"]
        row.role, row.workspace_id, row.enabled = body.role, body.workspace_id, body.enabled
        row.revision += 1
        await self.mappings.save(row)
        # Mapping edits invalidate managed grants until the new policy has passed a fresh proof.
        provider.policy_revision += 1
        provider.revision += 1
        provider.status, provider.checks_json = "draft", []
        await self.providers.save(provider)
        await self.catalog._audit(
            actor, tenant_id, "identity.mapping.saved", identifier, {"mapping_id": row.id, "role": row.role}
        )
        return self._mapping_dto(row)

    @transactional
    async def remove_mapping(self, actor, tenant_id, identifier, mapping_id, expected_revision):
        await self.catalog._lock_tenant(tenant_id)
        await self.catalog.authorize(actor, tenant_id, "identity:manage")
        provider = await self._row(tenant_id, identifier, lock=True)
        rows = await self.mappings.find_all(id=mapping_id, provider_id=identifier, tenant_id=tenant_id)
        if not rows or rows[0].revision != expected_revision:
            raise ConflictException(
                "Reload the access mapping before removing it.", code="IDENTITY_MAPPING_CONFLICT"
            )
        row = rows[0]
        row.enabled, row.revision = False, row.revision + 1
        await self.mappings.save(row)
        provider.policy_revision, provider.revision = provider.policy_revision + 1, provider.revision + 1
        provider.status, provider.checks_json = "draft", []
        await self.providers.save(provider)
        await self.catalog._audit(
            actor, tenant_id, "identity.mapping.disabled", identifier, {"mapping_id": row.id}
        )

    @transactional
    async def activate(self, actor, tenant_id, identifier, body):
        await self.catalog._lock_tenant(tenant_id)
        await self.catalog.authorize(actor, tenant_id, "identity:manage")
        row = await self._row(tenant_id, identifier, lock=True)
        proof = await self.validations.find_by_id(body.validation_id, lock=LockMode.PESSIMISTIC_WRITE)
        if (
            row.revision != body.expected_revision
            or proof is None
            or proof.provider_id != row.id
            or proof.tenant_id != tenant_id
            or proof.requested_by != actor
            or proof.status != "verified"
            or proof.revision != row.revision
            or proof.policy_revision != row.policy_revision
            or proof.expires_at <= datetime.now(UTC)
        ):
            raise ConflictException(
                "Complete a fresh sign-in test of this exact connection before activating it.",
                code="IDENTITY_TEST_REQUIRED",
            )
        passed = {
            check["id"]
            for check in proof.checks_json
            if check.get("status") == "passed" and check.get("verified") is True
        }
        if not {"fresh_sso", "directory", "broker_policy"} <= passed:
            raise ConflictException(
                "Resolve the failed or unverified checks before activating corporate access.",
                code="IDENTITY_CHECKS_REQUIRED",
            )
        recovery = await self.catalog.membership_repository.find_all(
            tenant_id=tenant_id, workspace_id=None, role="admin", active=True
        )
        if not recovery:
            raise ConflictException(
                "Keep a manual organization administrator for recovery.", code="IDENTITY_RECOVERY_REQUIRED"
            )
        if not await self.mappings.find_all(provider_id=identifier, tenant_id=tenant_id, enabled=True):
            raise ConflictException(
                "Add an explicit group-to-role mapping before activating corporate access.",
                code="IDENTITY_MAPPING_REQUIRED",
            )
        proof.status = "consumed"
        await self.validations.save(proof)
        row.status, row.revision = "active", row.revision + 1
        row.updated_at, row.updated_by = datetime.now(UTC), actor
        await self.providers.save(row)
        await self.catalog._audit(
            actor,
            tenant_id,
            "identity.provider.activated",
            identifier,
            {"policy_revision": row.policy_revision},
        )
        return provider_dto(row)
