# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime, timedelta

from test_provider_service import identities as identities
from test_provider_service import local_input

from koinon.catalog.entities import Membership
from koinon.catalog.repositories import MembershipRepository
from koinon.catalog.service import CatalogService
from koinon.corporate_identity.directory import NativeCorporateDirectory
from koinon.corporate_identity.entities import CorporateMapping
from koinon.corporate_identity.policy import CorporateIdentity, DirectorySnapshot
from koinon.corporate_identity.repositories import (
    CorporateGrantRepository,
    CorporateMappingRepository,
    CorporateProviderRepository,
)


async def test_expired_managed_access_rechecks_directory_and_preserves_manual_grants(identities, monkeypatch):
    service, context = identities
    catalog = context.get_bean(CatalogService)
    subject = "https://identity.example.test/realms/koinon|researcher"
    await context.get_bean(MembershipRepository).save(
        Membership(id="manual", subject=subject, tenant_id="north", role="viewer")
    )
    provider = await service.create("issuer|admin", "north", local_input())
    row = await context.get_bean(CorporateProviderRepository).find_by_id(provider.id)
    row.status = "active"
    await context.get_bean(CorporateProviderRepository).save(row)
    await context.get_bean(CorporateMappingRepository).save(
        CorporateMapping(
            id="refresh-rule",
            tenant_id="north",
            provider_id=provider.id,
            group_id="research",
            group_name="Research",
            role="editor",
            enabled=True,
            revision=1,
        )
    )
    now = datetime.now(UTC)
    await service.reconcile(
        provider.id,
        CorporateIdentity(subject, "researcher", False),
        DirectorySnapshot("researcher", frozenset({"research"}), True, now, now + timedelta(seconds=60)),
        expected_policy_revision=1,
    )
    grants = context.get_bean(CorporateGrantRepository)
    grant = (await grants.find_all(subject=subject))[0]
    grant.expires_at = now - timedelta(seconds=1)
    await grants.save(grant)
    assert await grants.current(subject, row.canonical_issuer) == []
    calls = []

    async def acquire(*args):
        return "synthetic-only"

    async def observe(settings, token, external):
        calls.append(external)
        observed = datetime.now(UTC)
        return DirectorySnapshot(external, frozenset(), True, observed, observed + timedelta(seconds=60))

    directory = context.get_bean(NativeCorporateDirectory)
    monkeypatch.setattr(directory, "acquire", acquire)
    monkeypatch.setattr(directory, "observe", observe)
    assert "catalog:write" not in await catalog.permissions(subject, "north")
    assert "catalog:read" in await catalog.permissions(subject, "north")
    assert calls == ["researcher"]
    assert (await context.get_bean(MembershipRepository).find_by_id("manual")).active is True
    assert (await grants.find_by_id(grant.id)).active is False
