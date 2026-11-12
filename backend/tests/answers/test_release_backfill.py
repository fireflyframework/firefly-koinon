# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Bounded maintenance work never shares a claim transaction with verification."""

from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

import pytest

from koinon.answers.release_backfill import AnswerReleaseBackfill
from koinon.answers.release_proof_dtos import ReleaseProjectionClaim, ReleaseProjectionCursor


class Journal:
    def __init__(self, count):
        self.events = []
        self.remaining = count
        self.claim = ReleaseProjectionClaim(
            job_id="job",
            claim_token="claim",
            revision=1,
            claim_until=datetime.now(UTC) + timedelta(seconds=30),
        )
        self.transaction = 0

    @asynccontextmanager
    async def unit(self):
        self.transaction += 1
        self.events.append(("begin", self.transaction))
        yield self
        self.events.append(("commit", self.transaction))

    async def acquire(self, job_id, tenant_id):
        self.events.append(("claim", self.transaction))
        return self.claim

    async def candidates(self, claim, *, limit):
        self.events.append(("candidates", self.transaction))
        if not self.remaining:
            return ()
        return (ReleaseProjectionCursor(created_at=datetime.now(UTC), release_result_id=str(self.remaining)),)

    async def process(self, claim, cursor):
        self.events.append(("verify", self.transaction))
        self.remaining -= 1
        self.claim = claim.model_copy(
            update={"revision": claim.revision + 1, "state": "complete" if not self.remaining else "running"}
        )
        return self.claim, "projected"


async def test_each_release_gets_a_new_committed_unit_and_batch_stops_at_25():
    journal = Journal(30)
    runner = AnswerReleaseBackfill(journal.unit)
    report = await runner.run("job")
    assert report.processed == 25
    assert report.state == "running"
    assert journal.events[:3] == [("begin", 1), ("claim", 1), ("commit", 1)]
    transactions = [number for event, number in journal.events if event == "verify"]
    assert len(transactions) == len(set(transactions)) == 25
    assert all(number > 1 for number in transactions)
    assert journal.remaining == 5


async def test_monotonic_budget_stops_before_starting_another_candidate():
    journal = Journal(30)
    ticks = iter((0.0, 0.1, 5.0, 5.0))
    runner = AnswerReleaseBackfill(journal.unit, clock=lambda: next(ticks))
    report = await runner.run("job")
    assert report.processed == 1
    assert journal.remaining == 29
    assert report.state == "running"


async def test_blocked_candidate_is_retained_and_no_later_candidate_runs():
    journal = Journal(2)

    async def blocked(claim, cursor):
        journal.events.append(("blocked", journal.transaction))
        return claim.model_copy(update={"state": "blocked"}), "blocked"

    journal.process = blocked
    report = await AnswerReleaseBackfill(journal.unit).run("job")
    assert report.state == "blocked" and report.processed == 1
    assert journal.remaining == 2
    assert sum(event == "blocked" for event, _ in journal.events) == 1


async def test_completed_audit_does_not_hide_unprojected_rollout_arrivals():
    journal = Journal(1)

    async def tail(_claim):
        return ("arrived-after-high-water",), True

    journal.rollout_tail = tail
    report = await AnswerReleaseBackfill(journal.unit, audit=True).run("audit")
    assert report.state == "rollout_pending"
    assert report.rollout_unprojected == ("arrived-after-high-water",)
    assert report.rollout_more is True


async def test_audit_reports_completion_only_after_its_rollout_tail_is_checked():
    journal = Journal(1)

    async def tail(_claim):
        journal.events.append(("tail", journal.transaction))
        return (), False

    journal.rollout_tail = tail
    report = await AnswerReleaseBackfill(journal.unit, audit=True).run("audit")
    assert report.state == "complete" and report.rollout_unprojected == ()
    assert [event for event, _ in journal.events][-2:] == ["tail", "commit"]


async def test_completed_audit_retries_timed_out_coverage_without_mutating_candidates():
    journal = Journal(0)
    journal.claim = journal.claim.model_copy(update={"state": "complete"})
    attempts = 0

    async def coverage(_claim):
        nonlocal attempts
        attempts += 1
        journal.events.append(("coverage", journal.transaction))
        if attempts == 1:
            raise TimeoutError()
        return (), False

    journal.rollout_tail = coverage
    runner = AnswerReleaseBackfill(journal.unit, audit=True)
    pending = await runner.run("audit")
    assert pending.state == "coverage_pending" and pending.processed == 0
    resumed = await runner.run("audit")
    assert resumed.state == "complete" and resumed.processed == 0
    assert attempts == 2
    assert not any(event in {"verify", "candidates"} for event, _ in journal.events)


async def test_batch_bound_is_causal_when_only_25_limit_changes_to_26(monkeypatch):
    import ast
    import inspect
    import textwrap

    original = AnswerReleaseBackfill.run
    tree = ast.parse(textwrap.dedent(inspect.getsource(original)))
    changed = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare) and ast.unparse(node) == "processed < 25":
            node.comparators[0] = ast.Constant(value=26)
            changed += 1
    assert changed == 1
    namespace = dict(original.__globals__)
    exec(compile(ast.fix_missing_locations(tree), "<controlled-backfill-limit-mutation>", "exec"), namespace)

    async def assert_bounded():
        journal = Journal(30)
        report = await AnswerReleaseBackfill(journal.unit).run("job")
        assert report.processed <= 25 and journal.remaining >= 5, "batch exceeded 25 releases"

    await assert_bounded()
    with monkeypatch.context() as mutation:
        mutation.setattr(AnswerReleaseBackfill, "run", namespace[original.__name__])
        with pytest.raises(AssertionError, match="batch exceeded 25 releases"):
            await assert_bounded()
    await assert_bounded()
