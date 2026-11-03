# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from collections.abc import Sequence

from pyfly.container import repository
from pyfly.data.relational.sqlalchemy import Repository
from sqlalchemy import select

from koinon.knowledge.entities import DomainBinding


@repository(name="knowledge.bindings")
class DomainBindingRepository(Repository[DomainBinding, str]):
    """Explicit durable identities, never inferred from editable catalog metadata."""

    async def for_catalog_ids(
        self, tenant_id: str, domain: str, catalog_ids: Sequence[str]
    ) -> list[DomainBinding]:
        identifiers = tuple(dict.fromkeys(catalog_ids))
        rows = []
        for start in range(0, len(identifiers), 200):
            rows.extend(
                (
                    await self._require_session().scalars(
                        select(DomainBinding).where(
                            DomainBinding.tenant_id == tenant_id,
                            DomainBinding.domain == domain,
                            DomainBinding.catalog_id.in_(identifiers[start : start + 200]),
                        )
                    )
                ).all()
            )
        return rows
