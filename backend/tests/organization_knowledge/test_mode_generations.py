# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime, timedelta
from importlib import import_module

import pytest
from pyfly.kernel import ServiceUnavailableException
from sqlalchemy import text

from koinon.security.authority import primary_authority
from koinon.tokens.entities import PersonalToken
from koinon.tokens.repositories import PersonalTokenRepository

generation = import_module("koinon.organization_knowledge.transitions.generations")
pytest_plugins = ("test_organization_knowledge_service",)


async def test_catalog_semantic_changes_coalesce_workspace_and_ignore_rename(knowledge):
    repository = generation.ModeGenerationRepository()
    before = await repository.current("north")
    foreign = await repository.current("south")
    async with primary_authority(read_only=False):
        session = repository._require_session()
        await session.execute(
            text("UPDATE lattice_catalog SET name='Renamed' WHERE id=:id"), {"id": knowledge.workspace.id}
        )
    assert await repository.current("north") == before
    async with primary_authority(read_only=False):
        await repository._require_session().execute(
            text("UPDATE lattice_catalog SET status='archived' WHERE id=:id"), {"id": knowledge.workspace.id}
        )
    after = await repository.current("north")
    assert after > before and await repository.current("south") == foreign
    changes = await repository.changes("north", after_generation=before)
    assert [(value.generation, value.workspace_id) for value in changes] == [(after, knowledge.workspace.id)]
    assert (
        await repository.changes("north", after_generation=after, after_workspace_id=knowledge.workspace.id)
        == []
    )


async def test_credential_usage_does_not_invalidate_readiness_but_revocation_does(knowledge):
    repository = generation.ModeGenerationRepository()
    token = await PersonalTokenRepository().save(
        PersonalToken(
            id="controlled-token",
            subject="admin",
            tenant_id="north",
            name="Controlled",
            token_hash="a" * 64,
            prefix="controlled",
            scopes=["settings:write"],
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
    )
    before = await repository.current("north")
    token.last_used_at = datetime.now(UTC)
    await PersonalTokenRepository().save(token)
    assert await repository.current("north") == before
    token.revoked_at = datetime.now(UTC)
    await PersonalTokenRepository().save(token)
    changes = await repository.changes("north", after_generation=before)
    assert len(changes) == 1 and changes[0].workspace_id == ""


async def test_rolled_back_change_does_not_advance_generation_or_journal(knowledge):
    repository = generation.ModeGenerationRepository()
    before = await repository.current("north")
    with pytest.raises(RuntimeError, match="rollback"):
        async with primary_authority(read_only=False):
            await repository._require_session().execute(
                text("UPDATE lattice_memberships SET active=false WHERE subject='admin'")
            )
            assert await repository.current("north") > before
            raise RuntimeError("rollback")
    assert await repository.current("north") == before
    assert await repository.changes("north", after_generation=before, after_workspace_id="~") == []


async def test_missing_counter_fails_closed_and_journal_pages_reject_invalid_limits(knowledge):
    repository = generation.ModeGenerationRepository()
    async with primary_authority(read_only=False):
        await repository._require_session().execute(
            text("DELETE FROM koinon_knowledge_readiness_generations WHERE tenant_id='south'")
        )
    with pytest.raises(ServiceUnavailableException) as error:
        await repository.current("south")
    assert error.value.code == "KNOWLEDGE_MODE_GENERATION_UNAVAILABLE"
    for limit in (0, 101, True):
        with pytest.raises(ValueError):
            await repository.changes("north", after_generation=0, limit=limit)


async def test_snapshot_watermark_excludes_its_whole_generation_but_page_cursor_keeps_siblings(knowledge):
    repository = generation.ModeGenerationRepository()
    current = await repository.current("north")
    async with primary_authority(read_only=False):
        session = repository._require_session()
        await session.execute(text("DELETE FROM koinon_knowledge_readiness_changes WHERE tenant_id='north'"))
        for workspace in ("", "first", "second"):
            await session.execute(
                text(
                    "INSERT INTO koinon_knowledge_readiness_changes(tenant_id,workspace_id,generation) "
                    "VALUES ('north',:workspace,:generation)"
                ),
                {"workspace": workspace, "generation": current},
            )
    assert await repository.changes("north", after_generation=current) == []
    first = await repository.changes("north", after_generation=current - 1, limit=1)
    assert first == [generation.ReadinessChange(current, "")]
    second = await repository.changes("north", after_generation=current, after_workspace_id="", limit=1)
    assert second == [generation.ReadinessChange(current, "first")]


async def test_index_job_parent_link_changes_invalidate_but_worker_polling_does_not(knowledge):
    from test_mode_transitions import transitions

    service = transitions(knowledge)
    repository = generation.ModeGenerationRepository()
    before = await repository.current("north")
    unrelated = await service.jobs.submit("north", "scope", "knowledge.mode", {}, "unrelated-mode")
    assert await repository.current("north") == before
    child = await service.jobs.submit(
        "north",
        knowledge.workspace.id,
        "knowledge.index",
        {"parent_mode_transition_id": "parent-one"},
        "linked-index",
    )
    before = await repository.current("north")
    assert before > 0
    child.status, child.progress = "running", 50
    await service.jobs.repository.save(child)
    assert await repository.current("north") == before
    child.payload = {"parent_mode_transition_id": "parent-two"}
    await service.jobs.repository.save(child)
    assert await repository.current("north") > before
    before = await repository.current("north")
    child.kind = "other"
    await service.jobs.repository.save(child)
    assert await repository.current("north") > before
    assert unrelated.kind == "knowledge.mode"
