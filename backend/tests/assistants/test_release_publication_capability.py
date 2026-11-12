# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""A publication permission belongs to one task, unit and exact object."""

import asyncio
from copy import copy
from types import SimpleNamespace

import pytest
from test_service import assistants as assistants

from koinon.answers import release_proofs as proofs


@pytest.mark.parametrize("mutation", ["copy", "plain", "unit", "task", "expired", "consumed", "release"])
async def test_publication_rejects_capability_rebinding(monkeypatch, mutation):
    unit = SimpleNamespace(completed=False, read_only=False)
    monkeypatch.setattr(proofs, "current_unit_of_work", lambda _name: unit)
    permit = proofs._Publication(
        task=asyncio.current_task(),
        unit=unit,
        assistants=object(),
        run_id="run",
        worker_id="worker",
        release_id="release",
        identity=(),
        generation=None,
        reset=None,
    )
    token = proofs._publication.set(permit)
    try:
        candidate = copy(permit) if mutation == "copy" else permit
        if mutation == "plain":
            candidate = "run"
        if mutation == "unit":
            permit.unit = object()
        if mutation == "task":
            permit.task = object()
        if mutation == "expired":
            permit.active = False
        if mutation == "consumed":
            permit.used = True
        with pytest.raises(proofs.PublicationRejected):
            proofs._require_publication(candidate, "other" if mutation == "release" else "release")
    finally:
        proofs._publication.reset(token)


async def test_inherited_context_cannot_publish_from_a_child_task(monkeypatch):
    unit = SimpleNamespace(completed=False, read_only=False)
    monkeypatch.setattr(proofs, "current_unit_of_work", lambda _name: unit)
    permit = proofs._Publication(
        task=asyncio.current_task(),
        unit=unit,
        assistants=object(),
        run_id="run",
        worker_id="worker",
        release_id="release",
        identity=(),
        generation=None,
        reset=None,
    )
    token = proofs._publication.set(permit)
    try:

        async def child():
            proofs._require_publication(permit, "release")

        with pytest.raises(proofs.PublicationRejected):
            await asyncio.create_task(child())
        assert proofs._require_publication(permit, "release") is permit
    finally:
        proofs._publication.reset(token)


@pytest.mark.parametrize("fail_publication", [False, True])
async def test_queue_calls_proof_writer_before_events_and_rolls_back_on_failure(
    assistants, monkeypatch, fail_publication
):
    from contextlib import asynccontextmanager
    from uuid import uuid4

    from test_output_release import prepared

    from koinon.answers.dtos import EvidenceAnswerPlan
    from koinon.answers.receipts import verified_release
    from koinon.assistants import queue as queue_module
    from koinon.assistants import run_sources

    service, _, queue, run, _ = await prepared(assistants)
    original_boundary = run_sources.run_source_unit
    publication = SimpleNamespace(release_id=uuid4().hex)
    observed = []

    @asynccontextmanager
    async def observed_boundary(*args, publish_proof=False, **kwargs):
        # This consumer-contract test isolates the writer; real capability/role checks run on PostgreSQL.
        if kwargs.get("purpose") == "release_answer":
            assert publish_proof is True
        async with original_boundary(*args, publish_proof=False, **kwargs):
            yield

    class ProofRecorder:
        async def publish_verified_release(self, admission, release_id):
            assert admission is publication and release_id == publication.release_id
            await service.results._require_session().flush()
            message = await service.message_repository.find_by_id(run.message_id)
            rows = await service.active_results(run)
            assert verified_release(message, rows) is not None
            assert any(row.id == release_id and row.kind == "answer_release" for row in rows)
            assert not any(
                event.type == "message_delta" for event in await service.events.find_after(run.id, 0)
            )
            observed.append(release_id)
            if fail_publication:
                raise RuntimeError("controlled proof writer failure")

    monkeypatch.setattr(run_sources, "run_source_unit", observed_boundary)
    monkeypatch.setattr(queue_module, "current_publication", lambda: publication)
    queue.release_proofs = SimpleNamespace(get=lambda: ProofRecorder())
    facts = await queue.fact_pool(run.id, "proposal-worker")
    plan = EvidenceAnswerPlan(
        outcome="answer", quotes=[{"fact_id": facts[0].id, "quote": "Verified native chunk"}]
    )
    if fail_publication:
        with pytest.raises(RuntimeError, match="proof writer failure"):
            await queue.release_answer(run.id, "proposal-worker", plan, "en")
    else:
        await queue.release_answer(run.id, "proposal-worker", plan, "en")
    assert observed == [publication.release_id]
    releases = [row for row in await service.results.find_all(run_id=run.id) if row.kind == "answer_release"]
    message = await service.message_repository.find_by_id(run.message_id)
    if fail_publication:
        assert releases == [] and message.text == ""
    else:
        assert len(releases) == 1 and releases[0].id == publication.release_id
        assert "Verified native chunk" in message.text


@pytest.mark.parametrize("guard", ["object", "task", "unit", "single_use"])
async def test_capability_denial_is_causal_when_each_guard_is_removed(monkeypatch, guard):
    import ast
    import inspect
    import textwrap

    expressions = {
        "object": "candidate is not _publication.get()",
        "task": "candidate.task is not asyncio.current_task()",
        "unit": "candidate.unit is not unit",
        "single_use": "candidate.used",
    }
    original = proofs._require_publication
    tree = ast.parse(textwrap.dedent(inspect.getsource(original)))
    removed = []
    for node in ast.walk(tree):
        if isinstance(node, ast.BoolOp):
            matching = [term for term in node.values if ast.unparse(term) == expressions[guard]]
            removed.extend(matching)
            node.values = [term for term in node.values if term not in matching]
    assert len(removed) == 1
    namespace = dict(original.__globals__)
    exec(
        compile(ast.fix_missing_locations(tree), "<controlled-capability-guard-mutation>", "exec"), namespace
    )
    mutant = namespace[original.__name__]
    unit = SimpleNamespace(completed=False, read_only=False)
    monkeypatch.setattr(proofs, "current_unit_of_work", lambda _name: unit)
    # Both functions must use the same test unit; only the named rejection term differs.
    mutant.__globals__["current_unit_of_work"] = proofs.current_unit_of_work
    permit = proofs._Publication(
        task=asyncio.current_task(),
        unit=unit,
        assistants=object(),
        run_id="run",
        worker_id="worker",
        release_id="release",
        identity=(),
        generation=None,
        reset=None,
    )
    token = proofs._publication.set(permit)
    try:
        assert proofs._require_publication(permit, "release") is permit
        candidate = copy(permit) if guard == "object" else permit
        field = {"task": "task", "unit": "unit", "single_use": "used"}.get(guard)
        previous = getattr(permit, field) if field else None
        if field:
            setattr(permit, field, True if field == "used" else object())

        def assert_denied():
            try:
                proofs._require_publication(candidate, "release")
            except proofs.PublicationRejected:
                return
            raise AssertionError("invalid capability was admitted")

        assert_denied()
        with monkeypatch.context() as mutation:
            mutation.setattr(proofs, "_require_publication", mutant)
            with pytest.raises(AssertionError, match="invalid capability was admitted"):
                assert_denied()
        assert_denied()
        if field:
            setattr(permit, field, previous)
        assert proofs._require_publication(permit, "release") is permit
    finally:
        proofs._publication.reset(token)
