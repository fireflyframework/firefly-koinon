# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Current persisted role readiness; this does not claim a live model evaluation."""

from pyfly.container import service
from pyfly.data.relational.sqlalchemy import LockMode, transactional
from pyfly.kernel import ServiceUnavailableException

from koinon.assistants.connections import api_for, options_fingerprint
from koinon.knowledge.connections.roles import ROLES
from koinon.knowledge.connections.service import KnowledgeConnectionService


@service(name="organization_knowledge.mode_role_readiness")
class ModeRoleReadiness:
    def __init__(self, connections: KnowledgeConnectionService):
        self.connections = connections

    @transactional(read_only=True)
    async def check(self, subject, tenant_id, workspace_id, mode, *, has_documents=True, lock=False):
        if mode not in {"rag", "rlm"}:
            raise ValueError("Select a document answer mode")
        await self.connections.authority(subject, tenant_id, workspace_id)
        roles = ["documents.rlm"] if mode == "rlm" else ["documents.answer"]
        if mode == "rag" and has_documents:
            roles.insert(0, "documents.embedding")
        result = {}
        for role in roles:
            row = await self.connections.selected(tenant_id, workspace_id, "documents", role)
            if row is not None and lock:
                row = await self.connections.connections.find_by_id(row.id, lock=LockMode.PESSIMISTIC_READ)
            if row is None or not row.enabled:
                raise ServiceUnavailableException(
                    f"Configure and enable {role} before preparing this mode",
                    code="KNOWLEDGE_MODEL_BINDING_REQUIRED",
                )
            pin = {
                "assignment_id": row.id,
                "assignment_revision": row.revision,
                "requires_current_agent": row.mode == "current_agent",
                "provider_id": row.provider_id,
                "provider_revision": None,
                "model_id": row.model_id,
                "space_id": row.space_id,
                "embedding_fingerprint": row.embedding_fingerprint,
                "dimensions": row.dimensions,
                "storage_dimensions": row.storage_dimensions,
                "options_sha256": None,
            }
            if row.mode == "current_agent":
                if ROLES[role].embedding:
                    raise ServiceUnavailableException(
                        "Embedding roles require an explicit provider",
                        code="KNOWLEDGE_EMBEDDING_BINDING_REQUIRED",
                    )
                result[role] = pin
                continue
            providers = await self.connections.providers.find_all(tenant_id=tenant_id, id=row.provider_id)
            if not providers or not providers[0].enabled or row.model_id not in providers[0].model_ids:
                raise ServiceUnavailableException(
                    f"Enable the declared provider and model for {role}",
                    code="KNOWLEDGE_PROVIDER_UNAVAILABLE",
                )
            provider = providers[0]
            if lock:
                provider = await self.connections.providers.find_by_id(
                    provider.id, lock=LockMode.PESSIMISTIC_READ
                )
                if provider is None or not provider.enabled or row.model_id not in provider.model_ids:
                    raise ServiceUnavailableException(
                        "The selected model provider changed", code="KNOWLEDGE_PROVIDER_UNAVAILABLE"
                    )
            if provider.kind != "ollama" and not provider.secret_ciphertext:
                raise ServiceUnavailableException(
                    f"Configure the provider credential for {role}",
                    code="KNOWLEDGE_PROVIDER_CREDENTIAL_REQUIRED",
                )
            try:
                if not ROLES[role].embedding:
                    self.connections.compiler.spec(provider, row.model_id, row.model_options)
                options = options_fingerprint(api_for(provider.kind, provider.api), row.model_options)
            except ValueError as error:
                raise ServiceUnavailableException(
                    f"Configure compatible model options for {role}", code="KNOWLEDGE_MODEL_OPTIONS_INVALID"
                ) from error
            result[role] = {**pin, "provider_revision": provider.revision, "options_sha256": options}
        return result
