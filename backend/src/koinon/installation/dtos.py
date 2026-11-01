# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Bounded operator plans reference credentials without containing them."""

from hashlib import sha256
from json import dumps
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, model_validator

from koinon.assistants.connections import ModelParameters
from koinon.assistants.dtos import AgentInput, ProviderInput
from koinon.catalog.service import PARENTS
from koinon.knowledge.connections.roles import ROLES

Key = str


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class ProviderInstallation(Input):
    key: Key = Field(pattern=r"^[a-z][a-z0-9_-]{0,63}$")
    name: str = Field(min_length=1, max_length=160)
    kind: Literal["openai", "ollama", "anthropic"]
    api: Literal["chat", "responses", "messages"] | None = None
    base_url: str = Field(min_length=1, max_length=2048)
    model_ids: list[str] = Field(min_length=1, max_length=100)
    secret_env: str | None = Field(default=None, pattern=r"^[A-Z][A-Z0-9_]{0,127}$")

    @model_validator(mode="after")
    def native_fields(self):
        ProviderInput.model_validate(self.model_dump(exclude={"key", "secret_env"}))
        url = urlsplit(self.base_url)
        if url.username is not None or url.password is not None or url.query or url.fragment:
            raise ValueError("Credentials belong in secret ENV references, never a provider URL")
        if len(set(self.model_ids)) != len(self.model_ids):
            raise ValueError("Declare each model once")
        return self


class CatalogInstallation(Input):
    key: Key = Field(pattern=r"^[a-z][a-z0-9_-]{0,63}$")
    kind: Literal["workspace", "project", "collection", "corpus"]
    name: str = Field(min_length=1, max_length=255)
    parent_key: Key | None = Field(default=None, min_length=1, max_length=64)
    description: str = Field(default="", max_length=4000)


class ConnectionInstallation(Input):
    key: Key = Field(pattern=r"^[a-z][a-z0-9_-]{0,63}$")
    role: str = Field(min_length=1, max_length=64)
    provider_key: Key = Field(min_length=1, max_length=64)
    model_id: str = Field(min_length=1, max_length=255)
    workspace_key: Key | None = None
    model_options: ModelParameters = Field(
        default_factory=lambda: ModelParameters(max_tokens=1024, request_timeout=30)
    )

    @model_validator(mode="after")
    def generative_role(self):
        role = ROLES.get(self.role)
        if role is None or role.embedding:
            raise ValueError("Declare a native generative role; embedding roles come from qualified indexes")
        return self


class IndexInstallation(Input):
    key: Key = Field(pattern=r"^[a-z][a-z0-9_-]{0,63}$")
    workspace_key: Key = Field(min_length=1, max_length=64)
    domain: Literal["documents", "structured"]
    provider_key: Key = Field(min_length=1, max_length=64)
    model_id: str = Field(min_length=1, max_length=255)
    dimensions: int = Field(ge=64, le=4000, strict=True)

    @model_validator(mode="after")
    def native_dimensions(self):
        if self.domain == "structured" and self.dimensions != 1536:
            raise ValueError("Structured native storage requires 1536 dimensions")
        return self


class AgentInstallation(Input):
    key: Key = Field(pattern=r"^[a-z][a-z0-9_-]{0,63}$")
    name: str = Field(min_length=1, max_length=160)
    provider_key: Key = Field(min_length=1, max_length=64)
    model_id: str = Field(min_length=1, max_length=255)
    tools: list[str] = Field(default_factory=list, max_length=4)
    model_options: ModelParameters = Field(
        default_factory=lambda: ModelParameters(max_tokens=1024, request_timeout=30)
    )
    description: str = Field(default="", max_length=2000)
    instructions: str = Field(default="", max_length=8000)
    set_default_if_empty: bool = True

    @model_validator(mode="after")
    def native_agent(self):
        AgentInput.model_validate(self.model_dump(exclude={"key", "provider_key", "set_default_if_empty"}))
        if len(set(self.tools)) != len(self.tools):
            raise ValueError("Declare each tool once")
        return self


class InstallationPlan(Input):
    schema_version: Literal[1]
    plan_key: Key = Field(pattern=r"^[a-z][a-z0-9_-]{0,63}$")
    tenant_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
    providers: list[ProviderInstallation] = Field(min_length=1, max_length=8)
    catalog: list[CatalogInstallation] = Field(min_length=1, max_length=32)
    connections: list[ConnectionInstallation] = Field(default_factory=list, max_length=32)
    indexes: list[IndexInstallation] = Field(default_factory=list, max_length=8)
    agent: AgentInstallation

    @model_validator(mode="after")
    def references(self):
        for group in (self.providers, self.catalog, self.connections, self.indexes):
            if len({item.key for item in group}) != len(group):
                raise ValueError("Use unique stable keys within each section")
        providers = {value.key: value for value in self.providers}
        catalog = {value.key: value for value in self.catalog}
        for node in self.catalog:
            parent = catalog.get(node.parent_key) if node.parent_key else None
            if (parent.kind if parent else None) not in PARENTS[node.kind] or (
                node.parent_key and parent is None
            ):
                raise ValueError("Select the native workspace, project and collection/corpus hierarchy")
        self.catalog_order()
        for entry in (*self.connections, *self.indexes, self.agent):
            provider = providers.get(entry.provider_key)
            if provider is None or entry.model_id not in provider.model_ids:
                raise ValueError("Select a declared provider and model")
            workspace = getattr(entry, "workspace_key", None)
            if workspace is not None and (workspace not in catalog or catalog[workspace].kind != "workspace"):
                raise ValueError("Select a declared workspace")
        if len({(value.workspace_key, value.domain) for value in self.indexes}) != len(self.indexes):
            raise ValueError("Only one initial index per workspace and domain is supported")
        if len({(value.workspace_key, value.role) for value in self.connections}) != len(self.connections):
            raise ValueError("Only one initial assignment per scope and role is supported")
        return self

    def catalog_order(self) -> list[str]:
        nodes = {node.key: node for node in self.catalog}
        order: list[str] = []
        visiting: set[str] = set()

        def visit(key):
            if key in visiting or len(visiting) > 16:
                raise ValueError("Catalog parents must be acyclic and bounded")
            if key in order:
                return
            if key not in nodes:
                raise ValueError("Select an existing catalog key")
            visiting.add(key)
            if nodes[key].parent_key:
                visit(nodes[key].parent_key)
            visiting.remove(key)
            order.append(key)

        for node in self.catalog:
            visit(node.key)
        return order

    def fingerprint(self) -> str:
        return sha256(
            dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
