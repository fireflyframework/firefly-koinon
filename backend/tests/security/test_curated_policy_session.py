# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Curated fixed-set policy and actual Catalog/CIAM helpers share one native Session."""

from types import SimpleNamespace

from pyfly.data.transaction import TransactionTemplate, current_unit_of_work
from sqlalchemy import update
from test_primary_authority import SUBJECT
from test_primary_authority import authority as authority

from koinon.catalog.entities import CatalogEntry, Membership
from koinon.catalog.repositories import MembershipRepository
from koinon.corporate_identity.entities import CorporateGrant, CorporateMapping, CorporateProvider
from koinon.corporate_identity.repositories import CorporateGrantRepository
from koinon.knowledge.curated.corpus import CuratedBodyCorpus, ServingVersion
from koinon.knowledge.curated.release_dtos import CuratedReleaseStamp
from koinon.security.authority import PRIMARY_POLICY_UNIT, primary_authority


async def test_curated_release_keeps_catalog_ciam_and_fresh_checks_in_one_fixed_session(
    authority, monkeypatch
):
    async with TransactionTemplate("primary").transaction() as writer:
        await writer.resource.execute(update(Membership).values(active=True))
        await writer.resource.execute(update(CorporateProvider).values(status="active"))
        await writer.resource.execute(update(CorporateMapping).values(enabled=True))
        await writer.resource.execute(update(CorporateGrant).values(active=True))
        writer.resource.add(
            CatalogEntry(
                id="workspace",
                tenant_id="tenant",
                workspace_id="workspace",
                kind="workspace",
                name="Inert workspace",
                created_by=SUBJECT,
            )
        )

    participants, fixed = [], []
    members = authority.ctx.get_bean(MembershipRepository)
    grants = authority.ctx.get_bean(CorporateGrantRepository)
    member_rows, managed_rows = members.find_all, grants.current

    async def observe_members(*args, **kwargs):
        participants.append(("catalog", current_unit_of_work("primary"), members._session))
        return await member_rows(*args, **kwargs)

    async def observe_managed(*args, **kwargs):
        participants.append(("ciam", current_unit_of_work("primary"), grants._session))
        return await managed_rows(*args, **kwargs)

    monkeypatch.setattr(members, "find_all", observe_members)
    monkeypatch.setattr(grants, "current", observe_managed)

    @primary_authority(fresh=True)
    async def fresh():
        unit = current_unit_of_work("primary")
        participants.append(("fresh", unit, unit.resource))

    async def version(subject, tenant, item, selected):
        unit = current_unit_of_work("primary")
        if not fixed:
            fixed.append(unit)
        await authority.managed.authorize(subject, tenant, "identity:manage")
        await fresh()
        return SimpleNamespace(
            selected_version=SimpleNamespace(
                version_id=item + "-version", version=selected, serving=True, publication="published"
            )
        )

    async def scope(subject, tenant, item):
        await authority.managed.memberships(subject)
        return SimpleNamespace(workspace_id="workspace"), SimpleNamespace(
            native_item_id=item + "-native",
            native_workspace_id="native",
            serving_version_id=item + "-version",
            serving_version=1,
        )

    stamp = CuratedReleaseStamp("0" * 64, "0" * 64, 0)

    class Release:
        async def observe(self, *args):
            return stamp

        async def observe_bound(self, *args):
            unit = current_unit_of_work("primary")
            participants.append(("observation", unit, unit.resource))
            return stamp

        async def require_unchanged(self, *args):
            return None

    corpus = CuratedBodyCorpus(
        SimpleNamespace(version=version, scope=scope, authority=SimpleNamespace(catalog=authority.managed)),
        Release(),
    )
    selected = tuple(
        ServingVersion(item, "workspace", item + "-native", "native", item + "-version", 1)
        for item in ("first", "second")
    )
    async with TransactionTemplate("primary", read_only=True).transaction() as replica:
        await corpus.authorize_release(SUBJECT, "tenant", selected)
        assert fixed[0] is not replica and current_unit_of_work("primary") is replica
    assert fixed[0].definition.name == PRIMARY_POLICY_UNIT and fixed[0].read_from_primary
    assert {name for name, _, _ in participants} == {"catalog", "ciam", "fresh", "observation"}
    assert all(unit is fixed[0] and session is fixed[0].resource for _, unit, session in participants)
