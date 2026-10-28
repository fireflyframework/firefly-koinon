# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime, timedelta

import pytest
from pyfly.kernel import ConflictException
from test_provider_service import identities as identities
from test_provider_service import local_input

from koinon.catalog.entities import Membership
from koinon.catalog.repositories import MembershipRepository
from koinon.corporate_identity.directory import NativeCorporateDirectory
from koinon.corporate_identity.dtos import IdentityActivation, IdentityMappingInput
from koinon.corporate_identity.entities import CorporateValidation
from koinon.corporate_identity.repositories import CorporateValidationRepository


async def test_real_mapping_and_exact_activation_proof_preserve_manual_recovery(identities, monkeypatch):
    service, context = identities
    provider = await service.create("issuer|admin", "north", local_input())
    directory = context.get_bean(NativeCorporateDirectory)

    async def acquire(*args):
        return "synthetic-token"

    async def group(settings, token, identifier):
        assert identifier == "directory-group"
        return {"id": identifier, "name": "Research team", "path": "/Research"}

    monkeypatch.setattr(directory, "acquire", acquire)
    monkeypatch.setattr(directory, "group", group)
    mapping = await service.save_mapping(
        "issuer|admin", "north", provider.id, IdentityMappingInput(group_id="directory-group", role="editor")
    )
    assert mapping["group_name"] == "Research team" and mapping["role"] == "editor"
    latest = await service.get("issuer|admin", "north", provider.id)
    assert latest.status == "draft" and latest.policy_revision == 2
    body = IdentityActivation(expected_revision=latest.revision, validation_id="missing")
    with pytest.raises(ConflictException, match="fresh sign-in"):
        await service.activate("issuer|admin", "north", provider.id, body)
    now = datetime.now(UTC)
    proofs = context.get_bean(CorporateValidationRepository)
    row = CorporateValidation(
        id="observed-proof",
        tenant_id="north",
        provider_id=provider.id,
        requested_by="issuer|admin",
        revision=latest.revision,
        policy_revision=latest.policy_revision,
        status="verified",
        checks_json=[
            {"id": name, "status": "passed", "verified": True} for name in ("fresh_sso", "directory")
        ],
        issued_at=now,
        expires_at=now + timedelta(minutes=5),
    )
    await proofs.save(row)
    body = IdentityActivation(expected_revision=latest.revision, validation_id=row.id)
    with pytest.raises(ConflictException, match="unverified"):
        await service.activate("issuer|admin", "north", provider.id, body)
    row.checks_json = row.checks_json + [{"id": "broker_policy", "status": "passed", "verified": True}]
    await proofs.save(row)
    active = await service.activate("issuer|admin", "north", provider.id, body)
    assert active.status == "active" and active.revision == latest.revision + 1
    assert (await proofs.find_by_id(row.id)).status == "consumed"
    with pytest.raises(ConflictException):
        await service.activate("issuer|admin", "north", provider.id, body)
    manual = await context.get_bean(MembershipRepository).find_all(tenant_id="north")
    assert len(manual) == 2 and all(isinstance(member, Membership) for member in manual)
    await service.remove_mapping("issuer|admin", "north", provider.id, mapping["id"], mapping["revision"])
    assert (await service.get("issuer|admin", "north", provider.id)).status == "draft"
