# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from unittest.mock import AsyncMock

import pytest
from pyfly.kernel import ConflictException
from test_service import assistants as assistants
from test_service import configured

from koinon.assistants.queue import AssistantQueue
from koinon.catalog.errors import AccessDenied


async def proposal_fixture(service, context):
    from koinon.assistants.proposals import CatalogProposals

    parent = None
    for kind in ("workspace", "project", "collection", "source", "document"):
        parent = await service.catalog.create(
            "issuer|admin", "north", kind=kind, name=kind, parent_id=parent.id if parent else None
        )
    _, agent = await configured(service)
    thread = await service.create_thread("issuer|admin", "north", {"scope": {"asset_ids": [parent.id]}})
    await service.submit(
        "issuer|admin",
        "north",
        thread["id"],
        {"agent_id": agent["id"], "message": "Propose a clearer title", "client_request_id": "proposal"},
    )
    queue = context.get_bean(AssistantQueue)
    run = await queue.claim("proposal-worker")
    proposals = context.get_bean(CatalogProposals)
    proposal = await proposals.propose(run.id, "proposal-worker", parent.id, {"name": "Reviewed title"})
    return proposals, proposal, run, parent


async def test_proposal_is_durable_read_only_until_explicit_owner_confirmation_and_replay_is_idempotent(
    assistants,
):
    from koinon.assistants.proposal_dtos import ProposalConfirmation

    service, context = assistants
    proposals, proposal, run, entry = await proposal_fixture(service, context)
    assert proposal.status == "pending" and proposal.before.name == "document"
    assert (await service.catalog.get("issuer|admin", "north", entry.id)).name == "document"
    for subject, tenant in (("issuer|other", "north"), ("issuer|outsider", "south")):
        with pytest.raises(AccessDenied):
            await proposals.get(subject, tenant, run.id, proposal.id)
    with pytest.raises(ConflictException):
        await proposals.confirm(
            "issuer|admin",
            "north",
            run.id,
            proposal.id,
            ProposalConfirmation(confirm=True, expected_revision=1),
        )
    await context.get_bean(AssistantQueue).finish(run.id, "proposal-worker")
    applied = await proposals.confirm(
        "issuer|admin", "north", run.id, proposal.id, ProposalConfirmation(confirm=True, expected_revision=1)
    )
    assert applied.status == "applied" and applied.revision == 2
    updated = await service.catalog.get("issuer|admin", "north", entry.id)
    assert updated.name == "Reviewed title"
    replay = await proposals.confirm(
        "issuer|admin", "north", run.id, proposal.id, ProposalConfirmation(confirm=True, expected_revision=1)
    )
    assert replay == applied
    assert (await service.catalog.get("issuer|admin", "north", entry.id)).updated_at == updated.updated_at


async def test_stale_resource_revoked_authority_and_superseded_attempt_deny_apply(assistants):
    from koinon.assistants.proposal_dtos import ProposalConfirmation

    service, context = assistants
    proposals, proposal, run, entry = await proposal_fixture(service, context)
    await context.get_bean(AssistantQueue).finish(run.id, "proposal-worker")
    await service.catalog.update("issuer|admin", "north", entry.id, {"description": "Concurrent edit"})
    with pytest.raises(ConflictException) as failure:
        await proposals.confirm(
            "issuer|admin",
            "north",
            run.id,
            proposal.id,
            ProposalConfirmation(confirm=True, expected_revision=1),
        )
    assert failure.value.code == "PROPOSAL_RESOURCE_CHANGED"
    assert (await service.catalog.get("issuer|admin", "north", entry.id)).name == "document"
    membership = await service.catalog.membership_repository.find_by_id("admin")
    membership.active = False
    await service.catalog.membership_repository.save(membership)
    with pytest.raises(AccessDenied):
        await proposals.confirm(
            "issuer|admin",
            "north",
            run.id,
            proposal.id,
            ProposalConfirmation(confirm=True, expected_revision=1),
        )


async def test_failed_catalog_audit_rolls_back_catalog_and_proposal_together(assistants, monkeypatch):
    from koinon.assistants.proposal_dtos import ProposalConfirmation
    from koinon.catalog.service import CatalogService

    service, context = assistants
    proposals, proposal, run, entry = await proposal_fixture(service, context)
    await context.get_bean(AssistantQueue).finish(run.id, "proposal-worker")
    monkeypatch.setattr(
        CatalogService, "_audit", AsyncMock(side_effect=RuntimeError("controlled storage failure"))
    )
    with pytest.raises(RuntimeError):
        await proposals.confirm(
            "issuer|admin",
            "north",
            run.id,
            proposal.id,
            ProposalConfirmation(confirm=True, expected_revision=1),
        )
    assert (await service.catalog.get("issuer|admin", "north", entry.id)).name == "document"
    assert (await proposals.get("issuer|admin", "north", run.id, proposal.id)).status == "pending"


async def test_proposals_cannot_escape_run_scope_and_cancel_never_mutates_resource(assistants):
    service, context = assistants
    proposals, proposal, run, entry = await proposal_fixture(service, context)
    other = await service.catalog.create(
        "issuer|admin", "north", kind="document", name="Other", parent_id=entry.parent_id
    )
    with pytest.raises(AccessDenied):
        await proposals.propose(run.id, "proposal-worker", other.id, {"name": "Escaped"})
    cancelled = await proposals.cancel("issuer|admin", "north", run.id, proposal.id, expected_revision=1)
    assert cancelled.status == "cancelled" and cancelled.revision == 2
    assert (
        await proposals.cancel("issuer|admin", "north", run.id, proposal.id, expected_revision=1) == cancelled
    )
    assert (await service.catalog.get("issuer|admin", "north", entry.id)).name == "document"
    run.attempts += 1
    await service.runs.save(run)
    with pytest.raises(ConflictException) as failure:
        await proposals.get("issuer|admin", "north", run.id, proposal.id)
    assert failure.value.code == "PROPOSAL_SUPERSEDED"


async def test_original_token_authority_is_required_and_confirm_requires_exact_boolean(assistants):
    from pydantic import ValidationError
    from pyfly.kernel import ServiceUnavailableException

    from koinon.assistants.proposal_dtos import ProposalConfirmation

    service, context = assistants
    proposals, proposal, run, entry = await proposal_fixture(service, context)
    run.access_token_id = "original-token"
    await service.runs.save(run)
    with pytest.raises(ServiceUnavailableException):
        await proposals.get("issuer|admin", "north", run.id, proposal.id)
    for confirm in (False, 1, "true"):
        with pytest.raises(ValidationError):
            ProposalConfirmation(confirm=confirm, expected_revision=1)


async def test_native_tool_can_only_propose_and_private_runs_cannot_expose_it(assistants):
    from koinon.assistants.execution import AssistantExecutor

    service, context = assistants
    proposals, proposal, run, entry = await proposal_fixture(service, context)
    executor = context.get_bean(AssistantExecutor)
    tools = await executor.tools(run.id, "proposal-worker", ["propose_catalog_update"])
    assert [tool.name for tool in tools] == ["propose_catalog_update"]
    value = await tools[0].execute(asset_id=entry.id, description="Clearer description")
    assert value["proposal"]["status"] == "pending" and value["requires_user_confirmation"] is True
    assert (await service.catalog.get("issuer|admin", "north", entry.id)).description == ""
    from test_attachment_execution import ref

    assert (
        await executor.tools(
            run.id,
            "proposal-worker",
            ["propose_catalog_update"],
            attachment_refs=(ref(),),
            private_search_enabled=False,
        )
        == []
    )


async def test_explicit_retry_cannot_revive_an_older_proposal_with_reused_attempt_number(assistants):
    service, context = assistants
    proposals, proposal, run, entry = await proposal_fixture(service, context)
    await service.cancel("issuer|admin", "north", run.id)
    await service.retry("issuer|admin", "north", run.id)
    claimed = await context.get_bean(AssistantQueue).claim("replacement-worker")
    assert claimed.id == run.id and claimed.attempts == 1
    with pytest.raises(ConflictException) as error:
        await proposals.get("issuer|admin", "north", run.id, proposal.id)
    assert error.value.code == "PROPOSAL_SUPERSEDED"
