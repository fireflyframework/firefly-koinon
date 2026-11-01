# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime

from koinon.activity.knowledge_values import KnowledgeActivity, KnowledgeObservation, summarize_knowledge


def test_unique_pieces_not_chunks_or_repeated_reads_are_counted_per_period_and_day():
    first = datetime(2026, 10, 25, 23, 30, tzinfo=UTC)
    second = datetime(2026, 10, 26, 23, 30, tzinfo=UTC)
    values = [
        KnowledgeObservation("document", "created", first),
        KnowledgeObservation("document", "consulted", first),
        KnowledgeObservation("document", "consulted", first),
        KnowledgeObservation("document", "consulted", second),
        KnowledgeObservation("dataset", "updated", second),
    ]
    summary = summarize_knowledge(values, time_zone="Europe/Madrid", partial=False)
    assert summary.counts.created.value == 1
    assert summary.counts.updated.value == 1
    assert summary.counts.consulted.value == 1
    assert list(summary.daily) == ["2026-10-26", "2026-10-27"]
    assert summary.daily["2026-10-26"].consulted.value == 1
    assert summary.daily["2026-10-27"].consulted.value == 1


def test_lower_bound_is_explicit_and_empty_observed_history_can_be_zero():
    summary = summarize_knowledge([], time_zone="UTC", partial=True)
    assert isinstance(summary, KnowledgeActivity)
    assert summary.counts.created.value == 0
    assert summary.counts.created.status == "partial"
    assert summary.counts.created.reason == "bounded_history"
    complete = summarize_knowledge([], time_zone="UTC", partial=False)
    assert complete.counts.created.status == "observed"
