# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from pyfly.container import repository
from pyfly.data.relational.sqlalchemy import Repository
from sqlalchemy import and_, case, exists, func, literal, or_, select
from sqlalchemy.orm import aliased

from koinon.catalog.entities import AuditEvent, CatalogEntry, Membership, Tenant
from koinon.knowledge.curated.entities import CuratedCatalogState, CuratedSourceRoot


def curated_admission(tenant_id, allowed_workspaces, allowed_resources, allowed_assets):
    entry = CatalogEntry
    state, root = CuratedCatalogState, CuratedSourceRoot
    source = aliased(CatalogEntry)
    archived = (
        select(entry.id, literal(0).label("depth"))
        .where(entry.tenant_id == tenant_id, entry.status == "archived")
        .cte("curated_archived", recursive=True)
    )
    child = aliased(CatalogEntry)
    archived = archived.union_all(
        select(child.id, archived.c.depth + 1)
        .join(archived, child.parent_id == archived.c.id)
        .where(child.tenant_id == tenant_id, archived.c.depth < 16)
    )
    invalid = [
        source.id.is_(None),
        source.tenant_id != tenant_id,
        root.tenant_id != tenant_id,
        source.kind.not_in(["document", "dataset"]),
        source.id.in_(select(archived.c.id)),
    ]
    if allowed_workspaces is not None:
        invalid.append(source.workspace_id.not_in(allowed_workspaces))
    if allowed_assets is not None:
        admitted = (
            select(entry.id, literal(0).label("depth"))
            .where(entry.tenant_id == tenant_id, entry.id.in_(allowed_assets))
            .cte("curated_token_admitted", recursive=True)
        )
        node = aliased(CatalogEntry)
        admitted = admitted.union_all(
            select(node.id, admitted.c.depth + 1)
            .join(admitted, node.parent_id == admitted.c.id)
            .where(node.tenant_id == tenant_id, admitted.c.depth < 16)
        )
        invalid.append(~or_(source.id.in_(allowed_resources or []), source.id.in_(select(admitted.c.id))))
    active = func.coalesce(state.serving_version_id, state.head_version_id)
    denied = exists(
        select(root.id)
        .outerjoin(source, source.id == root.source_asset_id)
        .where(root.item_id == entry.id, root.native_version_id == active, or_(*invalid))
        .correlate(entry, state)
    )
    count = (
        select(func.count())
        .select_from(root)
        .where(root.item_id == entry.id, root.native_version_id == active)
        .correlate(entry, state)
        .scalar_subquery()
    )
    visible = exists(
        select(state.item_id)
        .where(
            state.item_id == entry.id,
            state.tenant_id == tenant_id,
            state.workspace_id == entry.workspace_id,
            state.root_count == count,
            ~denied,
        )
        .correlate(entry)
    )
    return or_(entry.kind != "knowledge_item", visible)


@repository
class TenantRepository(Repository[Tenant, str]):
    """Tenant identities."""


@repository
class MembershipRepository(Repository[Membership, str]):
    """Durable grants, resolved for each protected operation."""

    async def find_page(
        self, tenant_id, *, q="", role=None, workspace_id=None, scope="all", page=1, page_size=25
    ):
        from koinon.profiles.entities import Profile

        predicates = [Membership.tenant_id == tenant_id, Membership.active.is_(True)]
        if workspace_id is not None:
            predicates.append(Membership.workspace_id == workspace_id)
        elif scope == "tenant":
            predicates.append(Membership.workspace_id.is_(None))
        if role:
            predicates.append(Membership.role == role)
        if q:
            escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            predicates.append(
                or_(
                    Profile.display_name.ilike(f"%{escaped}%", escape="\\"),
                    Membership.subject.ilike(f"%{escaped}%", escape="\\"),
                )
            )
        statement = (
            select(Membership).outerjoin(Profile, Profile.subject == Membership.subject).where(*predicates)
        )
        session = self._require_session()
        total = int((await session.scalar(select(func.count()).select_from(statement.subquery()))) or 0)
        rows = (
            await session.scalars(
                statement.order_by(
                    func.lower(func.coalesce(Profile.display_name, "")), Membership.subject, Membership.id
                )
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
        return {
            "items": list(rows),
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": (total + page_size - 1) // page_size,
        }


@repository
class CatalogRepository(Repository[CatalogEntry, str]):
    """Scoped catalog entries shared by both domains."""

    async def file_intake_for_key(self, tenant_id, dataset_id, key_sha256):
        return list(
            (
                await self._require_session().scalars(
                    select(CatalogEntry)
                    .where(
                        CatalogEntry.tenant_id == tenant_id,
                        CatalogEntry.parent_id == dataset_id,
                        CatalogEntry.kind == "index_version",
                        CatalogEntry.metadata_json["_koinon_intake"]["key_sha256"].as_string() == key_sha256,
                    )
                    .limit(2)
                )
            ).all()
        )

    async def curated_visible(
        self, tenant_id, entry_id, *, allowed_workspaces=None, allowed_resources=None, allowed_assets=None
    ):
        session = self._require_session()
        return (
            await session.scalar(
                select(CatalogEntry.id).where(
                    CatalogEntry.id == entry_id,
                    CatalogEntry.tenant_id == tenant_id,
                    curated_admission(tenant_id, allowed_workspaces, allowed_resources, allowed_assets),
                )
            )
            is not None
        )

    async def curated_ids(
        self, tenant_id, *, allowed_workspaces=None, allowed_resources=None, allowed_assets=None
    ):
        session = self._require_session()
        return set(
            await session.scalars(
                select(CatalogEntry.id).where(
                    CatalogEntry.tenant_id == tenant_id,
                    CatalogEntry.kind == "knowledge_item",
                    curated_admission(tenant_id, allowed_workspaces, allowed_resources, allowed_assets),
                )
            )
        )

    async def find_page(
        self,
        tenant_id,
        *,
        allowed_workspaces=None,
        allowed_resources=None,
        allowed_assets=None,
        parent=None,
        kind=None,
        workspace_id=None,
        project_id=None,
        include_archived=False,
        view="raw",
        q="",
        status=None,
        page=1,
        page_size=100,
        sort="name",
        order="asc",
    ):
        entry = CatalogEntry
        predicates = [
            entry.tenant_id == tenant_id,
            curated_admission(tenant_id, allowed_workspaces, allowed_resources, allowed_assets),
        ]
        if allowed_workspaces is not None:
            predicates.append(entry.workspace_id.in_(allowed_workspaces))
        if allowed_assets is not None:
            admitted = (
                select(entry.id, literal(0).label("depth"))
                .where(entry.tenant_id == tenant_id, entry.id.in_(allowed_assets))
                .cte("token_admitted", recursive=True)
            )
            descendant = aliased(entry)
            admitted = admitted.union_all(
                select(descendant.id, admitted.c.depth + 1)
                .join(admitted, descendant.parent_id == admitted.c.id)
                .where(descendant.tenant_id == tenant_id, admitted.c.depth < 16)
            )
            predicates.append(or_(entry.id.in_(allowed_resources or []), entry.id.in_(select(admitted.c.id))))
        if workspace_id:
            predicates.append(entry.workspace_id == workspace_id)
        if project_id:
            predicates.append(entry.project_id == project_id)
        if kind:
            predicates.append(entry.kind == kind)
        if status:
            predicates.append(entry.status == status)
        if q:
            escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            predicates.append(entry.name.ilike(f"%{escaped}%", escape="\\"))
        if not include_archived:
            hidden = (
                select(entry.id, literal(0).label("depth"))
                .where(entry.tenant_id == tenant_id, entry.status == "archived")
                .cte("archived_ancestry", recursive=True)
            )
            child = aliased(entry)
            hidden = hidden.union_all(
                select(child.id, hidden.c.depth + 1)
                .join(hidden, child.parent_id == hidden.c.id)
                .where(child.tenant_id == tenant_id, hidden.c.depth < 16)
            )
            predicates.append(entry.id.not_in(select(hidden.c.id)))
        if parent is not None:
            if view == "library" and parent.kind in {"collection", "corpus"}:
                source = aliased(entry)
                assets = aliased(entry)
                source_ids = select(source.id).where(
                    source.tenant_id == tenant_id, source.parent_id == parent.id, source.kind == "source"
                )
                has_assets = exists(
                    select(assets.id).where(
                        assets.tenant_id == tenant_id,
                        assets.parent_id == entry.id,
                        assets.kind.in_(["document", "dataset"]),
                    )
                )
                predicates.append(
                    or_(
                        and_(entry.parent_id.in_(source_ids), entry.kind.in_(["document", "dataset"])),
                        and_(entry.parent_id == parent.id, entry.kind == "source", ~has_assets),
                        and_(entry.parent_id == parent.id, entry.kind == "knowledge_item"),
                    )
                )
            else:
                predicates.append(entry.parent_id == parent.id)
        if view == "library":
            predicates.append(
                entry.kind.in_(
                    [
                        "workspace",
                        "project",
                        "collection",
                        "corpus",
                        "source",
                        "document",
                        "dataset",
                        "knowledge_item",
                    ]
                )
            )
        statement = select(entry).where(*predicates)
        session = self._require_session()
        total = int((await session.scalar(select(func.count()).select_from(statement.subquery()))) or 0)
        column = func.lower(entry.name) if sort == "name" else getattr(entry, sort)
        ordered = column.desc() if order == "desc" else column.asc()
        folders = case((entry.kind.in_(["workspace", "project", "collection", "corpus"]), 0), else_=1)
        rows = (
            await session.scalars(
                statement.order_by(folders, ordered, entry.id).offset((page - 1) * page_size).limit(page_size)
            )
        ).all()
        return {
            "items": list(rows),
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": (total + page_size - 1) // page_size,
        }


@repository
class AuditRepository(Repository[AuditEvent, str]):
    """Append-only application audit records."""

    async def find_page(
        self,
        tenant_id,
        *,
        q="",
        action=None,
        subject=None,
        start=None,
        end=None,
        page=1,
        page_size=25,
        sort="created_at",
        order="desc",
    ):
        from koinon.profiles.entities import Profile

        predicates = [AuditEvent.tenant_id == tenant_id]
        if action:
            predicates.append(AuditEvent.action == action)
        if subject:
            predicates.append(AuditEvent.subject == subject)
        if start:
            predicates.append(AuditEvent.created_at >= start)
        if end:
            predicates.append(AuditEvent.created_at < end)
        statement = (
            select(AuditEvent)
            .outerjoin(Profile, Profile.subject == AuditEvent.subject)
            .outerjoin(
                CatalogEntry,
                and_(
                    CatalogEntry.id == AuditEvent.resource_id, CatalogEntry.tenant_id == AuditEvent.tenant_id
                ),
            )
        )
        if q:
            escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            predicates.append(
                or_(
                    *(
                        column.ilike(f"%{escaped}%", escape="\\")
                        for column in (
                            Profile.display_name,
                            AuditEvent.action,
                            CatalogEntry.name,
                            AuditEvent.resource_id,
                            AuditEvent.subject,
                        )
                    )
                )
            )
        statement = statement.where(*predicates)
        session = self._require_session()
        total = int((await session.scalar(select(func.count()).select_from(statement.subquery()))) or 0)
        column = AuditEvent.created_at if sort == "created_at" else AuditEvent.action
        ordered = column.desc() if order == "desc" else column.asc()
        rows = (
            await session.scalars(
                statement.order_by(ordered, AuditEvent.id).offset((page - 1) * page_size).limit(page_size)
            )
        ).all()
        return {
            "items": list(rows),
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": (total + page_size - 1) // page_size,
        }
