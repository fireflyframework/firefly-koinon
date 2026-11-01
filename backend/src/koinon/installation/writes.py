# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Protected operator ports reuse the same domain validators and persistence as HTTP services."""

from dataclasses import dataclass, field
from hashlib import sha256
from json import dumps
from typing import Literal, cast
from uuid import NAMESPACE_URL, uuid5

from pydantic import SecretStr
from pyfly.container import Provider, service
from pyfly.data.relational.sqlalchemy import LockMode, transactional

from koinon.assistants.configuration_service import AssistantConfigurationService
from koinon.catalog.service import CatalogService
from koinon.installation.authority import ACTOR, InstallationAdmissions, InstallationError, InstallationPermit
from koinon.installation.dtos import (
    AgentInstallation,
    CatalogInstallation,
    ConnectionInstallation,
    ProviderInstallation,
)
from koinon.knowledge.connections.dtos import ConnectionInput
from koinon.knowledge.connections.roles import ROLES
from koinon.knowledge.connections.service import KnowledgeConnectionService
from koinon.organization_chat.repositories import OrganizationChatRepository


def resource_id(permit: InstallationPermit, key: str) -> str:
    return str(uuid5(NAMESPACE_URL, "koinon-installation:" + permit.run_id + ":" + key))


def fingerprint(value: dict) -> str:
    return sha256(dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True)
class ProviderProbeSnapshot:
    provider_id: str
    revision: int
    kind: str
    api: str
    base_url: str
    model_ids: list[str]
    secret: SecretStr | None = field(repr=False)


@service(name="installation.native_writes")
class NativeInstallationWrites:
    def __init__(
        self,
        admissions: InstallationAdmissions,
        configuration: Provider[AssistantConfigurationService],
        catalog: Provider[CatalogService],
        connections: Provider[KnowledgeConnectionService],
        chat: Provider[OrganizationChatRepository],
    ):
        self.admissions, self.configuration, self.catalog, self.connections, self.chat = (
            admissions,
            configuration,
            catalog,
            connections,
            chat,
        )

    @staticmethod
    def reference(run, section, key):
        value = run.checkpoints.get(section + ":" + key)
        if value is None or value.get("status") != "done":
            raise InstallationError("INSTALLATION_DEPENDENCY_PENDING")
        return value["resource_id"]

    @transactional(read_from_primary=True)
    async def provider(
        self, permit: InstallationPermit, value: ProviderInstallation, secret: SecretStr | None
    ) -> dict:
        run = await self.admissions.require(permit)
        configuration = self.configuration.get()
        await configuration.catalog._lock_tenant(permit.tenant_id)
        key = "provider:" + value.key
        previous = run.checkpoints.get(key)
        identifier = resource_id(permit, key)
        if previous:
            row = await configuration.providers.find_by_id(identifier, lock=LockMode.PESSIMISTIC_READ)
            if row is None or row.tenant_id != permit.tenant_id or row.revision != previous["revision"]:
                raise InstallationError("INSTALLATION_MANUAL_CHANGE")
            return previous
        if await configuration.providers.find_by_id(identifier) is not None or any(
            row.name.casefold() == value.name.casefold()
            for row in await configuration.providers.find_all(tenant_id=permit.tenant_id)
        ):
            raise InstallationError("INSTALLATION_PROVIDER_EXISTS")
        fields = value.model_dump(exclude={"key", "secret_env"})
        fields.update(secret=secret, enabled=True)
        result = await configuration._write_provider(ACTOR, permit.tenant_id, fields, create_id=identifier)
        receipt = {"status": "done", "resource_id": result["id"], "revision": result["revision"]}
        await self.admissions.checkpoint(permit, key, receipt)
        return receipt

    @transactional(read_from_primary=True)
    async def probe_snapshot(self, permit: InstallationPermit, provider_key: str) -> ProviderProbeSnapshot:
        run = await self.admissions.require(permit)
        configuration = self.configuration.get()
        identifier = self.reference(run, "provider", provider_key)
        row = await configuration.providers.find_by_id(identifier, lock=LockMode.PESSIMISTIC_READ)
        expected = run.checkpoints["provider:" + provider_key]
        if row is None or row.tenant_id != permit.tenant_id or row.revision != expected["revision"]:
            raise InstallationError("INSTALLATION_MANUAL_CHANGE")
        secret = (
            configuration.secrets.decrypt(permit.tenant_id, row.id, row.secret_ciphertext)
            if row.secret_ciphertext
            else None
        )
        return ProviderProbeSnapshot(
            row.id,
            row.revision,
            row.kind,
            row.api,
            row.base_url,
            list(row.model_ids),
            SecretStr(secret) if secret else None,
        )

    @transactional(read_from_primary=True)
    async def save_discovery(self, permit, provider_key, snapshot: ProviderProbeSnapshot, checks):
        run = await self.admissions.require(permit)
        if self.reference(run, "provider", provider_key) != snapshot.provider_id:
            raise InstallationError("INSTALLATION_DEPENDENCY_CHANGED")
        configuration = self.configuration.get()
        await configuration.catalog._lock_tenant(permit.tenant_id)
        await configuration._write_validation(
            ACTOR, permit.tenant_id, snapshot.provider_id, snapshot.revision, checks
        )
        await self.admissions.checkpoint(
            permit,
            "discovery:" + provider_key,
            {
                "status": "done",
                "resource_id": snapshot.provider_id,
                "revision": snapshot.revision,
                "connection_passed": any(v["id"] == "connection" and v["status"] == "passed" for v in checks),
                "models_passed": any(v["id"] == "models" and v["status"] == "passed" for v in checks),
            },
        )

    @transactional(read_from_primary=True)
    async def catalog_node(self, permit, value: CatalogInstallation):
        run = await self.admissions.require(permit)
        catalog = self.catalog.get()
        await catalog._lock_tenant(permit.tenant_id)
        key = "catalog:" + value.key
        parent_id = self.reference(run, "catalog", value.parent_key) if value.parent_key else None
        identifier = resource_id(permit, key)
        wanted = dict(
            name=value.name.strip(), kind=value.kind, parent_id=parent_id, description=value.description
        )
        previous = run.checkpoints.get(key)
        if previous:
            row = await catalog.catalog_repository.find_by_id(identifier)
            if (
                row is None
                or row.tenant_id != permit.tenant_id
                or fingerprint({field: getattr(row, field) for field in wanted}) != previous["fingerprint"]
            ):
                raise InstallationError("INSTALLATION_MANUAL_CHANGE")
            return previous
        if await catalog.catalog_repository.find_by_id(identifier) is not None or any(
            row.parent_id == parent_id and row.name.casefold() == value.name.casefold()
            for row in await catalog.catalog_repository.find_all(tenant_id=permit.tenant_id)
        ):
            raise InstallationError("INSTALLATION_CATALOG_EXISTS")
        row = await catalog._write_create(
            ACTOR,
            permit.tenant_id,
            **wanted,
            create_id=identifier,
            installation_run_id=permit.run_id,
            system_key=value.key,
        )
        receipt = {"status": "done", "resource_id": row.id, "fingerprint": fingerprint(wanted)}
        await self.admissions.checkpoint(permit, key, receipt)
        return receipt

    @transactional(read_from_primary=True)
    async def connection(self, permit: InstallationPermit, value: ConnectionInstallation) -> dict:
        run = await self.admissions.require(permit)
        connections = self.connections.get()
        await connections.connections.lock_tenant(permit.tenant_id)
        workspace_id = self.reference(run, "catalog", value.workspace_key) if value.workspace_key else None
        previous = run.checkpoints.get("connection:" + value.key)
        found = await connections.connections.find_all(
            tenant_id=permit.tenant_id,
            workspace_id=workspace_id,
            domain=cast(Literal["documents", "structured"], ROLES[value.role].domain),
            role=value.role,
        )
        if previous:
            if (
                len(found) != 1
                or found[0].id != previous["resource_id"]
                or found[0].revision != previous["revision"]
            ):
                raise InstallationError("INSTALLATION_MANUAL_CHANGE")
            return previous
        if found:
            raise InstallationError("INSTALLATION_CONNECTION_EXISTS")
        data = ConnectionInput(
            domain=cast(Literal["documents", "structured"], ROLES[value.role].domain),
            role=value.role,
            workspace_id=workspace_id,
            mode="provider",
            provider_id=self.reference(run, "provider", value.provider_key),
            model_id=value.model_id,
            model_options=value.model_options,
        )
        result = await connections._write_connection(ACTOR, permit.tenant_id, data)
        receipt = {"status": "done", "resource_id": result["id"], "revision": result["revision"]}
        await self.admissions.checkpoint(permit, "connection:" + value.key, receipt)
        return receipt

    @transactional(read_from_primary=True)
    async def agent(self, permit: InstallationPermit, value: AgentInstallation) -> dict:
        run = await self.admissions.require(permit)
        configuration = self.configuration.get()
        await configuration.catalog._lock_tenant(permit.tenant_id)
        key = "agent:" + value.key
        identifier = resource_id(permit, key)
        previous = run.checkpoints.get(key)
        if previous:
            row = await configuration.agents.find_by_id(identifier)
            if row is None or row.tenant_id != permit.tenant_id or row.revision != previous["revision"]:
                raise InstallationError("INSTALLATION_MANUAL_CHANGE")
            return previous
        if await configuration.agents.find_by_id(identifier) is not None or any(
            row.name.casefold() == value.name.casefold()
            for row in await configuration.agents.find_all(tenant_id=permit.tenant_id)
        ):
            raise InstallationError("INSTALLATION_AGENT_EXISTS")
        fields = value.model_dump(exclude={"key", "provider_key", "set_default_if_empty"})
        fields.update(provider_id=self.reference(run, "provider", value.provider_key), scope={}, enabled=True)
        row = await configuration._write_agent(
            ACTOR, permit.tenant_id, fields, create_id=identifier, initial_scope={}
        )
        receipt = {"status": "done", "resource_id": row.id, "revision": row.revision}
        await self.admissions.checkpoint(permit, key, receipt)
        return receipt

    @transactional(read_from_primary=True)
    async def default_agent(self, permit: InstallationPermit, agent_key: str):
        run = await self.admissions.require(permit)
        identifier = self.reference(run, "agent", agent_key)
        chat = self.chat.get()
        current = await chat.current(permit.tenant_id)
        previous = run.checkpoints.get("default_agent")
        if previous:
            if (
                current is None
                or current.default_agent_id != identifier
                or current.revision != previous["revision"]
            ):
                raise InstallationError("INSTALLATION_MANUAL_CHANGE")
            return previous
        if current is not None and current.default_agent_id is not None:
            raise InstallationError("INSTALLATION_DEFAULT_EXISTS")
        revision = current.revision if current else 0
        if not await chat.compare_and_swap(
            permit.tenant_id, identifier, revision, ACTOR, await self.admissions.runs.clock()
        ):
            raise InstallationError("INSTALLATION_DEFAULT_CONFLICT")
        await self.catalog.get()._audit(
            ACTOR, permit.tenant_id, "installation.default_agent", identifier, {"run_id": permit.run_id}
        )
        receipt = {"status": "done", "resource_id": identifier, "revision": revision + 1}
        await self.admissions.checkpoint(permit, "default_agent", receipt)
        return receipt

    @transactional(read_from_primary=True)
    async def qualified(self, permit, provider_key, snapshot, model_id, model_options, *, require_tools):
        run = await self.admissions.require(permit)
        if self.reference(run, "provider", provider_key) != snapshot.provider_id:
            raise InstallationError("INSTALLATION_DEPENDENCY_CHANGED")
        configuration = self.configuration.get()
        row = await configuration.providers.find_by_id(snapshot.provider_id, lock=LockMode.PESSIMISTIC_WRITE)
        if row is None or row.tenant_id != permit.tenant_id or row.revision != snapshot.revision:
            raise InstallationError("INSTALLATION_MANUAL_CHANGE")
        options = model_options.model_dump(mode="json", exclude_none=True)
        key = "qualified:" + fingerprint(
            {"provider_key": provider_key, "model_id": model_id, "options": options, "tools": require_tools}
        )
        if key in run.checkpoints:
            return
        await configuration.record_runtime_qualification(
            permit.tenant_id,
            snapshot.provider_id,
            snapshot.revision,
            model_id,
            ["installation_health"] if require_tools else [],
            options,
        )
        await configuration.catalog._audit(
            ACTOR,
            permit.tenant_id,
            "installation.provider.qualified",
            snapshot.provider_id,
            {"run_id": permit.run_id, "model_id": model_id, "tools": require_tools},
        )
        await self.admissions.checkpoint(
            permit,
            key,
            {
                "status": "done",
                "resource_id": snapshot.provider_id,
                "revision": snapshot.revision,
                "model_id": model_id,
                "tools": require_tools,
            },
        )
