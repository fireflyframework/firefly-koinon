# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Complete active folder paths for scoped operation history, before count and page."""

from collections.abc import Callable

from sqlalchemy import and_, literal, or_, select
from sqlalchemy.orm import aliased
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.sql.selectable import CTE, Select

from koinon.catalog.ancestry import MAX_FOLDER_ANCESTRY
from koinon.catalog.entities import CatalogEntry


def active_folder_roots(
    tenant: str,
    roots: Select[str] | Select[str | None],
    visible: Callable[[type[CatalogEntry]], ColumnElement[bool]],
    *,
    name: str,
) -> CTE:
    # Local import avoids the CatalogService/Repository composition cycle.
    from koinon.catalog.service import PARENTS

    leaf, parent = aliased(CatalogEntry), aliased(CatalogEntry)
    path = (
        select(
            leaf.id.label("root_id"),
            leaf.id.label("id"),
            leaf.parent_id,
            leaf.kind,
            leaf.workspace_id,
            leaf.project_id,
            literal(1).label("depth"),
        )
        .where(
            leaf.id.in_(roots),
            leaf.tenant_id == tenant,
            leaf.kind.in_(["collection", "corpus"]),
            leaf.workspace_id.is_not(None),
            leaf.project_id.is_not(None),
            visible(leaf),
        )
        .cte(name + "_path", recursive=True)
    )
    transitions = or_(
        *(
            and_(
                path.c.kind == kind, parent.kind.in_([value for value in PARENTS[kind] if value is not None])
            )
            for kind in ("collection", "corpus", "project")
        )
    )
    path = path.union_all(
        select(
            path.c.root_id,
            parent.id,
            parent.parent_id,
            parent.kind,
            path.c.workspace_id,
            path.c.project_id,
            path.c.depth + 1,
        )
        .join(path, parent.id == path.c.parent_id)
        .where(
            parent.tenant_id == tenant,
            parent.workspace_id == path.c.workspace_id,
            or_(
                and_(
                    parent.kind == "workspace", parent.id == path.c.workspace_id, parent.project_id.is_(None)
                ),
                and_(parent.kind != "workspace", parent.project_id == path.c.project_id),
            ),
            or_(parent.kind != "project", parent.id == path.c.project_id),
            transitions,
            visible(parent),
            path.c.depth < MAX_FOLDER_ANCESTRY,
        )
    )
    return (
        select(path.c.root_id, path.c.workspace_id, path.c.project_id)
        .where(path.c.kind == "workspace", path.c.parent_id.is_(None), path.c.depth >= 3)
        .cte(name)
    )
