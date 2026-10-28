# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0


def index_dto(row, *, management=True):
    result = {
        name: getattr(row, name)
        for name in (
            "id",
            "tenant_id",
            "workspace_id",
            "domain",
            "native_id",
            "provider_kind",
            "model_id",
            "dimensions",
            "storage_dimensions",
            "status",
            "revision",
            "job_id",
            "chunk_count",
            "vector_count",
            "indexed",
            "qualification",
            "error_code",
            "error",
        )
    }
    result.update(space_id=row.native_id, active=row.status == "active")
    for name in ("created_at", "ready_at", "activated_at", "retired_at"):
        value = getattr(row, name)
        result[name] = value.isoformat() if value else None
    result["recovery_required"] = row.status == "activating"
    if management:
        result["provider_id"] = row.provider_id
        result["created_by"], result["updated_by"] = row.created_by, row.updated_by
        result["previous_space_id"] = (row.transition or {}).get("previous_native_id")
    return result
