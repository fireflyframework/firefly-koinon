# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Selected persisted embedding providers; no chat or environment inference."""

from pyfly.container import service
from pyfly.data.relational.sqlalchemy import LockMode
from pyfly.kernel import InvalidRequestException, ServiceUnavailableException

from koinon.assistants.connections import ConnectionResolver
from koinon.assistants.repositories import ProviderRepository
from koinon.assistants.settings import ProviderSecrets
from koinon.catalog.errors import AccessDenied
from koinon.knowledge.connections.embeddings import open_embedding
from koinon.knowledge.indexes.probe import qualify_embedding


@service(name="knowledge.index_planner")
class IndexPlanner:
    def __init__(self, providers: ProviderRepository, compiler: ConnectionResolver, secrets: ProviderSecrets):
        self.providers, self.compiler, self.secrets = providers, compiler, secrets

    async def provider(self, tenant_id, provider_id, model_id):
        rows = await self.providers.find_all(tenant_id=tenant_id, id=provider_id)
        if not rows:
            raise AccessDenied("Provider is unavailable in this organization", code="ACCESS_DENIED")
        provider = await self.providers.find_by_id(provider_id, lock=LockMode.PESSIMISTIC_READ)
        if provider is None or provider.tenant_id != tenant_id:
            raise AccessDenied("Provider is unavailable in this organization", code="ACCESS_DENIED")
        if not provider.enabled:
            raise ServiceUnavailableException(
                "Enable the selected embedding provider", code="INDEX_PROVIDER_DISABLED"
            )
        if model_id not in provider.model_ids or provider.kind not in {"ollama", "openai"}:
            raise InvalidRequestException(
                "Choose a declared native embedding model", code="INVALID_INDEX_PROVIDER"
            )
        return provider

    def open(self, provider, model_id, dimensions=None):
        return open_embedding(self.compiler, self.secrets, provider, model_id, dimensions)

    async def prepare(self, tenant_id, data):
        provider = await self.provider(tenant_id, data.provider_id, data.model_id)
        profile = await qualify_embedding(
            self.open(provider, data.model_id),
            domain=data.domain,
            expected_dimensions=data.expected_dimensions,
        )
        return provider, profile
