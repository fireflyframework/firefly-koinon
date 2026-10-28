# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from sqlalchemy import select

from koinon.knowledge.lineage.entities import (
    SnapshotLineageRow,
    TransformStepRow,
)


class StructuredLineageRepository:
    """Borrows the caller's native session; never commits or opens another engine."""

    @staticmethod
    async def insert(session, row):
        session.add(row)
        await session.flush()
        return row

    @staticmethod
    async def get(session, entity, identifier):
        return (await session.execute(select(entity).where(entity.id == identifier))).scalar_one_or_none()

    @staticmethod
    async def scope_row(session, entity, identifier, scope):
        key = entity.snapshot_id if entity is SnapshotLineageRow else entity.id
        return (
            await session.execute(
                select(entity).where(
                    key == identifier,
                    entity.tenant_id == scope[0],
                    entity.workspace_id == scope[1],
                    entity.dataset_id == scope[2],
                )
            )
        ).scalar_one_or_none()

    @staticmethod
    async def steps(session, run_id, scope):
        return (
            (
                await session.execute(
                    select(TransformStepRow)
                    .where(
                        TransformStepRow.run_id == run_id,
                        TransformStepRow.tenant_id == scope[0],
                        TransformStepRow.workspace_id == scope[1],
                        TransformStepRow.dataset_id == scope[2],
                    )
                    .order_by(TransformStepRow.ordinal)
                )
            )
            .scalars()
            .all()
        )
