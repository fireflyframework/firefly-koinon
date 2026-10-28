# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from sqlalchemy import func, select


def filters(entity, scope):
    return (
        entity.tenant_id == scope["tenant_id"],
        entity.workspace_id == scope["workspace_id"],
        entity.dataset_id == scope["dataset_id"],
        entity.snapshot_id == scope["snapshot_id"],
    )


class CoordinateRepository:
    """Only borrowed native sessions; all point and page reads execute scoped SQL."""

    @staticmethod
    async def one(session, entity, scope):
        return (await session.execute(select(entity).where(*filters(entity, scope)))).scalar_one_or_none()

    @staticmethod
    async def page(session, entity, scope, order, page, page_size):
        total = (
            await session.execute(select(func.count()).select_from(entity).where(*filters(entity, scope)))
        ).scalar_one()
        rows = (
            (
                await session.execute(
                    select(entity)
                    .where(*filters(entity, scope))
                    .order_by(order)
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            )
            .scalars()
            .all()
        )
        return rows, total
