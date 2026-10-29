# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Persist role assignments without opening clients or exposing credentials."""

from hashlib import sha256
from json import dumps

from pydantic import ValidationError
from pyfly.container import service
from pyfly.data.relational.sqlalchemy import LockMode, transactional
from pyfly.kernel import ConflictException, DuplicateKeyException, InvalidRequestException

from koinon.assistants.connections import ConnectionResolver, ModelParameters, api_for, normalized_options
from koinon.assistants.repositories import ProviderRepository
from koinon.catalog.errors import AccessDenied
from koinon.catalog.service import CatalogService
from koinon.knowledge.connections.dtos import ConnectionInput
from koinon.knowledge.connections.entities import KnowledgeConnection, timestamp
from koinon.knowledge.connections.mappers import connection_dto
from koinon.knowledge.connections.repositories import KnowledgeConnectionRepository
from koinon.knowledge.connections.roles import ROLES


def embedding_fingerprint(provider, model_id, dimensions, storage_dimensions):
    identity = (
        provider.id,
        provider.kind,
        provider.base_url.rstrip("/"),
        model_id,
        dimensions,
        storage_dimensions,
    )
    return sha256(dumps(identity).encode()).hexdigest()


@service(name="knowledge.connection_service")
class KnowledgeConnectionService:
    def __init__(
        self,
        catalog: CatalogService,
        connections: KnowledgeConnectionRepository,
        providers: ProviderRepository,
        compiler: ConnectionResolver,
    ):
        self.catalog, self.connections, self.providers, self.compiler = (
            catalog,
            connections,
            providers,
            compiler,
        )

    async def authority(self, subject, tenant_id, workspace_id, *, permission="providers:write"):
        await self.catalog.authorize(subject, tenant_id, permission, workspace_id)
        if workspace_id is not None:
            workspace = await self.catalog.get(subject, tenant_id, workspace_id)
            if workspace.kind != "workspace" or workspace.status == "archived":
                raise AccessDenied("Select an active canonical workspace", code="ACCESS_DENIED")
            if self.catalog.restriction and permission in {"providers:write", "ingest:write"}:
                await self.catalog.restriction.resource(subject, workspace, write=True)

    async def scoped(self, tenant_id, identifier, *, lock=False):
        rows = await self.connections.find_all(tenant_id=tenant_id, id=identifier)
        if not rows:
            raise AccessDenied("Knowledge connection is unavailable", code="ACCESS_DENIED")
        row = (
            await self.connections.find_by_id(identifier, lock=LockMode.PESSIMISTIC_WRITE)
            if lock
            else rows[0]
        )
        if row is None or row.tenant_id != tenant_id:
            raise AccessDenied("Knowledge connection is unavailable", code="ACCESS_DENIED")
        return row

    async def selected(self, tenant_id, workspace_id, domain, role):
        for scope in (workspace_id, None) if workspace_id is not None else (None,):
            rows = await self.connections.find_all(
                tenant_id=tenant_id, workspace_id=scope, domain=domain, role=role
            )
            if rows:
                return rows[0]
        return None

    async def list(self, subject, tenant_id, workspace_id=None):
        await self.authority(subject, tenant_id, workspace_id)
        return [
            connection_dto(row)
            for row in await self.connections.find_all(tenant_id=tenant_id, workspace_id=workspace_id)
        ]

    async def descriptors(self, subject, tenant_id, workspace_id=None):
        await self.authority(subject, tenant_id, workspace_id, permission="catalog:read")
        roles = []
        for identifier, descriptor in ROLES.items():
            row = await self.selected(tenant_id, workspace_id, descriptor.domain, identifier)
            roles.append(
                {
                    "id": identifier,
                    "domain": descriptor.domain,
                    "label": descriptor.label,
                    "kind": "embedding" if descriptor.embedding else "generative",
                    "purposes": descriptor.purposes,
                    "supports_current_agent": not descriptor.embedding,
                    "compatible_index_required": descriptor.embedding,
                    "assignment": None
                    if row is None
                    else "tenant"
                    if row.workspace_id is None
                    else "workspace",
                    "status": "needs_setup" if row is None else "assigned" if row.enabled else "disabled",
                    "runtime_qualification": "not_run",
                }
            )
        result = {"roles": roles, "model_options_schema": ModelParameters.model_json_schema()}
        try:
            await self.authority(subject, tenant_id, workspace_id)
        except AccessDenied:
            return result
        result["providers"] = [
            {name: getattr(provider, name) for name in ("id", "name", "kind", "api", "model_ids", "enabled")}
            for provider in await self.providers.find_all(tenant_id=tenant_id)
        ]
        return result

    async def get(self, subject, tenant_id, identifier):
        row = await self.scoped(tenant_id, identifier)
        await self.authority(subject, tenant_id, row.workspace_id)
        return connection_dto(row)

    @transactional
    async def save(self, subject, tenant_id, values, connection_id=None):
        try:
            data = ConnectionInput.model_validate(values)
        except ValidationError as error:
            raise InvalidRequestException(
                "Provide valid scoped knowledge connection fields", code="INVALID_KNOWLEDGE_CONNECTION"
            ) from error
        await self.authority(subject, tenant_id, data.workspace_id)
        role = ROLES.get(data.role)
        if role is None or role.domain != data.domain:
            raise InvalidRequestException(
                "Choose a declared role in this domain", code="INVALID_KNOWLEDGE_ROLE"
            )
        current = await self.scoped(tenant_id, connection_id, lock=True) if connection_id else None
        if current:
            if (current.workspace_id, current.domain, current.role) != (
                data.workspace_id,
                data.domain,
                data.role,
            ):
                raise InvalidRequestException(
                    "A role assignment's scope is immutable", code="KNOWLEDGE_CONNECTION_SCOPE_IMMUTABLE"
                )
            if data.expected_revision != current.revision:
                raise ConflictException(
                    "Reload the current knowledge connection revision", code="KNOWLEDGE_CONNECTION_CONFLICT"
                )
        elif data.expected_revision is not None:
            raise InvalidRequestException(
                "A new role assignment has no prior revision", code="INVALID_KNOWLEDGE_REVISION"
            )
        elif await self.connections.find_all(
            tenant_id=tenant_id, scope_key=data.workspace_id or "", domain=data.domain, role=data.role
        ):
            raise ConflictException(
                "This scoped role is already assigned", code="KNOWLEDGE_CONNECTION_EXISTS"
            )
        provider = None
        options = data.model_options.model_dump(
            mode="json", exclude_unset=True, exclude_none=True
        ) if data.model_options else {}
        if data.mode == "current_agent":
            if (
                role.embedding
                or data.provider_id
                or data.model_id
                or options
                or any((data.dimensions, data.storage_dimensions, data.space_id))
            ):
                raise InvalidRequestException(
                    "Current-agent selection is explicit and available only to generative roles",
                    code="INVALID_KNOWLEDGE_CONNECTION",
                )
        else:
            providers = await self.providers.find_all(tenant_id=tenant_id, id=data.provider_id)
            if not providers:
                raise AccessDenied("Provider is unavailable in this organization", code="ACCESS_DENIED")
            provider = providers[0]
            if not data.model_id or data.model_id not in provider.model_ids:
                raise InvalidRequestException(
                    "Choose a model declared by this provider", code="INVALID_KNOWLEDGE_MODEL"
                )
            if role.embedding:
                if (
                    provider.kind not in {"ollama", "openai"}
                    or options
                    or not data.space_id
                    or not data.dimensions
                    or not data.storage_dimensions
                    or data.dimensions > data.storage_dimensions
                    or (data.domain == "documents" and data.dimensions != data.storage_dimensions)
                    or (data.domain == "structured" and data.storage_dimensions != 1536)
                ):
                    raise InvalidRequestException(
                        "Embedding roles require a separate compatible provider, "
                        "explicit indexed space and dimensions",
                        code="INVALID_KNOWLEDGE_EMBEDDING",
                    )
            else:
                if any((data.dimensions, data.storage_dimensions, data.space_id)):
                    raise InvalidRequestException(
                        "Only embedding roles accept indexed-space fields",
                        code="INVALID_KNOWLEDGE_CONNECTION",
                    )
                try:
                    spec = self.compiler.spec(provider, data.model_id, options)
                    assert spec.options is not None
                    options = normalized_options(api_for(provider.kind, provider.api), options).model_dump(
                        mode="json", exclude_none=True
                    )
                except ValueError as error:
                    raise InvalidRequestException(
                        "Choose native model options supported by this provider and API",
                        code="INVALID_KNOWLEDGE_MODEL_OPTIONS",
                    ) from error
        fingerprint = (
            embedding_fingerprint(provider, data.model_id, data.dimensions, data.storage_dimensions)
            if role.embedding
            else None
        )
        if role.embedding and await self.connections.find_conflicting_embedding_history(
            tenant_id, data.role, (data.space_id,), fingerprint
        ):
            raise ConflictException(
                "This indexed space is bound to a different connection; complete a reviewed reindex first",
                code="KNOWLEDGE_EMBEDDING_REINDEX_REQUIRED",
            )
        if (
            current
            and role.embedding
            and (current.embedding_fingerprint, current.space_id) != (fingerprint, data.space_id)
        ):
            raise ConflictException(
                "Changing an indexed embedding space requires a reviewed reindex before rebinding",
                code="KNOWLEDGE_EMBEDDING_REINDEX_REQUIRED",
            )
        identifier = sha256(
            dumps((tenant_id, data.workspace_id, data.domain, data.role)).encode()
        ).hexdigest()
        row = current or KnowledgeConnection(
            id=identifier,
            tenant_id=tenant_id,
            scope_key=data.workspace_id or "",
            workspace_id=data.workspace_id,
            domain=data.domain,
            role=data.role,
            created_by=subject,
            updated_by=subject,
        )
        for name in (
            "mode",
            "provider_id",
            "model_id",
            "dimensions",
            "storage_dimensions",
            "space_id",
            "enabled",
        ):
            setattr(row, name, getattr(data, name))
        row.model_options, row.embedding_fingerprint = options, fingerprint
        row.revision, row.updated_by, row.updated_at = (
            current.revision + 1 if current else 1,
            subject,
            timestamp(),
        )
        try:
            row = await self.connections.save(row)
        except DuplicateKeyException as error:
            raise ConflictException(
                "This scoped role is already assigned", code="KNOWLEDGE_CONNECTION_EXISTS"
            ) from error
        await self.catalog._audit(
            subject,
            tenant_id,
            "knowledge.connection.saved",
            row.id,
            {
                "role": row.role,
                "revision": row.revision,
                **(
                    {"space_id": row.space_id, "embedding_fingerprint": row.embedding_fingerprint}
                    if role.embedding
                    else {}
                ),
            },
        )
        return connection_dto(row)

    @transactional
    async def delete(self, subject, tenant_id, identifier, *, expected_revision):
        row = await self.scoped(tenant_id, identifier)
        await self.authority(subject, tenant_id, row.workspace_id)
        row = await self.scoped(tenant_id, identifier, lock=True)
        if row.revision != expected_revision:
            raise ConflictException(
                "Reload the current knowledge connection revision", code="KNOWLEDGE_CONNECTION_CONFLICT"
            )
        await self.connections.delete_by_id(row.id)
        await self.catalog._audit(
            subject,
            tenant_id,
            "knowledge.connection.deleted",
            row.id,
            {"role": row.role, "revision": row.revision},
        )
