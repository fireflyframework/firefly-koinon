# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Primary policy snapshots using the native transaction manager and propagation."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from pyfly.data.transaction import Isolation, Propagation, TransactionTemplate, current_unit_of_work
from pyfly.data.transaction.unit_of_work import UnitOfWork

PRIMARY_POLICY_UNIT = "koinon.security.primary-policy"
"""Fixed native snapshot name: every read authority participant must remain in this unit."""

_AUTHORITY_UNIT = "koinon.security.primary-authority"


@asynccontextmanager
async def primary_authority(
    *, read_only: bool = True, fresh: bool = False
) -> AsyncIterator[UnitOfWork | None]:
    """Share current primary writes or a policy snapshot; otherwise read current primary state.

    Primary writes retain their uncommitted grants and native lock order. A fresh output check starts a
    new read snapshot inside ordinary authority reads. An explicitly fixed policy snapshot owns all its
    read participants, including output checks, so their observations cannot be split across units.
    """
    existing = current_unit_of_work("primary")
    share = (
        existing is not None
        and not existing.completed
        and existing.read_from_primary
        and (
            not existing.read_only
            or read_only
            and (
                existing.definition.name == PRIMARY_POLICY_UNIT
                or not fresh
                and existing.definition.name == _AUTHORITY_UNIT
            )
        )
    )
    async with TransactionTemplate(
        "primary",
        name=_AUTHORITY_UNIT,
        propagation=Propagation.REQUIRED if share else Propagation.REQUIRES_NEW,
        isolation=Isolation.SERIALIZABLE if read_only else Isolation.DEFAULT,
        read_only=read_only,
        read_from_primary=True,
    ).transaction() as unit:
        yield unit
