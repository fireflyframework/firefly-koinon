# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Reuse database observations only within one immutable primary policy snapshot."""

from contextlib import asynccontextmanager
from typing import Any

from pyfly.data.transaction import Isolation, current_unit_of_work

from koinon.security.authority import PRIMARY_POLICY_UNIT, primary_authority


def _snapshot(unit):
    return (
        unit is not None
        and not unit.completed
        and unit.read_only
        and unit.read_from_primary
        and unit.definition.isolation == Isolation.SERIALIZABLE
        and unit.definition.name in {PRIMARY_POLICY_UNIT, "koinon.security.primary-authority"}
    )


@asynccontextmanager
async def policy_read():
    unit = current_unit_of_work("primary")
    if _snapshot(unit) or (
        unit is not None and not unit.completed and unit.read_from_primary and not unit.read_only
    ):
        # A rejected scope can be an ordinary directory filter, not a failed database participant.
        yield
    else:
        async with primary_authority():
            yield


def snapshot_values(owner: object, group: str) -> dict[Any, Any] | None:
    unit = current_unit_of_work("primary")
    if unit is None or not _snapshot(unit):
        return None
    # Fresh egress checks have different units; writes never reuse these observations.
    observations = unit.attributes.setdefault("koinon.policy-observations", {})
    return observations.setdefault((id(owner), group), {})
