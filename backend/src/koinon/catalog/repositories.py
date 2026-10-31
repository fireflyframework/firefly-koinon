# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from pyfly.container import repository
from pyfly.data.relational.sqlalchemy import Repository
from sqlalchemy import JSON, Text, and_, case, cast, column, exists, func, literal, or_, select
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import aliased
from sqlalchemy.sql.elements import ColumnElement

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
        from koinon.corporate_profiles.expressions import presentation_joins
        from koinon.organization_people.entities import OrganizationPersonRecord

        statement = (
            select(Membership)
            .outerjoin(Profile, Profile.subject == Membership.subject)
            .outerjoin(
                OrganizationPersonRecord,
                and_(
                    OrganizationPersonRecord.tenant_id == tenant_id,
                    OrganizationPersonRecord.subject == Membership.subject,
                ),
            )
        )
        statement, display_name = presentation_joins(statement, Membership.subject, tenant_id, Profile)
        if q:
            escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            predicates.append(
                or_(
                    display_name.ilike(f"%{escaped}%", escape="\\"),
                    Membership.subject.ilike(f"%{escaped}%", escape="\\"),
                )
            )
        statement = statement.where(*predicates)
        session = self._require_session()
        total = int((await session.scalar(select(func.count()).select_from(statement.subquery()))) or 0)
        rows = (
            await session.scalars(
                statement.order_by(func.lower(display_name), Membership.subject, Membership.id)
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
        format=None,
        tag=None,
        page=1,
        page_size=100,
        sort="name",
        order="asc",
    ):
        entry = CatalogEntry
        predicates: list[ColumnElement[bool]] = [
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
        visible = select(entry.id).where(*predicates).cte("catalog_visible")
        predicates = [entry.id.in_(select(visible.c.id))]
        if kind:
            predicates.append(entry.kind == kind)
        if status:
            predicates.append(entry.status == status)
        if q:
            escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            predicates.append(entry.name.ilike(f"%{escaped}%", escape="\\"))
        from koinon.catalog.summaries import format_expression

        file_format = format_expression(entry)
        if format:
            predicates.append(file_format == format)
        if tag:
            tags = entry.metadata_json["tags"]
            dialect = self._require_session().get_bind().dialect.name
            if dialect == "postgresql":
                safe_tags = case((func.json_typeof(tags) == "array", tags), else_=cast(literal("[]"), JSON))
                values = (
                    func.json_array_elements(safe_tags)
                    .table_valued(column("value", JSON))
                    .alias("catalog_tags")
                )
                tag_value = values.c.value.op("#>>")(cast(literal("{}"), ARRAY(Text)))
                string_tag = func.json_typeof(values.c.value) == "string"
                string_language = func.json_typeof(entry.metadata_json["language"]) == "string"
            else:
                values = func.json_each(tags).table_valued("value", "type").alias("catalog_tags")
                tag_value = values.c.value
                string_tag = and_(values.c.type == "text", func.json_type(tags) == "array")
                string_language = func.json_type(entry.metadata_json, "$.language") == "text"
            custom = (
                select(literal(1))
                .select_from(values)
                .where(string_tag, func.lower(func.trim(tag_value)) == tag)
            )
            predicates.append(
                or_(
                    file_format == tag,
                    and_(
                        string_language,
                        func.lower(func.trim(entry.metadata_json["language"].as_string())) == tag,
                    ),
                    exists(custom.correlate(entry)),
                )
            )
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
                        assets.id.in_(select(visible.c.id)),
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
        sort_column = func.lower(entry.name) if sort == "name" else getattr(entry, sort)
        ordered = sort_column.desc() if order == "desc" else sort_column.asc()
        folders = case((entry.kind.in_(["workspace", "project", "collection", "corpus"]), 0), else_=1)
        rows = (
            await session.scalars(
                statement.order_by(folders, ordered, func.lower(entry.name), entry.id)
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
        summaries = await self._page_summaries(rows, visible)
        return {
            "summaries": summaries,
            "items": list(rows),
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": (total + page_size - 1) // page_size,
        }

    async def _page_summaries(self, rows, visible):
        from koinon.catalog.summaries import LIBRARY_KINDS, format_expression, summary

        if not rows:
            return {}
        entry = CatalogEntry
        identifiers = [row.id for row in rows]
        tenant_id = rows[0].tenant_id
        child, parent, asset = aliased(entry), aliased(entry), aliased(entry)
        # Source wrappers disappear only when this caller can see an asset beneath them.
        has_assets = exists(
            select(asset.id)
            .where(
                asset.parent_id == child.id,
                asset.id.in_(select(visible.c.id)),
                asset.kind.in_(["document", "dataset"]),
            )
            .correlate(child)
        )
        direct = select(child.parent_id.label("parent_id"), child.kind).where(
            child.tenant_id == tenant_id,
            child.id.in_(select(visible.c.id)),
            child.kind.in_(sorted(LIBRARY_KINDS | {"table"})),
            child.parent_id.in_(identifiers),
            or_(child.kind != "source", ~has_assets),
        )
        projected = (
            select(parent.parent_id.label("parent_id"), child.kind)
            .join(
                parent,
                and_(parent.id == child.parent_id, parent.tenant_id == tenant_id, parent.kind == "source"),
            )
            .where(
                child.tenant_id == tenant_id,
                child.id.in_(select(visible.c.id)),
                child.kind.in_(["document", "dataset"]),
                parent.parent_id.in_(identifiers),
            )
        )
        children = direct.union_all(projected).subquery("library_children")
        counts_query = select(children.c.parent_id, children.c.kind, func.count()).group_by(
            children.c.parent_id,
            children.c.kind,
        )
        session = self._require_session()
        counts = {}
        for parent_id, kind, count in await session.execute(counts_query):
            group = counts.setdefault(parent_id, {"total": 0})
            group[kind] = count
            group["total"] += count
        source = aliased(entry)
        metadata_query = (
            select(entry.id, format_expression(entry), source.metadata_json)
            .outerjoin(
                source,
                and_(
                    source.id == entry.parent_id,
                    source.tenant_id == tenant_id,
                    source.kind == "source",
                    source.id.in_(select(visible.c.id)),
                ),
            )
            .where(entry.id.in_(identifiers), entry.tenant_id == tenant_id)
        )
        metadata = {
            identifier: (file_format, source_data)
            for identifier, file_format, source_data in await session.execute(metadata_query)
        }
        return {row.id: summary(row, counts.get(row.id, {}), *metadata[row.id]) for row in rows}


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
        members=None,
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
        from koinon.corporate_profiles.expressions import presentation_joins
        from koinon.organization_people.entities import OrganizationPersonRecord

        statement = statement.outerjoin(
            OrganizationPersonRecord,
            and_(
                OrganizationPersonRecord.tenant_id == tenant_id,
                OrganizationPersonRecord.subject == AuditEvent.subject,
            ),
        )
        statement, display_name = presentation_joins(statement, AuditEvent.subject, tenant_id, Profile)
        if members is not None:
            display_name = case(
                (
                    exists(
                        select(members.c.subject).where(
                            members.c.tenant_id == tenant_id,
                            members.c.subject == AuditEvent.subject,
                            members.c.active.is_(True),
                        )
                    ),
                    display_name,
                ),
                else_="",
            )
        if q:
            escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            predicates.append(
                or_(
                    *(
                        column.ilike(f"%{escaped}%", escape="\\")
                        for column in (
                            display_name,
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
