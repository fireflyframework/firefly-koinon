# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import pytest


async def test_lazy_taxonomy_seed_and_reads_use_the_verified_scope(repositories):
    from flycanon.config import CanonSettings
    from flycanon.core.services.audit import AuditService
    from flycanon.core.services.taxonomy import TaxonomyService
    from flycanon.core.services.taxonomy.handlers import GetTaxonomyHandler, GetTaxonomyQuery
    from flycanon.interfaces.enums import Domain

    service = TaxonomyService(
        repositories["taxonomy"],
        AuditService(
            repository=repositories["audit"],
            event_publisher=None,
            settings=CanonSettings(),
        ),
        CanonSettings(),
    )
    handler = GetTaxonomyHandler(service)
    for tenant in ("north", "south"):
        result = await handler.do_handle(GetTaxonomyQuery(tenant_id=tenant, workspace_id="workspace"))
        assert len(result.nodes) == len(Domain)
        assert await service.ensure_default_seed(tenant_id=tenant, workspace_id="workspace") == 0
    rows = await repositories["taxonomy"].list_all()
    assert {row.tenant_id for row in rows} == {"north", "south"}


async def test_taxonomy_cannot_attach_to_a_foreign_parent(repositories):
    from flycanon.config import CanonSettings
    from flycanon.core.services.audit import AuditService
    from flycanon.core.services.taxonomy import TaxonomyService
    from flycanon.core.services.taxonomy.taxonomy_service import TaxonomyNotFound
    from flycanon.interfaces.dtos.taxonomy import CreateTaxonomyNodeRequest
    from flycanon.interfaces.enums import Domain

    service = TaxonomyService(
        repositories["taxonomy"],
        AuditService(
            repository=repositories["audit"],
            event_publisher=None,
            settings=CanonSettings(),
        ),
        CanonSettings(),
    )
    await service.ensure_default_seed(tenant_id="north", workspace_id="workspace")
    parent = (await service.list_all(tenant_id="north", workspace_id="workspace"))[0]
    with pytest.raises(TaxonomyNotFound):
        await service.add_node(
            CreateTaxonomyNodeRequest(parent_id=parent.id, slug="child", label="Child", domain=Domain.legal),
            tenant_id="south",
            workspace_id="workspace",
        )
