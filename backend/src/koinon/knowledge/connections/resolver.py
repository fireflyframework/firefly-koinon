# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Resolve only trusted operation roles, after canonical authority and before secrets."""

from contextlib import AsyncExitStack, asynccontextmanager
from importlib import import_module
from json import dumps
from uuid import UUID

from pyfly.container import Container, service
from pyfly.data.relational.datasource_registry import DataSourceRegistry
from pyfly.data.transaction import infrastructure_unit
from pyfly.kernel import ServiceUnavailableException
from sqlalchemy import text

from koinon.assistants.connections import ConnectionResolver, api_for, options_fingerprint
from koinon.assistants.model_bindings import current_model_binding
from koinon.assistants.repositories import ProviderRepository
from koinon.assistants.settings import ProviderSecrets
from koinon.catalog.errors import AccessDenied
from koinon.knowledge.connections.embeddings import open_embedding
from koinon.knowledge.connections.roles import PERMISSIONS, ROLES
from koinon.knowledge.connections.service import KnowledgeConnectionService, embedding_fingerprint
from koinon.knowledge.model_bindings import DomainConnections, KnowledgeConnectionResolver
from koinon.knowledge.repositories import DomainBindingRepository


def prerequisite(detail, code="KNOWLEDGE_CONNECTION_REQUIRED"):
    return ServiceUnavailableException(detail, code=code)


@service(name="knowledge.connection_resolver")
class PersistedKnowledgeConnectionResolver(KnowledgeConnectionResolver):
    def __init__(
        self,
        assignments: KnowledgeConnectionService,
        bindings: DomainBindingRepository,
        providers: ProviderRepository,
        compiler: ConnectionResolver,
        secrets: ProviderSecrets,
        container: Container,
        datasources: DataSourceRegistry,
    ):
        self.assignments, self.bindings, self.providers = assignments, bindings, providers
        self.compiler, self.secrets, self.container, self.datasources = (
            compiler,
            secrets,
            container,
            datasources,
        )

    async def workspace(self, subject, tenant_id, domain, workspace_id, purpose, catalog_workspace_id=None):
        permission = PERMISSIONS[purpose]
        if catalog_workspace_id is not None:
            await self.assignments.authority(subject, tenant_id, catalog_workspace_id, permission=permission)
        rows = await self.bindings.find_all(
            tenant_id=tenant_id,
            domain=domain,
            entity_kind="workspace",
            native_id=workspace_id,
            native_workspace_id=workspace_id,
        )
        allowed = []
        for row in rows:
            if catalog_workspace_id is not None and row.catalog_id != catalog_workspace_id:
                continue
            try:
                await self.assignments.authority(subject, tenant_id, row.catalog_id, permission=permission)
            except AccessDenied:
                continue
            if row.workspace_id == row.catalog_id:
                allowed.append(row.catalog_id)
        allowed = list(dict.fromkeys(allowed))
        if len(allowed) != 1:
            raise prerequisite(
                "Select one authorized canonical workspace binding for this native operation",
                "KNOWLEDGE_WORKSPACE_BINDING_REQUIRED",
            )
        return allowed[0]

    async def embedding_profile(self, domain, tenant_id, workspace_id, row, provider):
        if row.embedding_fingerprint != embedding_fingerprint(
            provider, row.model_id, row.dimensions, row.storage_dimensions
        ):
            raise prerequisite(
                "The embedding connection changed; qualify a reindex before rebinding",
                "KNOWLEDGE_EMBEDDING_REINDEX_REQUIRED",
            )
        if domain == "canon":
            try:
                source = self.datasources.get("canon")
            except KeyError as error:
                raise prerequisite(
                    "Enable document data and apply its migrations", "KNOWLEDGE_INDEX_REQUIRED"
                ) from error
            async with infrastructure_unit(source) as session:
                result = await session.execute(
                    text(
                        "SELECT s.id,s.provider,s.model,s.dimensions,s.config_fingerprint "
                        "FROM canon_embedding_sets s JOIN canon_workspaces w "
                        "ON w.id=s.workspace_id AND w.tenant_id=s.tenant_id "
                        "WHERE s.tenant_id=:tenant AND s.workspace_id=:workspace "
                        "AND s.id=w.active_embedding_set_id"
                    ),
                    {"tenant": tenant_id, "workspace": workspace_id},
                )
                indexed = result.mappings().one_or_none()
            if (
                indexed is None
                or row.space_id not in {indexed["id"], "profile:" + indexed["config_fingerprint"]}
                or (provider.kind, row.model_id, row.dimensions, row.storage_dimensions)
                != (indexed["provider"], indexed["model"], indexed["dimensions"], indexed["dimensions"])
            ):
                raise prerequisite(
                    "Bind the active compatible document index; changing model or width requires reindex",
                    "KNOWLEDGE_EMBEDDING_REINDEX_REQUIRED",
                )
            if await self.assignments.connections.find_conflicting_embedding_history(
                tenant_id,
                row.role,
                (indexed["id"], "profile:" + indexed["config_fingerprint"]),
                row.embedding_fingerprint,
            ):
                raise prerequisite(
                    "The active embedding space has a different connection history; reindex before rebinding",
                    "KNOWLEDGE_EMBEDDING_REINDEX_REQUIRED",
                )
            return indexed["id"]
        async with infrastructure_unit(self.datasources.get("structured")) as session:
            exists = await session.scalar(text("SELECT to_regclass('public.flyquery_embedding_sets')"))
            indexed = (
                (
                    await session.execute(
                        text(
                            "SELECT id,provider,model,dimensions,config_fingerprint FROM flyquery"
                            "_embedding_sets WHERE tenant_id=:tenant AND workspace_id=:workspace "
                            "AND status='active'"
                        ),
                        {"tenant": tenant_id, "workspace": UUID(workspace_id)},
                    )
                )
                .mappings()
                .one_or_none()
                if exists
                else None
            )
        if indexed is not None or row.space_id.startswith("fs-"):
            if (
                indexed is None
                or row.space_id != indexed["id"]
                or (
                    provider.kind,
                    row.model_id,
                    row.dimensions,
                    row.storage_dimensions,
                    row.embedding_fingerprint,
                )
                != (
                    indexed["provider"],
                    indexed["model"],
                    indexed["dimensions"],
                    1536,
                    indexed["config_fingerprint"],
                )
            ):
                raise prerequisite(
                    "Bind the current qualified structured version; review any interrupted activation",
                    "KNOWLEDGE_EMBEDDING_REINDEX_REQUIRED",
                )
            return indexed["id"]
        from flyquery.config import FlyquerySettings
        from flyquery.core.services.retrieval.embedder import deployment_embedding_space

        if not self.container.contains_type(FlyquerySettings):
            raise prerequisite(
                "Enable structured data and its indexed embedding profile", "KNOWLEDGE_INDEX_REQUIRED"
            )
        settings = self.container.resolve(FlyquerySettings)
        if (
            row.space_id != deployment_embedding_space(settings)
            or provider.kind != settings.embedding_provider
            or row.model_id != settings.embedding_model
            or row.dimensions != settings.embedding_native_dim
            or row.storage_dimensions != settings.embedding_dimensions
            or row.storage_dimensions != 1536
        ):
            raise prerequisite(
                "Bind the qualified structured profile; model or width changes require reindex",
                "KNOWLEDGE_EMBEDDING_REINDEX_REQUIRED",
            )
        async with infrastructure_unit(self.datasources.get("structured")) as session:
            result = await session.execute(
                text(
                    "SELECT DISTINCT embedding_model FROM flyquery_schema_objects "
                    "WHERE tenant_id=:tenant AND workspace_id=:workspace AND embedding IS NOT NULL"
                ),
                {"tenant": tenant_id, "workspace": UUID(workspace_id)},
            )
            indexed_models = result.scalars().all()
        if any(model != row.model_id for model in indexed_models):
            raise prerequisite(
                "Existing structured vectors have a different or unknown model; reindex first",
                "KNOWLEDGE_EMBEDDING_REINDEX_REQUIRED",
            )
        return row.space_id

    @asynccontextmanager
    async def resolve(
        self, *, domain, tenant_id, workspace_id, subject, purpose, roles, catalog_workspace_id=None
    ):
        public_domain = {"canon": "documents", "structured": "structured"}.get(domain)
        if (
            purpose not in PERMISSIONS
            or not roles
            or len(roles) > 16
            or len(set(roles)) != len(roles)
            or any(
                role not in ROLES
                or ROLES[role].domain != public_domain
                or purpose not in ROLES[role].purposes
                for role in roles
            )
        ):
            raise prerequisite(
                "The trusted adapter requested an unsupported knowledge role or purpose",
                "KNOWLEDGE_ROLE_SCOPE_INVALID",
            )
        workspace = await self.workspace(
            subject, tenant_id, domain, str(workspace_id), purpose, catalog_workspace_id
        )
        if await self.assignments.connections.pending_index(tenant_id, public_domain, str(workspace_id)):
            raise prerequisite(
                "An index activation needs explicit finish or restore recovery", "KNOWLEDGE_INDEX_ACTIVATING"
            )
        port = import_module(
            ("flycanon" if domain == "canon" else "flyquery") + ".core.agents.model_bindings"
        )
        planned = []
        for role in roles:
            row = await self.assignments.selected(tenant_id, workspace, public_domain, role)
            if row is None or not row.enabled:
                raise prerequisite(
                    f"Configure and enable the authorized connection for {role}",
                    "KNOWLEDGE_MODEL_BINDING_REQUIRED",
                )
            if row.mode == "current_agent":
                if ROLES[role].embedding:
                    raise prerequisite(
                        "Embedding roles require a separate explicit connection",
                        "KNOWLEDGE_EMBEDDING_BINDING_REQUIRED",
                    )
                borrowed = current_model_binding(tenant_id, subject)
                if borrowed is None:
                    raise prerequisite(
                        f"Select an agent connection before using {role}", "KNOWLEDGE_CURRENT_AGENT_REQUIRED"
                    )
                planned.append((role, row, None, borrowed, None))
                continue
            providers = await self.providers.find_all(tenant_id=tenant_id, id=row.provider_id)
            if not providers or not providers[0].enabled or row.model_id not in providers[0].model_ids:
                raise prerequisite(
                    f"Enable a declared provider/model for {role}", "KNOWLEDGE_PROVIDER_UNAVAILABLE"
                )
            provider = providers[0]
            if provider.kind != "ollama" and not provider.secret_ciphertext:
                raise prerequisite(
                    f"Configure the provider credential for {role}", "KNOWLEDGE_PROVIDER_CREDENTIAL_REQUIRED"
                )
            if ROLES[role].embedding:
                profile = await self.embedding_profile(domain, tenant_id, str(workspace_id), row, provider)
                planned.append((role, row, provider, None, profile))
            else:
                try:
                    spec = self.compiler.spec(provider, row.model_id, row.model_options)
                except ValueError as error:
                    raise prerequisite(
                        f"Configure compatible native options for {role}", "KNOWLEDGE_MODEL_OPTIONS_INVALID"
                    ) from error
                planned.append((role, row, provider, spec, None))
        selected, embedded, cache = {}, {}, {}
        async with AsyncExitStack() as lifetime:
            for role, row, provider, spec, profile in planned:
                await self.assignments.authority(
                    subject, tenant_id, workspace, permission=PERMISSIONS[purpose]
                )
                if row.mode == "current_agent":
                    selected[role] = port.ModelBinding(
                        spec.model,
                        spec.model_settings,
                        spec.provider,
                        spec.api,
                        spec.output_mode,
                        provenance=port.ModelBindingProvenance(
                            mode="current_agent",
                            assignment_id=row.id,
                            assignment_revision=row.revision,
                            provider_id=spec.provider_id,
                            provider_revision=spec.provider_revision,
                            selected_model_id=spec.model_id,
                            model_options_sha256=spec.options_sha256,
                            agent_id=spec.agent_id,
                            agent_revision=spec.agent_revision,
                        ),
                    )
                    continue
                if ROLES[role].embedding:
                    embedder = await lifetime.enter_async_context(
                        open_embedding(self.compiler, self.secrets, provider, row.model_id, row.dimensions)
                    )
                    embedded[role] = port.EmbeddingBinding(
                        embedder,
                        f"{provider.kind}:{row.model_id}",
                        row.dimensions,
                        row.storage_dimensions,
                        profile,
                        **(
                            {"versioned": True}
                            if domain == "structured" and profile.startswith("fs-")
                            else {}
                        ),
                    )
                else:
                    secret = (
                        self.secrets.decrypt(tenant_id, provider.id, provider.secret_ciphertext)
                        if provider.secret_ciphertext
                        else "unused"
                    )
                    key = (
                        provider.id,
                        provider.revision,
                        row.model_id,
                        dumps(row.model_options, sort_keys=True),
                    )
                    if key not in cache:
                        cache[key] = await lifetime.enter_async_context(
                            self.compiler.models.build_with_secret(spec, secret)
                        )
                    api = api_for(provider.kind, provider.api)
                    selected[role] = port.ModelBinding(
                        cache[key],
                        self.compiler.settings_for(spec),
                        provider.kind,
                        api,
                        "native" if provider.kind == "ollama" else "default",
                        provenance=port.ModelBindingProvenance(
                            mode="provider",
                            assignment_id=row.id,
                            assignment_revision=row.revision,
                            provider_id=provider.id,
                            provider_revision=provider.revision,
                            selected_model_id=row.model_id,
                            model_options_sha256=options_fingerprint(api, row.model_options),
                        ),
                    )
                    del secret
            await self.assignments.authority(subject, tenant_id, workspace, permission=PERMISSIONS[purpose])
            yield DomainConnections(selected, embedded)
