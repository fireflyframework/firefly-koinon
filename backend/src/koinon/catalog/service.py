# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Catalog operations enforce persisted membership and complete ancestry."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, date, datetime, time, timedelta
from urllib.parse import urlsplit
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pyfly.container import Provider, service
from pyfly.data.relational.sqlalchemy import LockMode, transactional
from pyfly.kernel import ConflictException, InvalidRequestException

from koinon.catalog.entities import INTERNAL_METADATA_KEYS, AuditEvent, CatalogEntry, Membership
from koinon.catalog.errors import AccessDenied, InvalidHierarchy
from koinon.catalog.ports import ManagedMembershipReader, MembershipRecord
from koinon.catalog.repositories import (
    AuditRepository,
    CatalogRepository,
    MembershipRepository,
    TenantRepository,
)
from koinon.tokens.authorization import TokenRestriction
from koinon.tokens.entities import PersonalToken

_READ = frozenset(
    {
        "catalog:read",
        "knowledge:search",
        "chat:use",
        "exports:read",
        "exports:write",
        "shares:read",
        "shares:write",
        "evidence:read",
    }
)
_OPERATOR = _READ | {
    "query:execute",
    "catalog:write",
    "ingest:write",
    "providers:write",
    "agents:write",
    "jobs:manage",
    "sources:configure",
    "indexes:manage",
    "audit:read",
}
ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    "viewer": _READ,
    "analyst": _READ | {"query:execute"},
    "editor": _READ | {"query:execute", "catalog:write", "ingest:write"},
    "operator": _OPERATOR,
    "admin": _OPERATOR | {"members:write", "settings:write", "identity:manage"},
}

PARENTS: dict[str, frozenset[str | None]] = {
    "workspace": frozenset({None}),
    "project": frozenset({"workspace"}),
    "collection": frozenset({"project"}),
    "corpus": frozenset({"project"}),
    "source": frozenset({"collection", "corpus"}),
    "document": frozenset({"source"}),
    "dataset": frozenset({"source"}),
    "knowledge_item": frozenset({"collection", "corpus"}),
    "chunk": frozenset({"document"}),
    "table": frozenset({"dataset"}),
    "index_version": frozenset({"collection", "corpus", "source", "dataset"}),
    "query_session": frozenset({"project"}),
}


@service
class CatalogService:
    def __init__(
        self,
        tenant_repository: TenantRepository,
        membership_repository: MembershipRepository,
        catalog_repository: CatalogRepository,
        audit_repository: AuditRepository | None = None,
        restriction: TokenRestriction | None = None,
        managed_memberships: ManagedMembershipReader | None = None,
        managed_provider: Provider[ManagedMembershipReader | None] | None = None,
    ):
        self.tenant_repository = tenant_repository
        self.membership_repository = membership_repository
        self.catalog_repository = catalog_repository
        self.audit_repository = audit_repository
        self.restriction = restriction
        self._managed_memberships = managed_memberships
        self._managed_provider = managed_provider

    @staticmethod
    def require_knowledge_review(kind):
        if kind == "knowledge_item":
            raise InvalidHierarchy(
                "Use an explicitly confirmed knowledge intent for repository changes",
                code="KNOWLEDGE_REVIEW_REQUIRED",
            )

    @property
    def managed_memberships(self) -> ManagedMembershipReader | None:
        if self._managed_provider is not None:
            return self._managed_provider.get()
        return self._managed_memberships

    def effective_membership_rows(self):
        if self.managed_memberships is not None:
            return self.managed_memberships.effective_membership_rows()
        from sqlalchemy import select

        return select(Membership).where(Membership.active.is_(True)).subquery("effective_memberships")

    async def memberships(self, subject: str) -> list[MembershipRecord]:
        rows = await self.membership_repository.find_all(subject=subject, active=True)
        records: list[MembershipRecord] = list(rows)
        if self.managed_memberships is not None:
            records.extend(await self.managed_memberships.load_managed_memberships(subject))
        grant = await self.restriction.grant(subject) if self.restriction else None
        return [row for row in records if grant is None or row.tenant_id == grant.tenant_id]

    async def permissions(
        self, subject: str, tenant_id: str, workspace_id: str | None = None
    ) -> frozenset[str]:
        memberships = await self.memberships(subject)
        grant = await self.restriction.grant(subject) if self.restriction else None
        return self._resolved_permissions(memberships, tenant_id, workspace_id, grant)

    @staticmethod
    def _resolved_permissions(
        memberships: Sequence[MembershipRecord],
        tenant_id: str,
        workspace_id: str | None = None,
        grant: PersonalToken | None = None,
    ) -> frozenset[str]:
        granted: set[str] = set()
        for member in memberships:
            if member.tenant_id == tenant_id and (
                member.workspace_id is None or member.workspace_id == workspace_id
            ):
                granted.update(ROLE_PERMISSIONS.get(member.role, frozenset()))
        if grant is not None:
            if grant.tenant_id != tenant_id or (
                workspace_id is not None
                and grant.workspace_ids is not None
                and workspace_id not in grant.workspace_ids
            ):
                return frozenset()
            granted.intersection_update(grant.scopes)
            if workspace_id is None and (grant.workspace_ids is not None or grant.asset_ids is not None):
                granted.intersection_update({"catalog:read"})
        return frozenset(granted)

    async def authorize(
        self, subject: str, tenant_id: str, permission: str, workspace_id: str | None = None
    ) -> None:
        await self._validate_workspace(tenant_id, workspace_id)
        if permission not in await self.permissions(subject, tenant_id, workspace_id):
            raise AccessDenied("Resource is not accessible in the selected context", code="ACCESS_DENIED")

    async def _scoped_entry(self, tenant_id: str, entry_id: str, *, lock=False) -> CatalogEntry:
        rows = await self.catalog_repository.find_all(id=entry_id, tenant_id=tenant_id)
        if not rows:
            raise AccessDenied("Resource is not accessible in the selected context", code="ACCESS_DENIED")
        return (
            await self.catalog_repository.find_by_id(entry_id, lock=LockMode.PESSIMISTIC_WRITE)
            if lock
            else rows[0]
        )

    async def get(self, subject: str, tenant_id: str, entry_id: str) -> CatalogEntry:
        entry = await self._scoped_entry(tenant_id, entry_id)
        await self.authorize(subject, tenant_id, "catalog:read", entry.workspace_id)
        if self.restriction:
            await self.restriction.resource(subject, entry)
        if entry.kind == "knowledge_item":
            bounds = await self.curated_read_bounds(subject, tenant_id)
            if not await self.catalog_repository.curated_visible(tenant_id, entry.id, **bounds):
                raise AccessDenied("Knowledge source roots are unavailable", code="ACCESS_DENIED")
        return entry

    async def curated_read_bounds(self, subject, tenant_id):
        grants = [
            member
            for member in await self.memberships(subject)
            if member.tenant_id == tenant_id and "catalog:read" in ROLE_PERMISSIONS.get(member.role, ())
        ]
        allowed = (
            None
            if any(member.workspace_id is None for member in grants)
            else [member.workspace_id for member in grants if member.workspace_id is not None]
        )
        grant = await self.restriction.grant(subject) if self.restriction else None
        if grant is not None and grant.workspace_ids is not None:
            allowed = (
                grant.workspace_ids if allowed is None else sorted(set(allowed) & set(grant.workspace_ids))
            )
        return {
            "allowed_workspaces": allowed,
            "allowed_assets": grant.asset_ids if grant else None,
            "allowed_resources": grant.resource_ids if grant else None,
        }

    async def list(
        self,
        subject: str,
        tenant_id: str,
        *,
        parent_id: str | None = None,
        kind: str | None = None,
        workspace_id: str | None = None,
        include_archived: bool = False,
    ) -> list[CatalogEntry]:
        if parent_id is not None:
            parent = await self.get(subject, tenant_id, parent_id)
            if workspace_id is not None and workspace_id != parent.workspace_id:
                raise InvalidHierarchy("Parent and selected workspace disagree", code="INVALID_WORKSPACE")
            workspace_id = parent.workspace_id
        grants = [
            m
            for m in await self.memberships(subject)
            if m.tenant_id == tenant_id and "catalog:read" in ROLE_PERMISSIONS.get(m.role, frozenset())
        ]
        if not grants:
            raise AccessDenied("Resource is not accessible in the selected context", code="ACCESS_DENIED")
        if workspace_id is not None:
            await self.authorize(subject, tenant_id, "catalog:read", workspace_id)
        filters: dict = {"tenant_id": tenant_id}
        if parent_id is not None:
            filters["parent_id"] = parent_id
        if kind is not None:
            filters["kind"] = kind
        if workspace_id is not None:
            filters["workspace_id"] = workspace_id
        rows = await self.catalog_repository.find_all(**filters)
        tenant_wide = any(m.workspace_id is None for m in grants)
        allowed_workspaces = {m.workspace_id for m in grants}
        visible = [entry for entry in rows if tenant_wide or entry.workspace_id in allowed_workspaces]
        grant = await self.restriction.grant(subject) if self.restriction else None
        if grant is not None and self.restriction is not None:
            if "catalog:read" not in grant.scopes:
                raise AccessDenied("API token lacks catalog access", code="TOKEN_SCOPE_DENIED")
            restricted = []
            for entry in visible:
                try:
                    await self.restriction.resource(subject, entry)
                except AccessDenied:
                    continue
                restricted.append(entry)
            visible = restricted
        if any(entry.kind == "knowledge_item" for entry in visible):
            admitted = await self.catalog_repository.curated_ids(
                tenant_id, **await self.curated_read_bounds(subject, tenant_id)
            )
            visible = [entry for entry in visible if entry.kind != "knowledge_item" or entry.id in admitted]
        if include_archived:
            return visible
        ancestry = {entry.id: entry for entry in await self.catalog_repository.find_all(tenant_id=tenant_id)}

        def active(entry):
            seen = set()
            while entry is not None:
                if entry.id in seen or len(seen) >= 16 or entry.status == "archived":
                    return False
                seen.add(entry.id)
                if entry.parent_id is not None and entry.parent_id not in ancestry:
                    return False
                entry = ancestry.get(entry.parent_id)
            return True

        return [entry for entry in visible if active(entry)]

    @transactional
    async def create(
        self,
        subject: str,
        tenant_id: str,
        *,
        kind: str,
        name: str,
        parent_id: str | None = None,
        metadata: dict | None = None,
        description: str = "",
    ) -> CatalogEntry:
        self.require_knowledge_review(kind)
        if kind not in PARENTS or not name.strip() or len(name.strip()) > 255:
            raise InvalidHierarchy(
                "Choose a valid kind and a name from 1 to 255 characters", code="INVALID_RESOURCE"
            )
        parent = await self._scoped_entry(tenant_id, parent_id) if parent_id is not None else None
        if self.restriction and parent:
            await self.restriction.resource(subject, parent, write=True)
        workspace_id = parent.workspace_id if parent else None
        await self.authorize(subject, tenant_id, "catalog:write", workspace_id)
        if (parent.kind if parent else None) not in PARENTS[kind]:
            raise InvalidHierarchy("This resource requires a compatible parent", code="INVALID_PARENT")
        if metadata and INTERNAL_METADATA_KEYS.intersection(metadata):
            raise InvalidHierarchy("Reserved catalog metadata", code="RESERVED_METADATA")
        identifier = str(uuid4())
        entry = CatalogEntry(
            id=identifier,
            tenant_id=tenant_id,
            kind=kind,
            name=name.strip(),
            parent_id=parent_id,
            workspace_id=identifier if kind == "workspace" else workspace_id,
            project_id=identifier if kind == "project" else (parent.project_id if parent else None),
            description=description,
            metadata_json=metadata or {},
            created_by=subject,
            updated_by=subject,
        )
        saved = await self.catalog_repository.save(entry)
        await self._audit(subject, tenant_id, "catalog.created", entry.id, {"kind": kind})
        return saved

    async def context(self, subject: str) -> dict:
        memberships = await self.memberships(subject)
        grant = await self.restriction.grant(subject) if self.restriction else None
        tenants, workspaces = [], []
        for tenant_id in sorted({member.tenant_id for member in memberships}):
            tenant = await self.tenant_repository.find_by_id(tenant_id)
            if tenant is None:
                continue
            grants = [member for member in memberships if member.tenant_id == tenant_id]
            tenants.append(
                {
                    "id": tenant.id,
                    "name": tenant.name,
                    "roles": sorted({member.role for member in grants}),
                    "permissions": sorted(self._resolved_permissions(memberships, tenant_id, grant=grant)),
                }
            )
            workspaces.extend(await self.list(subject, tenant_id, kind="workspace"))
        workspace_permissions = {
            entry.id: sorted(self._resolved_permissions(memberships, entry.tenant_id, entry.id, grant))
            for entry in workspaces
        }
        return {
            "subject": subject,
            "tenants": tenants,
            "memberships": memberships,
            "workspaces": workspaces,
            "workspace_permissions": workspace_permissions,
        }

    async def _audit(self, subject: str, tenant_id: str, action: str, resource_id: str, details=None) -> None:
        if self.audit_repository is None:
            raise RuntimeError("Catalog mutations require the native audit repository")
        await self.audit_repository.save(
            AuditEvent(
                id=str(uuid4()),
                tenant_id=tenant_id,
                subject=subject,
                action=action,
                resource_id=resource_id,
                details=details or {},
            )
        )

    @transactional
    async def update(self, subject: str, tenant_id: str, entry_id: str, changes: dict) -> CatalogEntry:
        entry = await self._scoped_entry(tenant_id, entry_id, lock=True)
        await self.authorize(subject, tenant_id, "catalog:write", entry.workspace_id)
        if self.restriction:
            await self.restriction.resource(subject, entry, write=True)
        self.require_knowledge_review(entry.kind)
        if set(changes) - {"name", "description", "status", "metadata"}:
            raise InvalidHierarchy("Resource scope and ancestry are immutable", code="IMMUTABLE_SCOPE")
        if "name" in changes:
            name = changes["name"].strip()
            if not name or len(name) > 255:
                raise InvalidHierarchy("Choose a name from 1 to 255 characters", code="INVALID_RESOURCE")
            entry.name = name
        for field in ("description", "status"):
            if field in changes:
                if field == "status" and entry.status == "archived":
                    entry.metadata_json = {
                        **entry.metadata_json,
                        "_koinon_lifecycle": {"previous_status": changes[field]},
                    }
                else:
                    setattr(entry, field, changes[field])
        if "metadata" in changes:
            if INTERNAL_METADATA_KEYS.intersection(changes["metadata"]):
                raise InvalidHierarchy("Reserved catalog metadata", code="RESERVED_METADATA")
            internal = {
                key: value for key, value in entry.metadata_json.items() if key in INTERNAL_METADATA_KEYS
            }
            entry.metadata_json = {**changes["metadata"], **internal}
        entry.updated_at = datetime.now(UTC)
        entry.updated_by = subject
        saved = await self.catalog_repository.save(entry)
        await self._audit(subject, tenant_id, "catalog.updated", entry.id, {"fields": sorted(changes)})
        return saved

    @transactional
    async def delete(self, subject: str, tenant_id: str, entry_id: str) -> None:
        entry = await self._scoped_entry(tenant_id, entry_id, lock=True)
        await self.authorize(subject, tenant_id, "catalog:write", entry.workspace_id)
        if self.restriction:
            await self.restriction.resource(subject, entry, write=True)
        self.require_knowledge_review(entry.kind)
        if entry.metadata_json.get("_koinon_intake"):
            raise ConflictException(
                "Retained intake receipts cannot be deleted", code="INTAKE_RECEIPT_IMMUTABLE"
            )
        children = await self.catalog_repository.find_all(tenant_id=tenant_id, parent_id=entry_id)
        grants = await self.membership_repository.find_all(tenant_id=tenant_id, workspace_id=entry_id)
        if children or grants:
            raise ConflictException(
                "Remove dependent resources and memberships first", code="RESOURCE_NOT_EMPTY"
            )
        await self.catalog_repository.delete_by_id(entry.id)
        await self._audit(subject, tenant_id, "catalog.deleted", entry.id, {"kind": entry.kind})

    async def _validate_workspace(self, tenant_id: str, workspace_id: str | None) -> None:
        if workspace_id is not None:
            workspace = await self._scoped_entry(tenant_id, workspace_id)
            if workspace.kind != "workspace":
                raise InvalidHierarchy("Select a workspace in this tenant", code="INVALID_WORKSPACE")

    async def list_members(
        self, subject: str, tenant_id: str, workspace_id: str | None = None
    ) -> list[Membership]:
        await self._validate_workspace(tenant_id, workspace_id)
        await self.authorize(subject, tenant_id, "members:write", workspace_id)
        filters = {"tenant_id": tenant_id, "active": True}
        if workspace_id is not None:
            filters["workspace_id"] = workspace_id
        return await self.membership_repository.find_all(**filters)

    @transactional(read_only=True)
    async def member_page(
        self,
        subject: str,
        tenant_id: str,
        *,
        q: str = "",
        role: str | None = None,
        workspace_id: str | None = None,
        scope: str = "all",
        page: int = 1,
        page_size: int = 25,
    ) -> dict:
        if (
            len(q) > 80
            or page < 1
            or page_size < 1
            or page_size > 100
            or scope not in {"all", "tenant", "workspace"}
            or (role is not None and role not in ROLE_PERMISSIONS)
            or (scope == "workspace" and not workspace_id)
            or (scope == "tenant" and workspace_id is not None)
        ):
            raise InvalidRequestException(
                "Choose supported membership filters", code="INVALID_MEMBERSHIP_FILTER"
            )
        await self.authorize(subject, tenant_id, "members:write", workspace_id)
        if self.managed_memberships is not None:
            return await self.managed_memberships.effective_membership_page(
                tenant_id,
                q=q,
                role=role,
                workspace_id=workspace_id,
                scope=scope,
                page=page,
                page_size=page_size,
            )
        return await self.membership_repository.find_page(
            tenant_id, q=q, role=role, workspace_id=workspace_id, scope=scope, page=page, page_size=page_size
        )

    async def _lock_tenant(self, tenant_id: str) -> None:
        tenant = await self.tenant_repository.find_by_id(tenant_id, lock=LockMode.PESSIMISTIC_WRITE)
        if tenant is None:
            raise AccessDenied("Resource is not accessible in the selected context", code="ACCESS_DENIED")

    @transactional
    async def create_member(
        self, actor: str, tenant_id: str, *, subject: str, role: str, workspace_id: str | None = None
    ) -> Membership:
        issuer, separator, principal = subject.partition("|")
        parsed = urlsplit(issuer)
        if (
            not separator
            or not principal
            or not parsed.hostname
            or parsed.scheme not in ("http", "https")
            or len(subject) > 512
            or role not in ROLE_PERMISSIONS
        ):
            raise InvalidHierarchy(
                "Use a canonical issuer|subject and a supported role", code="INVALID_MEMBERSHIP"
            )
        await self._lock_tenant(tenant_id)
        await self._validate_workspace(tenant_id, workspace_id)
        await self.authorize(actor, tenant_id, "members:write", workspace_id)
        existing = await self.membership_repository.find_all(
            subject=subject, tenant_id=tenant_id, workspace_id=workspace_id
        )
        if any(member.active for member in existing):
            raise ConflictException(
                "Identity already has a membership in this scope", code="MEMBERSHIP_EXISTS"
            )
        member = (
            existing[0]
            if existing
            else Membership(
                id=str(uuid4()), subject=subject, tenant_id=tenant_id, workspace_id=workspace_id, role=role
            )
        )
        member.active, member.role = True, role
        saved = await self.membership_repository.save(member)
        await self._audit(
            actor, tenant_id, "membership.created", member.id, {"subject": subject, "role": role}
        )
        return saved

    @transactional
    async def update_member(
        self,
        actor: str,
        tenant_id: str,
        member_id: str,
        *,
        role: str | None = None,
        active: bool | None = None,
    ) -> Membership:
        await self._lock_tenant(tenant_id)
        rows = await self.membership_repository.find_all(id=member_id, tenant_id=tenant_id)
        if not rows:
            raise AccessDenied("Resource is not accessible in the selected context", code="ACCESS_DENIED")
        member = rows[0]
        await self.authorize(actor, tenant_id, "members:write", member.workspace_id)
        if role is not None and role not in ROLE_PERMISSIONS:
            raise InvalidHierarchy("Choose a supported role", code="INVALID_MEMBERSHIP")
        demoting = role not in (None, "admin") or active is False
        if member.active and member.role == "admin" and member.workspace_id is None and demoting:
            admins = await self.membership_repository.find_all(
                tenant_id=tenant_id, workspace_id=None, role="admin", active=True
            )
            if len(admins) <= 1:
                raise ConflictException("Tenant must retain an active administrator", code="LAST_ADMIN")
        if role is not None:
            member.role = role
        if active is not None:
            member.active = active
        saved = await self.membership_repository.save(member)
        await self._audit(
            actor, tenant_id, "membership.updated", member.id, {"role": member.role, "active": member.active}
        )
        return saved

    async def audit(self, subject: str, tenant_id: str) -> list[AuditEvent]:
        await self.authorize(subject, tenant_id, "audit:read")
        if self.audit_repository is None:
            raise RuntimeError("Audit repository is unavailable")
        return await self.audit_repository.find_all(tenant_id=tenant_id)

    @transactional(read_only=True)
    async def audit_page(
        self,
        actor: str,
        tenant_id: str,
        *,
        q: str = "",
        action: str | None = None,
        subject: str | None = None,
        from_date: date | str | None = None,
        through_date: date | str | None = None,
        time_zone: str = "UTC",
        page: int = 1,
        page_size: int = 25,
        sort: str = "created_at",
        order: str = "desc",
    ) -> dict:
        await self.authorize(actor, tenant_id, "audit:read")

        def calendar_day(value):
            if not isinstance(value, str):
                return value
            if len(value) != 10 or value[4] != "-" or value[7] != "-":
                raise ValueError("Use an ISO calendar date")
            return date.fromisoformat(value)

        try:
            from_date, through_date = calendar_day(from_date), calendar_day(through_date)
        except ValueError as exc:
            raise InvalidRequestException(
                "Choose valid audit calendar dates", code="INVALID_AUDIT_FILTER"
            ) from exc
        if (
            len(q) > 80
            or (action is not None and len(action) > 64)
            or (subject is not None and len(subject) > 512)
            or page < 1
            or not 1 <= page_size <= 100
            or sort not in {"created_at", "action"}
            or order not in {"asc", "desc"}
            or len(time_zone) > 64
            or (from_date is not None and not isinstance(from_date, date))
            or (through_date is not None and not isinstance(through_date, date))
            or (from_date and through_date and from_date > through_date)
        ):
            raise InvalidRequestException("Choose supported audit filters", code="INVALID_AUDIT_FILTER")
        try:
            zone = ZoneInfo(time_zone)
            start = datetime.combine(from_date, time.min, zone).astimezone(UTC) if from_date else None
            end = (
                datetime.combine(through_date + timedelta(days=1), time.min, zone).astimezone(UTC)
                if through_date
                else None
            )
        except (ValueError, ZoneInfoNotFoundError, OverflowError) as exc:
            raise InvalidRequestException(
                "Choose a valid audit date window and timezone", code="INVALID_AUDIT_FILTER"
            ) from exc
        if self.audit_repository is None:
            raise RuntimeError("Audit repository is unavailable")
        return await self.audit_repository.find_page(
            tenant_id,
            q=q.strip(),
            action=action,
            subject=subject,
            start=start,
            end=end,
            page=page,
            page_size=page_size,
            sort=sort,
            order=order,
        )

    @transactional
    async def archive(self, subject: str, tenant_id: str, entry_id: str) -> CatalogEntry:
        entry = await self._scoped_entry(tenant_id, entry_id, lock=True)
        await self.authorize(subject, tenant_id, "catalog:write", entry.workspace_id)
        if self.restriction:
            await self.restriction.resource(subject, entry, write=True)
        self.require_knowledge_review(entry.kind)
        if entry.status != "archived":
            entry.metadata_json = {
                **entry.metadata_json,
                "_koinon_lifecycle": {"previous_status": entry.status},
            }
            entry.status, entry.updated_at, entry.updated_by = "archived", datetime.now(UTC), subject
            await self.catalog_repository.save(entry)
            await self._audit(subject, tenant_id, "catalog.archived", entry.id)
        return entry

    @transactional
    async def restore(self, subject: str, tenant_id: str, entry_id: str) -> CatalogEntry:
        entry = await self._scoped_entry(tenant_id, entry_id, lock=True)
        await self.authorize(subject, tenant_id, "catalog:write", entry.workspace_id)
        if self.restriction:
            await self.restriction.resource(subject, entry, write=True)
        self.require_knowledge_review(entry.kind)
        if entry.status != "archived":
            raise ConflictException("This knowledge is not archived", code="RESOURCE_NOT_ARCHIVED")
        metadata = dict(entry.metadata_json)
        previous = metadata.pop("_koinon_lifecycle", {}).get("previous_status", "draft")
        entry.status, entry.metadata_json, entry.updated_at, entry.updated_by = (
            previous,
            metadata,
            datetime.now(UTC),
            subject,
        )
        await self.catalog_repository.save(entry)
        await self._audit(subject, tenant_id, "catalog.restored", entry.id)
        return entry

    async def page(
        self,
        subject: str,
        tenant_id: str,
        *,
        parent_id=None,
        workspace_id=None,
        project_id=None,
        kind=None,
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
    ) -> dict:
        from koinon.catalog.summaries import FORMATS

        if (
            type(page) is not int
            or not 1 <= page <= 1000000
            or type(page_size) is not int
            or not 1 <= page_size <= 100
            or sort not in {"name", "kind", "created_at", "updated_at"}
            or order not in {"asc", "desc"}
            or view not in {"raw", "library"}
            or len(q) > 255
            or (kind is not None and kind not in PARENTS)
            or (
                status is not None
                and status not in {"ready", "draft", "pending", "disabled", "archived", "error"}
            )
            or (format is not None and format.strip().lower() not in FORMATS)
            or (tag is not None and not 1 <= len(tag.strip()) <= 64)
        ):
            raise InvalidHierarchy("Choose valid filters and a page size from 1 to 100", code="INVALID_PAGE")
        parent = await self.get(subject, tenant_id, parent_id) if parent_id else None
        if parent:
            if workspace_id is not None and workspace_id != parent.workspace_id:
                raise InvalidHierarchy("Parent and selected workspace disagree", code="INVALID_WORKSPACE")
            workspace_id = parent.workspace_id
        if project_id:
            project = await self.get(subject, tenant_id, project_id)
            if project.kind != "project":
                raise InvalidHierarchy("Choose a project in this organization", code="INVALID_PROJECT")
            if workspace_id is not None and project.workspace_id != workspace_id:
                raise InvalidHierarchy("Project and selected workspace disagree", code="INVALID_WORKSPACE")
            if parent is not None and parent.project_id != project.id:
                raise InvalidHierarchy("Parent and selected project disagree", code="INVALID_PROJECT")
            workspace_id = project.workspace_id
        grants = [
            member
            for member in await self.memberships(subject)
            if member.tenant_id == tenant_id and "catalog:read" in ROLE_PERMISSIONS.get(member.role, ())
        ]
        if not grants:
            raise AccessDenied("Resource is not accessible in the selected context", code="ACCESS_DENIED")
        if workspace_id:
            await self.authorize(subject, tenant_id, "catalog:read", workspace_id)
        allowed = (
            None
            if any(member.workspace_id is None for member in grants)
            else [member.workspace_id for member in grants]
        )
        grant = await self.restriction.grant(subject) if self.restriction else None
        if grant is not None and self.restriction is not None:
            if "catalog:read" not in grant.scopes:
                raise AccessDenied("API token lacks catalog access", code="TOKEN_SCOPE_DENIED")
            if grant.workspace_ids is not None:
                allowed = (
                    grant.workspace_ids
                    if allowed is None
                    else sorted({value for value in allowed if value is not None} & set(grant.workspace_ids))
                )
        return await self.catalog_repository.find_page(
            tenant_id,
            allowed_workspaces=allowed,
            parent=parent,
            allowed_resources=grant.resource_ids if grant else None,
            allowed_assets=grant.asset_ids if grant else None,
            kind=kind,
            workspace_id=workspace_id,
            project_id=project_id,
            include_archived=include_archived,
            view=view,
            q=q.strip(),
            status=status,
            format=format.strip().lower() if format else None,
            tag=tag.strip().lower() if tag else None,
            page=page,
            page_size=page_size,
            sort=sort,
            order=order,
        )
