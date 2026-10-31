# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Private ingestion facts are captured by the server and reauthorized by native policies."""

import json
from contextlib import AsyncExitStack, asynccontextmanager
from hashlib import sha256
from importlib import import_module
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator, model_validator
from pyfly.container import service
from pyfly.context.conditions import conditional_on_property
from pyfly.data.transaction import Isolation, Propagation, TransactionTemplate, current_unit_of_work
from pyfly.kernel import ConflictException
from pyfly.security.context import SecurityContext
from pyfly.security.context_holder import SecurityContextHolder

from koinon.assistants.connections import api_for, options_fingerprint
from koinon.assistants.model_bindings import BorrowedModel, bind_model, current_model_binding
from koinon.assistants.repositories import AgentRepository
from koinon.assistants.scope import KnowledgeScopePolicy
from koinon.knowledge.adapters import native_scope
from koinon.knowledge.connections.resolver import PersistedKnowledgeConnectionResolver
from koinon.knowledge.connections.roles import ROLES
from koinon.security.authority import PRIMARY_POLICY_UNIT


def unavailable():
    return ConflictException(
        "The queued ingestion authority is unresolved; review and submit a new job",
        code="INGEST_EXECUTION_CONTEXT_REQUIRED",
    )


class ExecutionAgent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    agent_id: str = Field(min_length=1, max_length=64)
    agent_revision: int = Field(ge=1)
    provider_id: str = Field(min_length=1, max_length=64)
    provider_revision: int = Field(ge=1)
    model_id: str = Field(min_length=1, max_length=255)
    options_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class IngestionExecution(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    version: Literal[1] = 1
    subject: str = Field(min_length=3, max_length=512)
    token_id: str | None = Field(default=None, min_length=1, max_length=64)
    tenant_id: str = Field(min_length=1, max_length=64)
    domain: Literal["canon", "structured"]
    native_workspace_id: str = Field(min_length=1, max_length=64)
    catalog_workspace_id: str = Field(min_length=1, max_length=64)
    resource_ids: tuple[str, ...] = Field(min_length=1, max_length=16)
    roles: tuple[str, ...] = Field(min_length=1, max_length=8)
    selections: dict[str, dict[str, JsonValue]] = Field(max_length=8)
    agent: ExecutionAgent | None = None

    @field_validator("version", mode="before")
    @classmethod
    def exact_version(cls, value):
        if type(value) is not int or value != 1:
            raise ValueError("Unsupported execution context version")
        return value

    @model_validator(mode="after")
    def bounded(self):
        issuer, separator, subject = self.subject.partition("|")
        if not separator or not issuer or not subject:
            raise ValueError("A canonical subject is required")
        if len(set(self.resource_ids)) != len(self.resource_ids) or any(
            not 0 < len(value) <= 64 for value in self.resource_ids
        ):
            raise ValueError("Use exact bounded resources")
        expected = "documents" if self.domain == "canon" else "structured"
        if len(set(self.roles)) != len(self.roles) or any(
            role not in ROLES or ROLES[role].domain != expected for role in self.roles
        ):
            raise ValueError("Use exact native ingestion roles")
        if set(self.roles) != set(self.selections):
            raise ValueError("Every role requires an exact selection")
        if len(self.model_dump_json().encode()) > 16384:
            raise ValueError("Execution context exceeds its bound")
        return self


@asynccontextmanager
async def policy_unit():
    current = current_unit_of_work("primary")
    share = (
        current is not None
        and not current.completed
        and current.read_from_primary
        and (not current.read_only or current.definition.name == PRIMARY_POLICY_UNIT)
    )
    async with TransactionTemplate(
        "primary",
        name=PRIMARY_POLICY_UNIT,
        propagation=Propagation.REQUIRED if share else Propagation.REQUIRES_NEW,
        isolation=Isolation.SERIALIZABLE,
        read_only=True,
        read_from_primary=True,
    ).transaction():
        yield


@service(name="operations.ingestion_execution")
@conditional_on_property("koinon.knowledge.enabled", having_value="true", match_if_missing=True)
class IngestionExecutionAuthority:
    def __init__(
        self,
        resolver: PersistedKnowledgeConnectionResolver,
        agents: AgentRepository,
        scopes: KnowledgeScopePolicy,
    ):
        self.resolver, self.agents, self.scopes = resolver, agents, scopes
        self.catalog = resolver.assignments.catalog

    async def _selections(self, tenant_id, workspace_id, roles):
        result = {}
        for role in roles:
            row = await self.resolver.assignments.selected(tenant_id, workspace_id, ROLES[role].domain, role)
            if row is None or not row.enabled:
                raise unavailable()
            provider = await self.resolver.providers.find_by_id(row.provider_id) if row.provider_id else None
            if row.mode == "provider" and (
                provider is None
                or provider.tenant_id != tenant_id
                or not provider.enabled
                or row.model_id not in provider.model_ids
            ):
                raise unavailable()
            result[role] = {
                "assignment_id": row.id,
                "revision": row.revision,
                "mode": row.mode,
                "provider_id": row.provider_id,
                "provider_revision": provider.revision if provider else None,
                "model_id": row.model_id,
                "options_sha256": sha256(
                    json.dumps(row.model_options, sort_keys=True, allow_nan=False).encode()
                ).hexdigest(),
                "space_id": row.space_id,
                "embedding_fingerprint": row.embedding_fingerprint,
                "dimensions": row.dimensions,
                "storage_dimensions": row.storage_dimensions,
            }
        return result

    async def capture(self, domain, arguments, roles):
        subject, tenant = arguments["actor"], arguments["tenant_id"]
        context = SecurityContextHolder.get_context()
        if context is None:
            raise unavailable()
        async with policy_unit():
            workspace = await self.resolver.workspace(
                subject,
                tenant,
                domain,
                str(arguments["workspace_id"]),
                "ingest",
                arguments.get("catalog_workspace_id"),
            )
            resources = tuple(
                dict.fromkeys(
                    [
                        workspace,
                        *[
                            arguments[key]
                            for key in ("source_catalog_id",)
                            if isinstance(arguments.get(key), str)
                        ],
                    ]
                )
            )
            pins = await self._selections(tenant, workspace, roles)
            borrowed = current_model_binding(tenant, subject)
            agent = (
                {
                    key: getattr(borrowed, key)
                    for key in (
                        "agent_id",
                        "agent_revision",
                        "provider_id",
                        "provider_revision",
                        "model_id",
                        "options_sha256",
                    )
                }
                if borrowed
                else None
            )
            value = IngestionExecution(
                subject=subject,
                token_id=context.attributes.get("koinon_token_id"),
                tenant_id=tenant,
                domain=domain,
                native_workspace_id=str(arguments["workspace_id"]),
                catalog_workspace_id=workspace,
                resource_ids=resources,
                roles=roles,
                selections=pins,
                agent=ExecutionAgent.model_validate(agent) if agent is not None else None,
            )
            await self.validate(value)
            return value

    async def validate(self, value: IngestionExecution):
        context = SecurityContextHolder.get_context()
        if context is None or context.attributes.get("koinon_token_id") != value.token_id:
            raise unavailable()
        if f"{context.attributes.get('iss')}|{context.attributes.get('sub')}" != value.subject:
            raise unavailable()
        async with policy_unit():
            workspace = await self.resolver.workspace(
                value.subject,
                value.tenant_id,
                value.domain,
                value.native_workspace_id,
                "ingest",
                value.catalog_workspace_id,
            )
            for identifier in value.resource_ids:
                entry = await self.catalog.get(value.subject, value.tenant_id, identifier)
                if entry.workspace_id != workspace:
                    raise unavailable()
                await self.catalog.authorize(value.subject, value.tenant_id, "ingest:write", workspace)
                if self.catalog.restriction:
                    await self.catalog.restriction.resource(value.subject, entry, write=True)
            if await self._selections(value.tenant_id, workspace, value.roles) != value.selections:
                raise unavailable()
            if value.agent is not None:
                agent = await self.agents.find_by_id(value.agent.agent_id)
                provider = await self.resolver.providers.find_by_id(value.agent.provider_id)
                if (
                    agent is None
                    or provider is None
                    or not agent.enabled
                    or not provider.enabled
                    or (
                        agent.tenant_id,
                        agent.id,
                        agent.revision,
                        agent.provider_id,
                        agent.model_id,
                        provider.revision,
                        options_fingerprint(api_for(provider.kind, provider.api), agent.model_options),
                    )
                    != (
                        value.tenant_id,
                        value.agent.agent_id,
                        value.agent.agent_revision,
                        value.agent.provider_id,
                        value.agent.model_id,
                        value.agent.provider_revision,
                        value.agent.options_sha256,
                    )
                ):
                    raise unavailable()
                for identifier in value.resource_ids:
                    entry = await self.catalog.get(value.subject, value.tenant_id, identifier)
                    requested: dict = {"workspace_id": workspace}
                    current, seen = entry, set()
                    while current is not None:
                        if current.id in seen or len(seen) >= 16:
                            raise unavailable()
                        seen.add(current.id)
                        if current.kind == "project":
                            requested["project_id"] = current.id
                        if current.kind in {"collection", "corpus"}:
                            requested["collection_id"] = current.id
                        current = (
                            await self.catalog.get(value.subject, value.tenant_id, current.parent_id)
                            if current.parent_id
                            else None
                        )
                    if entry.kind in {"document", "dataset", "knowledge_item"}:
                        requested["asset_ids"] = [identifier]
                    elif entry.kind == "source" and agent.scope.get("asset_ids") is not None:
                        raise unavailable()
                    await self.scopes.validate_scope(value.subject, value.tenant_id, requested, agent.scope)

    @asynccontextmanager
    async def admit(self, domain, job, lease):
        from pydantic import ValidationError
        from pyfly.context.consumer_context import PRIVATE_CONSUMER_CONTEXT

        payload = job.metadata_json if domain == "canon" else job.get("request_json")
        if isinstance(payload, str):
            payload = json.loads(payload)
        try:
            value = IngestionExecution.model_validate((payload or {}).get(PRIVATE_CONSUMER_CONTEXT))
        except (ValidationError, TypeError, ValueError):
            raise unavailable() from None
        tenant = job.tenant_id if domain == "canon" else job["tenant_id"]
        native = job.workspace_id if domain == "canon" else job["workspace_id"]
        if domain == "structured":
            from uuid import UUID

            native = str(UUID(str(native)))
        if (value.domain, value.tenant_id, value.native_workspace_id) != (domain, tenant, str(native)):
            raise unavailable()
        issuer, _, subject = value.subject.partition("|")
        attributes = {"iss": issuer, "sub": subject}
        if value.token_id:
            attributes["koinon_token_id"] = value.token_id
        with SecurityContextHolder.using(SecurityContext(user_id=subject, attributes=attributes)):
            await self.validate(value)
            port = import_module(
                ("flycanon" if domain == "canon" else "flyquery") + ".core.agents.model_bindings"
            )
            async with AsyncExitStack() as lifetime:
                if value.agent is not None:
                    agent = await self.agents.find_by_id(value.agent.agent_id)
                    if agent is None:
                        raise unavailable()
                    provider = await self.resolver.providers.find_by_id(agent.provider_id)
                    if provider is None:
                        raise unavailable()
                    compiler = self.resolver.compiler
                    spec = compiler.spec(provider, agent.model_id, agent.model_options)
                    secret = (
                        self.resolver.secrets.decrypt(tenant, provider.id, provider.secret_ciphertext)
                        if provider.secret_ciphertext
                        else "unused"
                    )
                    model = await lifetime.enter_async_context(
                        compiler.models.build_with_secret(spec, secret)
                    )
                    del secret
                    binding = BorrowedModel(
                        model,
                        compiler.settings_for(spec),
                        provider.kind,
                        cast(Literal["chat", "responses", "messages"], api_for(provider.kind, provider.api)),
                        compiler.output_mode(provider, agent.model_id, agent.model_options, model),
                        agent_id=value.agent.agent_id,
                        agent_revision=value.agent.agent_revision,
                        provider_id=value.agent.provider_id,
                        provider_revision=value.agent.provider_revision,
                        model_id=value.agent.model_id,
                        options_sha256=value.agent.options_sha256,
                    )
                    lifetime.enter_context(bind_model(tenant, value.subject, binding))
                lifetime.enter_context(native_scope(domain, tenant, str(native), value.subject))
                connections = await lifetime.enter_async_context(
                    self.resolver.resolve(
                        domain=domain,
                        tenant_id=tenant,
                        workspace_id=str(native),
                        subject=value.subject,
                        purpose="ingest",
                        roles=value.roles,
                        catalog_workspace_id=value.catalog_workspace_id,
                    )
                )
                token = port.push_bindings(
                    tenant_id=tenant,
                    workspace_id=str(native),
                    subject=value.subject,
                    bindings=connections.models,
                    embeddings=connections.embeddings,
                )
                lifetime.callback(port.reset_bindings, token)
                lease_port = import_module(
                    (
                        "flycanon.core.services.sources"
                        if domain == "canon"
                        else "flyquery.core.services.ingestion"
                    )
                    + ".lease"
                )
                lifetime.enter_context(lease_port.bind_ingest_lease(lease, lambda: self.validate(value)))
                await self.validate(value)
                yield
