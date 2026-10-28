# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from koinon.catalog.errors import AccessDenied
from koinon.evidence.access import EvidenceAccess
from koinon.evidence.dtos import SourceReference


def setup():
    member = SimpleNamespace(subject="owner", tenant_id="north", workspace_id="w", role="viewer")
    entries = {
        "a": SimpleNamespace(id="a", tenant_id="north", workspace_id="w", parent_id="w", status="ready"),
        "w": SimpleNamespace(id="w", tenant_id="north", workspace_id="w", parent_id=None, status="ready"),
    }

    async def row(**filters):
        entry = entries.get(filters.get("id"))
        return [entry] if entry and entry.tenant_id == filters.get("tenant_id") else []

    catalog = SimpleNamespace(
        get=AsyncMock(return_value=entries["a"]),
        authorize=AsyncMock(),
        membership_repository=SimpleNamespace(find_all=AsyncMock(return_value=[member])),
        catalog_repository=SimpleNamespace(find_all=AsyncMock(side_effect=row)),
        managed_memberships=None,
    )
    tokens = SimpleNamespace(find_by_id=AsyncMock(return_value=None))
    source = SourceReference(id="s", asset_id="a", title="Policy", kind="document")
    return EvidenceAccess(catalog, tokens), catalog, tokens, source, entries


async def test_recipient_uses_real_context_but_owner_is_checked_without_impersonation():
    access, catalog, _, source, _ = setup()
    await access.check("recipient", "north", (source,), permission="shares:read", owner_subject="owner")
    catalog.get.assert_awaited_once_with("recipient", "north", "a")
    catalog.membership_repository.find_all.assert_awaited_once_with(subject="owner", active=True)
    assert all(call.args[0] == "recipient" for call in catalog.authorize.await_args_list)


async def test_revoked_owner_or_archived_ancestor_blocks_entire_manifest():
    access, catalog, _, source, entries = setup()
    catalog.membership_repository.find_all.return_value = []
    with pytest.raises(AccessDenied):
        await access.check("recipient", "north", (source,), permission="shares:read", owner_subject="owner")
    catalog.membership_repository.find_all.return_value = [
        SimpleNamespace(tenant_id="north", workspace_id="w", role="viewer")
    ]
    entries["w"].status = "archived"
    with pytest.raises(AccessDenied):
        await access.check("recipient", "north", (source,), permission="shares:read", owner_subject="owner")


async def test_revoked_or_expired_originating_token_blocks_persisted_share():
    access, _, tokens, source, _ = setup()
    tokens.find_by_id.return_value = SimpleNamespace(
        subject="owner",
        tenant_id="north",
        revoked_at=None,
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
    )
    with pytest.raises(AccessDenied):
        await access.check(
            "recipient",
            "north",
            (source,),
            permission="shares:read",
            owner_subject="owner",
            originating_token_ids=("pat",),
        )


async def test_scoped_pat_uses_current_resource_checks_instead_of_blanket_denial():
    access, catalog, _, source, _ = setup()
    await access.check("owner", "north", (source,), permission="exports:read")
    catalog.authorize.assert_awaited_once_with("owner", "north", "exports:read", "w")
    catalog.get.side_effect = AccessDenied("Resource exceeds token scope")
    with pytest.raises(AccessDenied):
        await access.check("owner", "north", (source,), permission="exports:read")


async def test_creator_token_remains_bound_to_its_sources_after_interactive_recipient_login():
    access, _, tokens, source, _ = setup()
    token = SimpleNamespace(
        subject="owner",
        tenant_id="north",
        revoked_at=None,
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        scopes=["catalog:read", "shares:write"],
        workspace_ids=["w"],
        asset_ids=["other"],
    )
    tokens.find_by_id.return_value = token
    with pytest.raises(AccessDenied):
        await access.check(
            "recipient",
            "north",
            (source,),
            permission="shares:read",
            owner_subject="owner",
            creator_token_id="pat",
            creator_permission="shares:write",
        )
    token.asset_ids = ["a"]
    await access.check(
        "recipient",
        "north",
        (source,),
        permission="shares:read",
        owner_subject="owner",
        creator_token_id="pat",
        creator_permission="shares:write",
    )
    token.revoked_at = datetime.now(UTC)
    with pytest.raises(AccessDenied):
        await access.check(
            "recipient",
            "north",
            (source,),
            permission="shares:read",
            owner_subject="owner",
            creator_token_id="pat",
            creator_permission="shares:write",
        )


def published_source():
    return SourceReference(
        id="published-reference",
        asset_id="a",
        title="Published threshold",
        kind="knowledge_version",
        knowledge_item_id="a",
        knowledge_version_id="committed-version",
        knowledge_version=1,
        used_revision="knowledge-content-sha256:" + "a" * 64,
    )


@pytest.mark.parametrize("permission", ["shares:read", "shares:write", "exports:read", "exports:write"])
async def test_published_knowledge_fails_closed_after_owner_loses_underlying_workspace(permission):
    access, catalog, _, _, _ = setup()
    item_grant = SimpleNamespace(tenant_id="north", workspace_id="w", role="viewer")
    source_grant = SimpleNamespace(tenant_id="north", workspace_id="source-workspace", role="viewer")
    current_memberships = [item_grant, source_grant]
    catalog.membership_repository.find_all.return_value = current_memberships
    current_memberships.remove(source_grant)
    from pyfly.security.context import SecurityContext
    from pyfly.security.context_holder import SecurityContextHolder

    recipient = SecurityContext(user_id="recipient", attributes={"iss": "issuer", "sub": "recipient"})
    with SecurityContextHolder.using(recipient):
        with pytest.raises(AccessDenied) as raised:
            await access.check(
                "recipient", "north", (published_source(),), permission=permission, owner_subject="owner"
            )
        assert raised.value.code == "CURATED_TRANSITIVE_AUTHORITY_UNQUALIFIED"
        assert SecurityContextHolder.get_context() is recipient
    assert all(call.args[0] == "recipient" for call in catalog.get.await_args_list)


@pytest.mark.parametrize("permission", ["shares:read", "shares:write", "exports:read", "exports:write"])
@pytest.mark.parametrize("token_role", ["origin", "creator"])
async def test_published_knowledge_cannot_skip_underlying_pat_resource_ceilings(permission, token_role):
    access, catalog, tokens, _, _ = setup()
    creator_permission = "shares:write" if permission.startswith("shares:") else "exports:write"
    tokens.find_by_id.return_value = SimpleNamespace(
        subject="owner",
        tenant_id="north",
        revoked_at=None,
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        scopes=["catalog:read", creator_permission],
        workspace_ids=["w"],
        asset_ids=["a"],
    )
    # This valid token covers the published item, but not its underlying source resource.
    options = (
        {"originating_token_ids": ("pat",)}
        if token_role == "origin"
        else {"creator_token_id": "pat", "creator_permission": creator_permission}
    )
    with pytest.raises(AccessDenied) as raised:
        await access.check(
            "recipient",
            "north",
            (published_source(),),
            permission=permission,
            owner_subject="owner",
            **options,
        )
    assert raised.value.code == "CURATED_TRANSITIVE_AUTHORITY_UNQUALIFIED"
    assert all(call.args[0] == "recipient" for call in catalog.get.await_args_list)


async def test_fail_closed_transfer_guard_preserves_owner_evidence_inspection():
    access, catalog, _, _, _ = setup()
    await access.check("owner", "north", (published_source(),), permission="evidence:read")
    catalog.authorize.assert_awaited_once_with("owner", "north", "evidence:read", "w")


@pytest.mark.parametrize("curated_first", [False, True])
async def test_one_unqualified_curated_source_blocks_the_whole_mixed_share(curated_first):
    access, catalog, _, document, _ = setup()
    sources = (published_source(), document) if curated_first else (document, published_source())
    with pytest.raises(AccessDenied) as raised:
        await access.check("recipient", "north", sources, permission="shares:read", owner_subject="owner")
    assert raised.value.code == "CURATED_TRANSITIVE_AUTHORITY_UNQUALIFIED"
    catalog.get.assert_not_awaited()
