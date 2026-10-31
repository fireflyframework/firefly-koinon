# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime, timedelta

import pytest


@pytest.fixture
async def reviewed(tmp_path):
    from pyfly.container.scanner import scan_package
    from pyfly.context import ApplicationContext
    from pyfly.core import Config

    from koinon.authorized_applications.repositories import AuthorizedApplicationRepository
    from koinon.catalog.entities import Membership, Tenant
    from koinon.catalog.repositories import MembershipRepository, TenantRepository
    from koinon.catalog.service import CatalogService
    from koinon.knowledge.curated.intents import KnowledgeIntents
    from koinon.knowledge.external_reviews.service import ExternalKnowledgeReviews
    from koinon.knowledge.repositories import DomainBindingRepository
    from koinon.tokens.authorization import TokenRestriction
    from koinon.tokens.entities import PersonalToken
    from koinon.tokens.repositories import PersonalTokenRepository

    context = ApplicationContext(
        Config(
            {
                "pyfly": {
                    "banner": {"mode": "off"},
                    "data": {
                        "relational": {
                            "enabled": True,
                            "ddl-auto": "create",
                            "url": f"sqlite+aiosqlite:///{tmp_path / 'review.db'}",
                        }
                    },
                }
            }
        )
    )
    for package in ("koinon.catalog", "koinon.knowledge.curated", "koinon.knowledge.external_reviews"):
        scan_package(package, context.container)
    for cls in (
        PersonalTokenRepository,
        TokenRestriction,
        DomainBindingRepository,
        AuthorizedApplicationRepository,
    ):
        context.register_bean(cls)
    await context.start()
    try:
        await context.get_bean(TenantRepository).save(Tenant(id="north", name="North"))
        await context.get_bean(MembershipRepository).save(
            Membership(id="owner", subject="issuer|owner", tenant_id="north", role="editor")
        )
        catalog = context.get_bean(CatalogService)
        parent = None
        for kind in ("workspace", "project", "collection"):
            parent = await catalog.create(
                "issuer|owner", "north", kind=kind, name=kind, parent_id=parent.id if parent else None
            )
        for token in ("origin", "other"):
            await context.get_bean(PersonalTokenRepository).save(
                PersonalToken(
                    id=token,
                    subject="issuer|owner",
                    tenant_id="north",
                    name=token,
                    token_hash=token[0] * 64,
                    prefix=token,
                    scopes=["catalog:read", "catalog:write", "ingest:write"],
                    expires_at=datetime.now(UTC) + timedelta(hours=1),
                )
            )
        service = context.get_bean(ExternalKnowledgeReviews)
        intents = context.get_bean(KnowledgeIntents)
        yield service, intents, parent, context
    finally:
        await context.stop()
