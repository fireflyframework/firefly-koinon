# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import asyncio
from types import SimpleNamespace

import pytest
from pyfly.kernel import ConflictException

from koinon.catalog.errors import AccessDenied
from koinon.organization_knowledge.dtos import OrganizationKnowledgeSnapshot, snapshot_digest
from koinon.organization_knowledge.runtime import bind_snapshot, current_snapshot, snapshot_for_run


def snapshot(tenant="north", mode="rag", revision=0):
    values = dict(
        tenant_id=tenant,
        schema_version=1,
        revision=revision,
        origin="organization" if revision else "deployment",
        documents=dict(
            answer_mode=mode,
            retrieval_top_k=10,
            retrieval_per_query_k=30,
            retrieval_rrf_k=60,
            query_expansion_enabled=False,
            query_expansion_n=3,
            answer_top_k=10,
            rlm_max_iters=8,
            rlm_sub_budget=12,
            rlm_max_depth=1,
            rlm_self_consistency=1,
            rlm_extended_reasoning=False,
        ),
        structured=dict(
            top_k_schema=12,
            top_k_examples=5,
            top_k_metrics=8,
            rrf_k=60,
            generation_candidates=3,
            max_refine_retries=2,
            grounding_min_confidence=0.55,
        ),
    )
    return OrganizationKnowledgeSnapshot.model_validate({**values, "digest": snapshot_digest(values)})


def test_policy_scope_rejects_other_subject_or_organization_and_cleans_up():
    assert current_snapshot("issuer|one", "north") is None
    value = snapshot()
    with bind_snapshot(value, "issuer|one"):
        assert current_snapshot("issuer|one", "north") == value
        for subject, tenant in (("issuer|two", "north"), ("issuer|one", "south")):
            with pytest.raises(AccessDenied):
                current_snapshot(subject, tenant)
    assert current_snapshot("issuer|one", "north") is None


@pytest.mark.asyncio
async def test_concurrent_organizations_keep_independent_frozen_policies():
    async def read(tenant, mode):
        with bind_snapshot(snapshot(tenant, mode), "issuer|one"):
            await asyncio.sleep(0)
            return current_snapshot("issuer|one", tenant).documents.answer_mode

    assert await asyncio.gather(read("north", "rag"), read("south", "rlm")) == ["rag", "rlm"]


@pytest.mark.asyncio
async def test_inherited_child_cannot_borrow_closed_policy_or_fall_back_to_new_defaults():
    release = asyncio.Event()

    async def inherited():
        await release.wait()
        with pytest.raises(AccessDenied):
            current_snapshot("issuer|one", "north")

    with bind_snapshot(snapshot(), "issuer|one"):
        child = asyncio.create_task(inherited())
    release.set()
    await child


@pytest.mark.asyncio
async def test_nested_child_cannot_extend_its_parent_policy_lifetime():
    ready, release = asyncio.Event(), asyncio.Event()
    value = snapshot()

    async def nested():
        with bind_snapshot(value, "issuer|one"):
            ready.set()
            await release.wait()
            with pytest.raises(AccessDenied):
                current_snapshot("issuer|one", "north")

    with bind_snapshot(value, "issuer|one"):
        child = asyncio.create_task(nested())
        await ready.wait()
    release.set()
    await child


def test_nested_policy_cannot_silently_replace_the_admitted_revision():
    with (
        bind_snapshot(snapshot(), "issuer|one"),
        pytest.raises(AccessDenied),
        bind_snapshot(snapshot(revision=1), "issuer|one"),
    ):
        pass


def test_run_snapshot_preserves_old_policy_and_rejects_tampering_or_foreign_tenant():
    value = snapshot(mode="rlm", revision=3)
    run = SimpleNamespace(tenant_id="north", knowledge_settings_snapshot=value.model_dump(mode="json"))
    assert snapshot_for_run(run) == value
    run.knowledge_settings_snapshot["documents"]["answer_mode"] = "rag"
    with pytest.raises(ConflictException):
        snapshot_for_run(run)
    run.knowledge_settings_snapshot = value.model_dump(mode="json")
    run.tenant_id = "south"
    with pytest.raises(ConflictException):
        snapshot_for_run(run)


def test_historical_missing_policy_remains_unknown():
    assert snapshot_for_run(SimpleNamespace(tenant_id="north")) is None
    assert snapshot_for_run(SimpleNamespace(tenant_id="north", knowledge_settings_snapshot=None)) is None
