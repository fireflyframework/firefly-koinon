# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import asyncio
import hashlib
from datetime import UTC, datetime

from pydantic import ValidationError
from pyfly.container import service
from pyfly.core import Config
from pyfly.data.relational.sqlalchemy import transactional
from pyfly.kernel import ConflictException, ServiceUnavailableException
from pyfly.kernel.exceptions import ValidationException

from koinon.catalog.errors import AccessDenied
from koinon.catalog.service import CatalogService
from koinon.organization_branding.dtos import (
    BrandingResetInput,
    BrandingValues,
    OrganizationBranding,
    OrganizationBrandingInput,
    encode_branding,
)
from koinon.organization_branding.repositories import OrganizationBrandingRepository

_READ = frozenset({
    "catalog:read", "knowledge:search", "query:execute", "chat:use", "settings:write",
    "exports:write", "shares:write",
})


@service(name="organization_branding.service")
class OrganizationBrandingService:
    def __init__(self, catalog: CatalogService, settings: OrganizationBrandingRepository, config: Config):
        self.catalog, self.settings = catalog, settings
        self.defaults = BrandingValues.model_validate(config.get("koinon.branding", {}))
        self._validation_slots = asyncio.Semaphore(2)

    async def _authorize_read(self, subject, tenant_id):
        memberships = await self.catalog.memberships(subject)
        restriction = self.catalog.restriction
        grant = await restriction.grant(subject) if restriction else None
        workspaces = {row.workspace_id for row in memberships if row.tenant_id == tenant_id}
        if grant is not None:
            if grant.tenant_id != tenant_id:
                raise AccessDenied("Organization branding is unavailable", code="ACCESS_DENIED")
            if grant.workspace_ids is not None:
                workspaces = set(grant.workspace_ids)
            if grant.asset_ids is not None:
                workspaces = set()
                for asset_id in grant.asset_ids:
                    entry = await self.catalog.catalog_repository.find_by_id(asset_id)
                    if entry is not None and entry.tenant_id == tenant_id:
                        if restriction is not None:
                            await restriction.resource(subject, entry)
                        workspaces.add(entry.workspace_id)
        for workspace in workspaces:
            if self.catalog._resolved_permissions(memberships, tenant_id, workspace, grant) & _READ:
                await self.catalog._validate_workspace(tenant_id, workspace)
                return
        raise AccessDenied("Organization branding is unavailable", code="ACCESS_DENIED")

    def _decode(self, tenant_id, revision, payload):
        try:
            branding = (
                BrandingValues.model_validate_json(payload)
                if payload
                else self.defaults
            )
            return OrganizationBranding(
                tenant_id=tenant_id,
                revision=revision,
                origin="organization" if payload else "deployment",
                branding=branding,
            )
        except ValueError:
            raise ServiceUnavailableException(
                "Organization branding is outside the supported contract", code="BRANDING_UNAVAILABLE"
            ) from None

    async def _view(self, tenant_id, row):
        revision, payload = (row.revision, row.branding_json) if row else (0, None)
        return await self._offload(self._decode, tenant_id, revision, payload)

    async def _offload(self, operation, *arguments):
        await self._validation_slots.acquire()
        try:
            task = asyncio.create_task(asyncio.to_thread(operation, *arguments))
        except BaseException:
            self._validation_slots.release()
            raise

        def finished(value):
            self._validation_slots.release()
            if not value.cancelled():
                value.exception()

        task.add_done_callback(finished)
        return await asyncio.shield(task)

    @transactional(read_only=True)
    async def get(self, subject, tenant_id) -> OrganizationBranding:
        await self._authorize_read(subject, tenant_id)
        return await self._view(tenant_id, await self.settings.current(tenant_id))

    @transactional(read_only=True)
    async def _authorize_write(self, subject, tenant_id):
        await self.catalog.authorize(subject, tenant_id, "settings:write")

    async def update(self, subject, tenant_id, values: OrganizationBrandingInput) -> OrganizationBranding:
        await self._authorize_write(subject, tenant_id)
        values = OrganizationBrandingInput.model_validate(values)
        try:
            branding = await self._offload(BrandingValues.model_validate, values.branding.model_dump())
        except ValidationError as error:
            errors = [
                {**item, "loc": ("branding", *item["loc"])}
                for item in error.errors(include_input=False, include_context=False, include_url=False)
            ]
            detail = "; ".join(
                f"{'.'.join(str(part) for part in item['loc'])}: {item['msg']}" for item in errors
            )
            raise ValidationException(
                "Validation failed: " + detail, code="VALIDATION_ERROR", context={"errors": errors}
            ) from None
        return await self._write(subject, tenant_id, values.expected_revision, branding)

    @transactional
    async def reset(self, subject, tenant_id, expected_revision: int) -> OrganizationBranding:
        await self.catalog.authorize(subject, tenant_id, "settings:write")
        values = BrandingResetInput(expected_revision=expected_revision)
        return await self._write(subject, tenant_id, values.expected_revision, None)

    @transactional
    async def _write(self, subject, tenant_id, revision, branding):
        await self.catalog.authorize(subject, tenant_id, "settings:write")
        payload = encode_branding(branding) if branding is not None else None
        if not await self.settings.compare_and_swap(tenant_id, payload, revision, subject, datetime.now(UTC)):
            raise ConflictException(
                "Organization branding changed. Reload and try again.", code="ORGANIZATION_BRANDING_CHANGED"
            )
        # Audit references the configuration without retaining uploaded image bytes a second time.
        details = dict(revision=revision + 1, origin="organization" if payload else "deployment")
        if branding is not None and payload is not None:
            details["digest"] = hashlib.sha256(payload.encode("ascii")).hexdigest()
            details["product_name"] = branding.product_name
            details["assistant_name"] = branding.assistant_name
        await self.catalog._audit(
            subject,
            tenant_id,
            "organization_branding.updated" if payload else "organization_branding.reset",
            tenant_id,
            details,
        )
        return await self._view(tenant_id, await self.settings.current(tenant_id))
