# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0


from koinon.api.json_values import portable_json
from koinon.catalog.entities import INTERNAL_METADATA_KEYS, AuditEvent, CatalogEntry


def entry_dto(entry: CatalogEntry) -> dict:
    fields = (
        "id",
        "tenant_id",
        "kind",
        "name",
        "parent_id",
        "workspace_id",
        "project_id",
        "description",
        "status",
        "created_by",
        "updated_by",
    )
    return {
        **{field: getattr(entry, field) for field in fields},
        "system_managed": entry.system_key is not None,
        "metadata": portable_json(
            {key: value for key, value in entry.metadata_json.items() if key not in INTERNAL_METADATA_KEYS}
        ),
        "created_at": entry.created_at.isoformat(),
        "updated_at": entry.updated_at.isoformat(),
    }


def member_dto(member) -> dict:
    return {
        **{
            field: getattr(member, field)
            for field in ("id", "subject", "tenant_id", "workspace_id", "role", "active")
        },
        "managed": getattr(member, "managed", False),
        "origin": getattr(member, "origin", "manual"),
        "source_id": getattr(member, "source_id", None),
        "source_name": getattr(member, "source_name", None),
        "expires_at": member.expires_at.isoformat() if getattr(member, "expires_at", None) else None,
    }


def audit_dto(event: AuditEvent) -> dict:
    return {
        **{field: getattr(event, field) for field in ("id", "tenant_id", "subject", "action", "resource_id")},
        "details": portable_json(event.details),
        "created_at": event.created_at.isoformat(),
    }
