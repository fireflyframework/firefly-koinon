# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime

from pyfly.container import repository
from pyfly.data.relational.sqlalchemy import Repository
from sqlalchemy import and_, func, or_, select

from koinon.corporate_identity.entities import (
    CorporateGrant,
    CorporateMapping,
    CorporateProvider,
    CorporateValidation,
)


@repository(name="identity.provider_repository")
class CorporateProviderRepository(Repository[CorporateProvider, str]):
    async def page(self, tenant_id, *, q="", kind=None, status=None, page=1, page_size=25):
        predicates = [CorporateProvider.tenant_id == tenant_id]
        if kind:
            predicates.append(CorporateProvider.kind == kind)
        if status:
            predicates.append(CorporateProvider.status == status)
        if q:
            escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            predicates.append(CorporateProvider.name.ilike("%" + escaped + "%", escape="\\"))
        statement = select(CorporateProvider).where(*predicates)
        session = self._require_session()
        total = int((await session.scalar(select(func.count()).select_from(statement.subquery()))) or 0)
        rows = list(
            await session.scalars(
                statement.order_by(func.lower(CorporateProvider.name), CorporateProvider.id)
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        return {
            "items": rows,
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": (total + page_size - 1) // page_size,
        }


@repository(name="identity.mapping_repository")
class CorporateMappingRepository(Repository[CorporateMapping, str]):
    async def page(
        self, tenant_id, provider_id, *, q="", status="all", workspace_id=None, page=1, page_size=25
    ):
        predicates = [CorporateMapping.tenant_id == tenant_id, CorporateMapping.provider_id == provider_id]
        if status != "all":
            predicates.append(CorporateMapping.enabled.is_(status == "enabled"))
        if workspace_id is not None:
            predicates.append(CorporateMapping.workspace_id == workspace_id)
        if q:
            escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            predicates.append(CorporateMapping.group_name.ilike("%" + escaped + "%", escape="\\"))
        statement = select(CorporateMapping).where(*predicates)
        session = self._require_session()
        total = int((await session.scalar(select(func.count()).select_from(statement.subquery()))) or 0)
        rows = list(
            await session.scalars(
                statement.order_by(func.lower(CorporateMapping.group_name), CorporateMapping.id)
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        return {
            "items": rows,
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": (total + page_size - 1) // page_size,
        }


@repository(name="identity.grant_repository")
class CorporateGrantRepository(Repository[CorporateGrant, str]):
    async def current(self, subject, issuer):
        now = datetime.now(UTC)
        statement = (
            select(CorporateGrant, CorporateProvider.name)
            .join(CorporateProvider, CorporateGrant.provider_id == CorporateProvider.id)
            .join(CorporateMapping, CorporateGrant.mapping_id == CorporateMapping.id)
            .where(
                CorporateGrant.subject == subject,
                CorporateGrant.active.is_(True),
                CorporateGrant.expires_at > now,
                CorporateProvider.status == "active",
                CorporateProvider.canonical_issuer == issuer,
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
        return list((await self._require_session().execute(statement)).all())


@repository(name="identity.validation_repository")
class CorporateValidationRepository(Repository[CorporateValidation, str]):
    pass
