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
