# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from types import SimpleNamespace

import pytest
from platform_fixture import authority as authority
from pyfly.data.transaction import Propagation, TransactionTemplate, current_unit_of_work
from pyfly.kernel import ServiceUnavailableException

from koinon.catalog.errors import AccessDenied
from koinon.catalog.repositories import MembershipRepository
from koinon.platform.mappers import component
from koinon.platform.service import PlatformService
from koinon.security.authority import PRIMARY_POLICY_UNIT


async def test_health_metadata_and_policy_share_native_fixed_snapshot(authority):
    _, access = authority

    class Diagnostics:
        async def observe(self, subject, tenant):
            unit = current_unit_of_work("primary")
            assert unit.read_from_primary and unit.read_only
            assert unit.definition.name == PRIMARY_POLICY_UNIT
            return [component("workers", reason="WORKER_LIVENESS_UNKNOWN")]

    service = PlatformService(access, Diagnostics(), SimpleNamespace())
    result = await service.health("issuer|admin", "north")
    assert result.tenant_id == "north" and result.summary.unknown == 1


async def test_committed_revocation_during_read_prevents_observation_release(authority):
    context, access = authority
    members = context.get_bean(MembershipRepository)

    class Diagnostics:
        async def observe(self, subject, tenant):
            async with TransactionTemplate("primary", propagation=Propagation.REQUIRES_NEW).transaction():
                member = await members.find_by_id("admin")
                member.active = False
                await members.save(member)
            return [component("workers", reason="WORKER_LIVENESS_UNKNOWN")]

    service = PlatformService(access, Diagnostics(), SimpleNamespace())
    with pytest.raises(AccessDenied):
        await service.health("issuer|admin", "north")


async def test_diagnostic_failures_are_sanitized_instead_of_leaking_driver_details(authority):
    _, access = authority

    class Diagnostics:
        async def observe(self, subject, tenant):
            raise ValueError("postgresql://credential@private.invalid/private-path")

    service = PlatformService(access, Diagnostics(), SimpleNamespace())
    with pytest.raises(ServiceUnavailableException) as captured:
        await service.health("issuer|admin", "north")
    assert "credential" not in str(captured.value)
    assert "private.invalid" not in str(captured.value)
