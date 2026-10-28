# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0


from pyfly.container import service
from pyfly.kernel import InvalidRequestException

from koinon.catalog.errors import AccessDenied
from koinon.catalog.service import CatalogService

SCOPE_FIELDS = frozenset({"workspace_id", "project_id", "collection_id", "asset_ids"})


@service(name="assistants.scope")
class KnowledgeScopePolicy:
    def __init__(self, catalog: CatalogService):
        self.catalog = catalog

    async def validate_scope(
        self, subject: str, tenant_id: str, requested: dict, limit: dict | None = None
    ) -> dict:
        if set(requested) - SCOPE_FIELDS or (limit is not None and set(limit) - SCOPE_FIELDS):
            raise InvalidRequestException("Unsupported knowledge scope", code="INVALID_SCOPE")
        scope = {key: value for key, value in (limit or {}).items() if value is not None}
        for key, value in requested.items():
            if value is None:
                continue
            if key in scope and key != "asset_ids" and scope[key] != value:
                raise AccessDenied("Selected knowledge exceeds the agent's scope", code="SCOPE_DENIED")
            if key == "asset_ids":
                if (
                    not isinstance(value, list)
                    or len(value) > 128
                    or any(not isinstance(v, str) for v in value)
                ):
                    raise InvalidRequestException("Select up to 128 knowledge items", code="INVALID_SCOPE")
                if key in scope and not set(value).issubset(scope[key]):
                    raise AccessDenied("Selected knowledge exceeds the agent's scope", code="SCOPE_DENIED")
                value = list(dict.fromkeys(value))
            scope[key] = value
        selected = []
        for key, kind in (
            ("workspace_id", "workspace"),
            ("project_id", "project"),
            ("collection_id", "collection"),
        ):
            if key in scope:
                entry = await self.catalog.get(subject, tenant_id, scope[key])
                allowed = {"collection", "corpus"} if kind == "collection" else {kind}
                if entry.kind not in allowed:
                    raise InvalidRequestException(
                        "Selected knowledge has an incompatible type", code="INVALID_SCOPE"
                    )
                selected.append(entry)
        for entry_id in scope.get("asset_ids", []):
            entry = await self.catalog.get(subject, tenant_id, entry_id)
            if entry.kind not in {"document", "dataset", "knowledge_item"}:
                raise InvalidRequestException(
                    "Choose documents, datasets, or committed knowledge", code="INVALID_SCOPE"
                )
            selected.append(entry)
        for entry in selected:
            chain, seen, current = {}, set(), entry
            while current is not None:
                if current.id in seen or len(seen) > 16:
                    raise InvalidRequestException("Knowledge ancestry is invalid", code="INVALID_SCOPE")
                seen.add(current.id)
                chain["collection" if current.kind == "corpus" else current.kind] = current.id
                current = (
                    await self.catalog.get(subject, tenant_id, current.parent_id)
                    if current.parent_id
                    else None
                )
            for key, kind in (
                ("workspace_id", "workspace"),
                ("project_id", "project"),
                ("collection_id", "collection"),
            ):
                if key in scope and kind in chain and chain[kind] != scope[key]:
                    raise AccessDenied("Selected knowledge belongs to another folder", code="SCOPE_DENIED")
        await self.catalog.authorize(subject, tenant_id, "chat:use", scope.get("workspace_id"))
        return scope
