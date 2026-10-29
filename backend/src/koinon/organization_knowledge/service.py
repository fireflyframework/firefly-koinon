# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime

from flycanon.config import CanonSettings
from flyquery.config import FlyquerySettings
from pydantic import BaseModel, ValidationError
from pyfly.container import Provider, service
from pyfly.data.relational.sqlalchemy import transactional
from pyfly.kernel import ConflictException, ServiceUnavailableException

from koinon.catalog.errors import AccessDenied
from koinon.catalog.service import CatalogService
from koinon.organization_knowledge.dtos import (
    DocumentKnowledgeBounds,
    DocumentKnowledgeSettings,
    OrganizationKnowledgeCapabilities,
    OrganizationKnowledgeSettings,
    OrganizationKnowledgeSettingsInput,
    OrganizationKnowledgeSnapshot,
    StructuredKnowledgeBounds,
    StructuredKnowledgeSettings,
    snapshot_digest,
)
from koinon.organization_knowledge.repositories import OrganizationKnowledgeRepository

_READ = frozenset({"settings:write", "knowledge:search", "query:execute", "chat:use"})


def numeric_bounds(policy: type[BaseModel], bounds: type[BaseModel]) -> dict:
    properties = policy.model_json_schema()["properties"]
    return {
        name: {"minimum": properties[name]["minimum"], "maximum": properties[name]["maximum"]}
        for name in bounds.model_fields
    }


def capabilities() -> OrganizationKnowledgeCapabilities:
    return OrganizationKnowledgeCapabilities.model_validate(
        {
            "documents": {
                "answer_modes": ["rag", "rlm"],
                "rlm_curated_knowledge_supported": False,
                "rlm_curated_knowledge_reason": "KNOWLEDGE_RLM_UNQUALIFIED",
                "rlm_model_role": "documents.rlm",
                "rlm_recorded_views_required": True,
                "rlm_recorded_views_reason": "RLM_DOCUMENT_VIEWS_REQUIRED",
                "bounds": numeric_bounds(DocumentKnowledgeSettings, DocumentKnowledgeBounds),
            },
            "structured": {"bounds": numeric_bounds(StructuredKnowledgeSettings, StructuredKnowledgeBounds)},
        }
    )


@service(name="organization_knowledge.service")
class OrganizationKnowledgeService:
    def __init__(
        self,
        catalog: CatalogService,
        settings: OrganizationKnowledgeRepository,
        documents: Provider[CanonSettings | None],
        structured: Provider[FlyquerySettings | None],
    ):
        self.catalog, self.settings = catalog, settings
        self.documents, self.structured = documents, structured

    async def _authorize_read(self, subject, tenant_id):
        memberships = await self.catalog.memberships(subject)
        restriction = self.catalog.restriction
        grant = await restriction.grant(subject) if restriction else None
        workspaces = {row.workspace_id for row in memberships if row.tenant_id == tenant_id}
        if grant is not None:
            if grant.tenant_id != tenant_id:
                raise AccessDenied("Organization knowledge settings are unavailable", code="ACCESS_DENIED")
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
        raise AccessDenied("Organization knowledge settings are unavailable", code="ACCESS_DENIED")

    def _deployment(self):
        documents, structured = self.documents.get(), self.structured.get()
        if documents is None or structured is None:
            raise ServiceUnavailableException(
                "Native knowledge settings are unavailable", code="KNOWLEDGE_SETTINGS_UNAVAILABLE"
            )
        document_values = {
            name: getattr(documents, name)
            for name in DocumentKnowledgeSettings.model_fields
            if name not in {"answer_top_k", "rlm_extended_reasoning"}
        }
        # The canonical adapter historically supplies 10 hits and no extended reasoning.
        document_values.update(answer_top_k=10, rlm_extended_reasoning=False)
        return (
            DocumentKnowledgeSettings.model_validate(document_values),
            StructuredKnowledgeSettings.model_validate(
                {name: getattr(structured, name) for name in StructuredKnowledgeSettings.model_fields}
            ),
        )

    def _snapshot(self, tenant_id, row) -> OrganizationKnowledgeSnapshot:
        try:
            if row is None:
                documents, structured = self._deployment()
            else:
                documents = DocumentKnowledgeSettings.model_validate(row.documents)
                structured = StructuredKnowledgeSettings.model_validate(row.structured)
            values = dict(
                tenant_id=tenant_id,
                schema_version=row.schema_version if row else 1,
                revision=row.revision if row else 0,
                origin="organization" if row else "deployment",
                documents=documents.model_dump(mode="json"),
                structured=structured.model_dump(mode="json"),
            )
            return OrganizationKnowledgeSnapshot.model_validate({**values, "digest": snapshot_digest(values)})
        except ValidationError:
            raise ServiceUnavailableException(
                "Knowledge settings are outside the supported policy contract",
                code="KNOWLEDGE_SETTINGS_UNAVAILABLE",
            ) from None

    def _view(self, tenant_id, row) -> OrganizationKnowledgeSettings:
        value = self._snapshot(tenant_id, row)
        return OrganizationKnowledgeSettings.model_validate(
            {**value.model_dump(mode="json", exclude={"digest"}), "capabilities": capabilities()}
        )

    @transactional(read_only=True)
    async def get(self, subject, tenant_id) -> OrganizationKnowledgeSettings:
        await self._authorize_read(subject, tenant_id)
        return self._view(tenant_id, await self.settings.current(tenant_id))

    @transactional(read_only=True)
    async def snapshot(self, subject, tenant_id) -> OrganizationKnowledgeSnapshot:
        await self._authorize_read(subject, tenant_id)
        return self._snapshot(tenant_id, await self.settings.current(tenant_id))

    @transactional
    async def update(
        self, subject, tenant_id, values: OrganizationKnowledgeSettingsInput
    ) -> OrganizationKnowledgeSettings:
        await self.catalog.authorize(subject, tenant_id, "settings:write")
        values = OrganizationKnowledgeSettingsInput.model_validate(values)
        if not await self.settings.compare_and_swap(
            tenant_id,
            values.documents.model_dump(mode="json"),
            values.structured.model_dump(mode="json"),
            values.expected_revision,
            subject,
            datetime.now(UTC),
        ):
            raise ConflictException(
                "Organization knowledge settings changed. Reload and try again.",
                code="ORGANIZATION_KNOWLEDGE_CHANGED",
            )
        row = await self.settings.current(tenant_id)
        snapshot = self._snapshot(tenant_id, row)
        await self.catalog._audit(
            subject, tenant_id, "organization_knowledge.updated", tenant_id, snapshot.model_dump(mode="json")
        )
        return self._view(tenant_id, row)
