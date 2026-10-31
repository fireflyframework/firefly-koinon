# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from koinon.knowledge.connections.entities import KnowledgeConnection


def connection_dto(row: KnowledgeConnection) -> dict:
    result = {
        name: getattr(row, name)
        for name in (
            "id",
            "tenant_id",
            "workspace_id",
            "domain",
            "role",
            "mode",
            "provider_id",
            "model_id",
            "model_options",
            "dimensions",
            "storage_dimensions",
            "space_id",
            "embedding_fingerprint",
            "enabled",
            "revision",
            "created_by",
            "updated_by",
        )
    }
    return {**result, "created_at": row.created_at.isoformat(), "updated_at": row.updated_at.isoformat()}


def dependency_configuration(row, provider):
    if row is None:
        return None
    admitted = provider if provider is not None and row.model_id in provider.model_ids else None
    return {
        "scope": "tenant" if row.workspace_id is None else "workspace",
        "mode": row.mode,
        "enabled": row.enabled,
        "provider": admitted.kind if admitted is not None else None,
        "model_id": row.model_id if admitted is not None else None,
        "configured": bool(
            row.enabled
            and admitted is not None
            and admitted.enabled
            and (admitted.kind == "ollama" or admitted.secret_ciphertext)
        ),
    }
