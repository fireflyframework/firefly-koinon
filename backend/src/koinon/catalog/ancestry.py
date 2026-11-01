# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Bounded catalog ancestry checks shared by creation and folder movement."""

from collections.abc import Awaitable, Callable, Mapping

from koinon.catalog.entities import CatalogEntry
from koinon.catalog.errors import InvalidHierarchy

MAX_ANCESTRY = 16
MAX_FOLDER_ANCESTRY = 12


async def validated_ancestry(
    entry: CatalogEntry,
    read: Callable[[str], Awaitable[CatalogEntry]],
    parents: Mapping[str, frozenset[str | None]],
) -> list[CatalogEntry]:
    chain, seen = [], set()
    current = entry
    while True:
        if current.id in seen or len(chain) >= MAX_ANCESTRY:
            raise InvalidHierarchy("Catalog ancestry is cyclic or too deep", code="INVALID_ANCESTRY")
        seen.add(current.id)
        chain.append(current)
        if current.status == "archived":
            raise InvalidHierarchy("Choose an active destination folder", code="RESOURCE_ARCHIVED")
        if current.parent_id is None:
            break
        current = await read(current.parent_id)
    workspace = chain[-1]
    project = next((node.id for node in chain if node.kind == "project"), None)
    if workspace.kind != "workspace" or workspace.project_id is not None:
        raise InvalidHierarchy("The folder has no knowledge space", code="INVALID_ANCESTRY")
    for position, node in enumerate(chain):
        parent = chain[position + 1] if position + 1 < len(chain) else None
        if (
            node.tenant_id != workspace.tenant_id
            or node.workspace_id != workspace.id
            or (node.kind != "workspace" and node.project_id != project)
            or (parent.kind if parent else None) not in parents.get(node.kind, ())
        ):
            raise InvalidHierarchy(
                "Folder ancestry disagrees with its knowledge scope", code="INVALID_ANCESTRY"
            )
    return chain
