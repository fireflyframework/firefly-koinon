# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Bounded SQL pages inside the caller's native primary read transaction."""

from pyfly.data.transaction import current_unit_of_work
from pyfly.kernel import InvalidRequestException
from sqlalchemy import func, or_, select


async def sql_page(
    model, predicates, *, page=1, page_size=25, q="", search=(), sort="created_at", order="desc", sorts=()
):
    if (
        not isinstance(page, int)
        or page < 1
        or not 1 <= page_size <= 100
        or len(q) > 255
        or order not in {"asc", "desc"}
        or sort not in sorts
    ):
        raise InvalidRequestException(
            "Choose valid filters and a page size from 1 to 100", code="INVALID_PAGE"
        )
    unit = current_unit_of_work("primary")
    if unit is None:
        raise RuntimeError("Paged reads require the native primary read transaction")
    statement = select(model).where(*predicates)
    if q.strip():
        value = q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        statement = statement.where(
            or_(*(getattr(model, field).ilike("%" + value + "%", escape="\\") for field in search))
        )
    total = int((await unit.resource.scalar(select(func.count()).select_from(statement.subquery()))) or 0)
    column = getattr(model, sort)
    ordered = column.asc() if order == "asc" else column.desc()
    items = list(
        (
            await unit.resource.scalars(
                statement.order_by(ordered, model.id).offset((page - 1) * page_size).limit(page_size)
            )
        ).all()
    )
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size,
    }
