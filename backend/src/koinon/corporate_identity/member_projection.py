# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""One SQL projection for manual and currently effective corporate access."""

from datetime import UTC, datetime
from types import SimpleNamespace

from pyfly.data.relational.sqlalchemy import UtcDateTime
from sqlalchemy import and_, func, literal, or_, select, union_all

from koinon.catalog.entities import Membership
from koinon.corporate_identity.entities import CorporateGrant, CorporateMapping, CorporateProvider
from koinon.profiles.entities import Profile


def membership_rows(issuer: str):
    manual = select(
        Membership.id,
        Membership.subject,
        Membership.tenant_id,
        Membership.workspace_id,
        Membership.role,
        Membership.active,
        Membership.created_at,
        literal(False).label("managed"),
        literal("manual").label("origin"),
        literal(None).label("source_id"),
        literal(None).label("source_name"),
        literal(None, type_=UtcDateTime()).label("expires_at"),
    ).where(Membership.active.is_(True))
    managed = (
        select(
            CorporateGrant.id,
            CorporateGrant.subject,
            CorporateGrant.tenant_id,
            CorporateGrant.workspace_id,
            CorporateGrant.role,
            CorporateGrant.active,
            CorporateGrant.observed_at.label("created_at"),
            literal(True).label("managed"),
            literal("corporate").label("origin"),
            CorporateProvider.id.label("source_id"),
            CorporateProvider.name.label("source_name"),
            CorporateGrant.expires_at,
        )
        .join(CorporateProvider, CorporateGrant.provider_id == CorporateProvider.id)
        .join(CorporateMapping, CorporateGrant.mapping_id == CorporateMapping.id)
        .where(
            CorporateGrant.active.is_(True),
            CorporateGrant.expires_at > datetime.now(UTC),
            CorporateProvider.canonical_issuer == issuer,
            CorporateProvider.status == "active",
            CorporateProvider.tenant_id == CorporateGrant.tenant_id,
            CorporateProvider.policy_revision == CorporateGrant.policy_revision,
            CorporateMapping.provider_id == CorporateProvider.id,
            CorporateMapping.tenant_id == CorporateGrant.tenant_id,
            CorporateMapping.enabled.is_(True),
            CorporateMapping.revision == CorporateGrant.mapping_revision,
            CorporateMapping.role == CorporateGrant.role,
            or_(
                and_(CorporateMapping.workspace_id.is_(None), CorporateGrant.workspace_id.is_(None)),
                CorporateMapping.workspace_id == CorporateGrant.workspace_id,
            ),
        )
    )
    return union_all(manual, managed).subquery("effective_memberships")


async def member_page(
    session, issuer, tenant_id, *, q="", role=None, workspace_id=None, scope="all", page=1, page_size=25
):
    members = membership_rows(issuer)
    predicates = [members.c.tenant_id == tenant_id]
    if workspace_id is not None:
        predicates.append(members.c.workspace_id == workspace_id)
    elif scope == "tenant":
        predicates.append(members.c.workspace_id.is_(None))
    if role:
        predicates.append(members.c.role == role)
    if q:
        escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        predicates.append(
            or_(
                Profile.display_name.ilike("%" + escaped + "%", escape="\\"),
                members.c.subject.ilike("%" + escaped + "%", escape="\\"),
            )
        )
    statement = select(members).outerjoin(Profile, Profile.subject == members.c.subject).where(*predicates)
    total = int((await session.scalar(select(func.count()).select_from(statement.subquery()))) or 0)
    rows = (
        await session.execute(
            statement.order_by(
                func.lower(func.coalesce(Profile.display_name, "")), members.c.subject, members.c.id
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).mappings()
    return {
        "items": [SimpleNamespace(**dict(row)) for row in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size,
    }
