# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0


from pyfly.container import service
from pyfly.data.relational.sqlalchemy import LockMode, transactional
from pyfly.kernel import ConflictException, InvalidRequestException

from koinon.assistants.connections import (
    APIS,
    CLASSES,
    DEFAULT_URLS,
    ConnectionResolver,
    ModelParameters,
    api_for,
    capability_state,
    input_modalities,
    normalized_options,
    options_fingerprint,
    provider_state,
)
from koinon.assistants.dependencies import ConnectionDependencies
from koinon.assistants.entities import AgentConfiguration, Provider
from koinon.assistants.lifecycle import identifier, timestamp
from koinon.assistants.mappers import provider_dto
from koinon.assistants.probe import ProviderProbe
from koinon.assistants.repositories import AgentRepository, ProviderRepository
from koinon.assistants.scope import KnowledgeScopePolicy
from koinon.assistants.settings import AssistantSettings, ProviderSecrets
from koinon.catalog.errors import AccessDenied
from koinon.catalog.service import CatalogService

TOOLS = frozenset({"search_knowledge", "inspect_schema", "query_dataset", "propose_catalog_update"})

PROVIDER_DEFAULTS = DEFAULT_URLS


@service(name="assistants.configuration-service")
class AssistantConfigurationService:
    def __init__(
        self,
        catalog: CatalogService,
        providers: ProviderRepository,
        agents: AgentRepository,
        secrets: ProviderSecrets,
        settings: AssistantSettings,
        probe: ProviderProbe,
        scope_policy: KnowledgeScopePolicy,
        connections: ConnectionResolver,
        dependencies: ConnectionDependencies,
    ):
        self.catalog, self.providers, self.agents = catalog, providers, agents
        self.secrets, self.settings, self.probe = secrets, settings, probe
        self.scope_policy = scope_policy
        self.connections, self.dependencies = connections, dependencies

    async def validate_scope(self, subject, tenant_id, requested, limit=None):
        return await self.scope_policy.validate_scope(subject, tenant_id, requested, limit)

    async def scoped(self, repository, tenant_id: str, resource_id: str, *, lock=False):
        rows = await repository.find_all(id=resource_id, tenant_id=tenant_id)
        if not rows:
            raise AccessDenied("Resource is unavailable in this organization", code="ACCESS_DENIED")
        return await repository.find_by_id(resource_id, lock=LockMode.PESSIMISTIC_WRITE) if lock else rows[0]

    def provider_address(self, kind: str, address: str) -> str:
        try:
            return self.connections.address(kind, address)
        except ValueError as exc:
            raise InvalidRequestException(str(exc), code="PROVIDER_HOST_DENIED") from exc

    @transactional
    async def save_provider(
        self, subject: str, tenant_id: str, values: dict, provider_id: str | None = None
    ) -> dict:
        await self.catalog.authorize(subject, tenant_id, "providers:write")
        if set(values) - {"name", "kind", "api", "base_url", "model_ids", "secret", "enabled"}:
            raise InvalidRequestException("Unsupported provider fields", code="INVALID_PROVIDER")
        current = (
            await self.scoped(self.providers, tenant_id, provider_id, lock=True) if provider_id else None
        )
        kind = values.get("kind", current.kind if current else "")
        name = str(values.get("name", current.name if current else "")).strip()
        models = values.get("model_ids", current.model_ids if current else [])
        if (
            not name
            or len(name) > 160
            or not isinstance(models, list)
            or len(models) > 100
            or any(not isinstance(model, str) or not model.strip() or len(model) > 255 for model in models)
        ):
            raise InvalidRequestException(
                "Provide a name and supported model identifiers", code="INVALID_PROVIDER"
            )
        address = self.provider_address(kind, values.get("base_url", current.base_url if current else ""))
        row = current or Provider(
            id=identifier(), tenant_id=tenant_id, name=name, kind=kind, base_url=address
        )
        try:
            row.api = api_for(
                kind, values.get("api", current.api if current and current.kind == kind else None)
            )
        except ValueError as exc:
            raise InvalidRequestException(str(exc), code="INVALID_PROVIDER_API") from exc
        row.name, row.kind, row.base_url, row.model_ids = name, kind, address, list(dict.fromkeys(models))
        if "secret" in values:
            secret = values["secret"]
            if hasattr(secret, "get_secret_value"):
                secret = secret.get_secret_value()
            if secret is None:
                row.secret_ciphertext = None
            elif isinstance(secret, str) and 0 < len(secret) <= 16384:
                row.secret_ciphertext = self.secrets.encrypt(tenant_id, row.id, secret)
            else:
                raise InvalidRequestException(
                    "Enter a nonempty provider credential", code="INVALID_CREDENTIAL"
                )
        row.enabled = values.get("enabled", current.enabled if current else True)
        row.validated_revision, row.checks = 0, []
        row.revision = current.revision + 1 if current else 1
        row.updated_at = timestamp()
        row = await self.providers.save(row)
        await self.catalog._audit(
            subject, tenant_id, "provider.saved", row.id, {"kind": kind, "revision": row.revision}
        )
        return provider_dto(row)

    async def configuration(self, subject: str, tenant_id: str) -> dict:
        await self.catalog.authorize(subject, tenant_id, "providers:write")
        return {
            "providers": [provider_dto(row) for row in await self.providers.find_all(tenant_id=tenant_id)],
            "provider_types": [
                {
                    "id": kind,
                    "name": label,
                    "fields": [
                        {
                            "name": "api",
                            "label": "Model API",
                            "type": "select",
                            "required": True,
                            "default": APIS[kind][0],
                            "options": [{"value": api, "label": api} for api in APIS[kind]],
                        },
                        {"name": "name", "label": "Display name", "type": "text", "required": True},
                        {
                            "name": "base_url",
                            "label": "API base URL",
                            "type": "url",
                            "required": True,
                            "default": PROVIDER_DEFAULTS.get(kind, ""),
                        },
                        {"name": "model_ids", "label": "Models", "type": "string_list", "required": True},
                        {
                            "name": "secret",
                            "label": "API key",
                            "type": "secret",
                            "write_only": True,
                            "required": kind != "ollama",
                        },
                    ],
                }
                for kind, label in (("ollama", "Ollama"), ("openai", "OpenAI"), ("anthropic", "Anthropic"))
            ],
            "connections": self.dependencies.describe(),
            "framework_providers": self.connections.supported_providers(),
            "model_options_schema": ModelParameters.model_json_schema(),
            "checks": [
                {
                    "id": "provider_hosts",
                    "status": "passed" if self.settings.allowed_provider_hosts else "needs_setup",
                    "message": "Provider addresses require the deployment administrator's allowlist.",
                }
            ],
        }

    async def agent_dto(self, row: AgentConfiguration) -> dict:
        provider = await self.scoped(self.providers, row.tenant_id, row.provider_id)
        state = provider_state(provider)
        option_error = None
        option_key = "invalid"
        model_settings = {}
        try:
            spec = self.connections.spec(provider, row.model_id, row.model_options)
            assert spec.options is not None
            options = normalized_options(state["api"], row.model_options).model_dump(
                mode="json", exclude_none=True
            )
            model_settings = self.connections.settings_for(spec)
            option_key = options_fingerprint(state["api"], row.model_options)
        except ValueError as exc:
            option_error = str(exc)
            options = row.model_options
        configured = state["configured"] and row.model_id in provider.model_ids and option_error is None
        capability = next(
            (c for c in capability_state(provider, option_key) if c["model_id"] == row.model_id), None
        )
        unsupported = capability is not None and (
            capability["chat"]["supported"] is False
            or (bool(row.tools) and capability["tools"]["supported"] is False)
        )
        dependencies = self.dependencies.for_tools(row.tools)
        checks = [
            {
                "id": "configuration",
                "status": "passed" if configured else "needs_setup",
                "message": "Model connection is configured."
                if configured
                else "Configure a provider and model first.",
            }
        ]
        for name in ("chat", "streaming", *(("tools",) if row.tools else ())):
            value = capability[name] if capability else {"supported": None, "verified": False}
            checks.append(
                {
                    "id": name,
                    "capability": name,
                    **value,
                    "status": "passed"
                    if value["verified"]
                    else "failed"
                    if value["supported"] is False
                    else "unverified",
                    "message": f"{name.capitalize()} was observed through the native API."
                    if value["verified"]
                    else f"{name.capitalize()} is unsupported."
                    if value["supported"] is False
                    else f"{name.capitalize()} remains unverified; discovery is not a generation test.",
                }
            )
        checks.extend({"id": d["id"], "status": d["status"], "message": d["reason"]} for d in dependencies)
        if option_error:
            checks.append({"id": "model_options", "status": "failed", "message": option_error})
        status = (
            "disabled"
            if not row.enabled
            else "needs_setup"
            if not configured or unsupported
            else "ready"
            if all(c["status"] == "passed" for c in checks)
            else "unverified"
        )
        return {
            "id": row.id,
            "name": row.name,
            "description": row.description,
            "provider_id": row.provider_id,
            "model_id": row.model_id,
            "model_class": CLASSES[state["api"]],
            "api": state["api"],
            "model_options": options,
            "model_options_supported": capability.get("option_fields", []) if capability else [],
            "model_settings": model_settings,
            "input_modalities": input_modalities(capability),
            "input_modality_policy": "provider_advertised; native binary context counting required",
            "tools": row.tools,
            "scope": row.scope,
            "instructions": row.instructions,
            "enabled": row.enabled,
            "revision": row.revision,
            "configured": bool(configured),
            "can_run": bool(row.enabled and configured and state["discovered"] and not unsupported),
            "status": status,
            "checks": checks,
            "dependencies": dependencies,
        }

    @transactional
    async def save_agent(
        self, subject: str, tenant_id: str, values: dict, agent_id: str | None = None
    ) -> dict:
        await self.catalog.authorize(subject, tenant_id, "agents:write")
        if set(values) - {
            "name",
            "description",
            "provider_id",
            "model_id",
            "model_options",
            "tools",
            "scope",
            "instructions",
            "enabled",
        }:
            raise InvalidRequestException("Unsupported agent fields", code="INVALID_AGENT")
        current = await self.scoped(self.agents, tenant_id, agent_id, lock=True) if agent_id else None

        def value(name, default):
            return values.get(name, getattr(current, name) if current else default)

        provider = await self.scoped(self.providers, tenant_id, value("provider_id", ""))
        name, model, tools = (
            value("name", "").strip(),
            value("model_id", ""),
            value("tools", ["search_knowledge"]),
        )
        if (
            not name
            or len(name) > 160
            or model not in provider.model_ids
            or not isinstance(tools, list)
            or not set(tools) <= TOOLS
        ):
            raise InvalidRequestException(
                "Choose a name, configured model and supported tools", code="INVALID_AGENT"
            )
        known = next((c for c in capability_state(provider) if c["model_id"] == model), None)
        if known and (
            known["chat"]["supported"] is False or (tools and known["tools"]["supported"] is False)
        ):
            raise InvalidRequestException(
                "The selected model does not support this conversational agent",
                code="MODEL_CAPABILITY_UNSUPPORTED",
            )
        scope = await self.validate_scope(subject, tenant_id, value("scope", {}))
        instructions, description = value("instructions", ""), value("description", "")
        if len(instructions) > 8000 or len(description) > 2000:
            raise InvalidRequestException(
                "Agent description or instructions are too long", code="INVALID_AGENT"
            )
        row = current or AgentConfiguration(
            id=identifier(), tenant_id=tenant_id, provider_id=provider.id, name=name, model_id=model
        )
        try:
            spec = self.connections.spec(provider, model, value("model_options", {}))
            assert spec.options is not None
            row.model_options = normalized_options(
                api_for(provider.kind, provider.api), value("model_options", {})
            ).model_dump(mode="json", exclude_none=True)
        except ValueError as exc:
            raise InvalidRequestException(str(exc), code="INVALID_MODEL_OPTIONS") from exc
        row.name, row.description, row.provider_id, row.model_id = name, description, provider.id, model
        row.tools, row.scope, row.instructions, row.enabled = (
            list(dict.fromkeys(tools)),
            scope,
            instructions,
            value("enabled", True),
        )
        row.revision = current.revision + 1 if current else 1
        row.updated_at = timestamp()
        row = await self.agents.save(row)
        await self.catalog._audit(subject, tenant_id, "agent.saved", row.id, {"revision": row.revision})
        return await self.agent_dto(row)

    async def list_agents(self, subject: str, tenant_id: str, *, scope: dict | None = None) -> list[dict]:
        if scope is not None:
            await self.validate_scope(subject, tenant_id, scope)
        visible = []
        for row in await self.agents.find_all(tenant_id=tenant_id):
            try:
                await self.validate_scope(subject, tenant_id, scope or {}, row.scope)
            except AccessDenied:
                continue
            visible.append(await self.agent_dto(row))
        if not visible and scope is None:
            await self.catalog.authorize(subject, tenant_id, "chat:use")
        return visible

    async def validate_provider(self, subject: str, tenant_id: str, provider_id: str) -> dict:

        await self.catalog.authorize(subject, tenant_id, "providers:write")
        row = await self.scoped(self.providers, tenant_id, provider_id)
        address = self.provider_address(row.kind, row.base_url)
        revision = row.revision
        secret = (
            self.secrets.decrypt(tenant_id, row.id, row.secret_ciphertext) if row.secret_ciphertext else None
        )
        checks = await self.probe.check(row.kind, address, row.model_ids, secret, api=row.api)
        await self._save_validation(subject, tenant_id, row.id, revision, checks)
        state = provider_state(await self.providers.find_by_id(row.id))
        return {
            "provider_id": row.id,
            "revision": revision,
            "checks": checks,
            "connected": state["connected"],
            "discovered": state["discovered"],
            "status": "needs_setup"
            if any(c["chat"]["supported"] is False for c in state["model_capabilities"])
            else "ready"
            if state["validated"]
            else "unverified"
            if state["discovered"]
            else "needs_setup",
        }

    @transactional
    async def _save_validation(
        self, subject: str, tenant_id: str, provider_id: str, revision: int, checks: list[dict]
    ):
        await self.catalog.authorize(subject, tenant_id, "providers:write")
        row = await self.providers.find_by_id(provider_id, lock=LockMode.PESSIMISTIC_WRITE)
        if row is None or row.tenant_id != tenant_id or row.revision != revision:
            raise ConflictException(
                "Provider settings changed during validation. Validate them again.",
                code="CONFIGURATION_CHANGED",
            )
        row.checks = checks
        row.validated_revision = (
            revision
            if all(
                any(c["id"] == name and c["status"] == "passed" for c in checks)
                for name in ("connection", "models")
            )
            else 0
        )
        await self.providers.save(row)
        await self.catalog._audit(
            subject,
            tenant_id,
            "provider.validated",
            row.id,
            {"revision": revision, "passed": row.validated_revision == revision},
        )

    async def validate_agent(self, subject: str, tenant_id: str, agent_id: str) -> dict:
        await self.catalog.authorize(subject, tenant_id, "agents:write")
        row = await self.scoped(self.agents, tenant_id, agent_id)
        await self.validate_scope(subject, tenant_id, row.scope)
        await self.validate_provider(subject, tenant_id, row.provider_id)
        return await self.agent_dto(row)

    @transactional(read_only=True)
    async def agent_page(
        self,
        subject,
        tenant_id,
        *,
        q="",
        page=1,
        page_size=25,
        status=None,
        sort="name",
        order="asc",
        workspace_id=None,
        project_id=None,
    ):
        from koinon.web.pagination import sql_page

        requested = {
            key: value
            for key, value in {"workspace_id": workspace_id, "project_id": project_id}.items()
            if value
        }
        visible = await self.list_agents(subject, tenant_id, scope=requested or None)
        if status not in {None, "ready", "needs_setup", "unverified", "disabled"}:
            raise InvalidRequestException("Choose a supported agent status", code="INVALID_FILTER")
        admitted = {row["id"]: row for row in visible if status is None or row["status"] == status}
        result = await sql_page(
            AgentConfiguration,
            [AgentConfiguration.tenant_id == tenant_id, AgentConfiguration.id.in_(admitted)],
            page=page,
            page_size=page_size,
            q=q,
            search=("name", "description"),
            sort=sort,
            order=order,
            sorts=("name", "created_at", "updated_at"),
        )
        return {**result, "items": [admitted[row.id] for row in result["items"]]}

    @transactional
    async def record_runtime_qualification(
        self,
        tenant_id: str,
        provider_id: str,
        revision: int,
        model_id: str,
        observed_tools: list[str],
        model_options: dict | None = None,
    ) -> None:
        row = await self.providers.find_by_id(provider_id, lock=LockMode.PESSIMISTIC_WRITE)
        if (
            row is None
            or row.tenant_id != tenant_id
            or row.revision != revision
            or model_id not in row.model_ids
        ):
            return
        option_key = options_fingerprint(api_for(row.kind, row.api), model_options)
        checks = list(row.checks)
        for capability in ("chat", "streaming", *(("tools",) if observed_tools else ())):
            key = f"observed:{model_id}:{capability}:{option_key}"
            previous = next((c for c in checks if c["id"] == key), {})
            checks = [c for c in checks if c["id"] != key]
            check = {
                "id": key,
                "model_id": model_id,
                "capability": capability,
                "status": "passed",
                "supported": True,
                "verified": True,
                "options_key": option_key,
                "observed_at": timestamp().isoformat(),
                "message": f"{capability.capitalize()} observed in a completed native run.",
            }
            if capability == "tools":
                check["observed_tools"] = sorted(
                    set(previous.get("observed_tools", [])) | set(observed_tools)
                )
            checks.append(check)
        observed = [c for c in checks if c.get("verified")][-64:]
        row.checks = [c for c in checks if not c.get("verified")] + observed
        await self.providers.save(row)
