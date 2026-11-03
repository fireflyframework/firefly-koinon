# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0

from collections.abc import Sequence

import pytest

from flycanon.core.services.query.rlm.corpus import CanonCorpusBuilder, Filters

from .test_corpus import FakeKnowledgeRepository, FakeObjectStore, FakeSourceRepository, _row


class CountedIds(Sequence):
    def __init__(self, values):
        self.values, self.visits = values, 0

    def __len__(self):
        return len(self.values)

    def __getitem__(self, index):
        self.visits += 1
        return self.values[index]


class SelectedSources(FakeSourceRepository):
    def __init__(self, rows):
        super().__init__(rows)
        self.batches = []

    async def list_sources(self, **kwargs):
        raise AssertionError("A selected-source query must not enumerate the workspace")

    async def get_many_scoped(self, source_ids, **kwargs):
        self.batches.append(tuple(source_ids))
        return await super().get_many_scoped(source_ids, **kwargs)


@pytest.mark.asyncio
async def test_selected_corpus_batches_every_admitted_id_without_workspace_enumeration():
    rows = [_row(f"s{number:04d}", filename=f"doc{number}.txt") for number in range(601)]
    rows.append(_row("unselected", filename="hidden.txt"))
    repository = SelectedSources(rows)
    store = FakeObjectStore({})
    builder = CanonCorpusBuilder(
        source_repository=repository, knowledge_repository=FakeKnowledgeRepository(), object_store=store
    )
    identifiers = CountedIds([row.id for row in rows[:-1]] * 2)
    corpus = await builder.build(tenant_id="t1", workspace_id="w1", filters=Filters(source_ids=identifiers))
    assert len(corpus) == 601
    assert len(repository.batches) == 4
    assert max(map(len, repository.batches)) <= 200
    assert len({value for batch in repository.batches for value in batch}) == 601
    assert identifiers.visits <= 3 * len(identifiers)
    assert "hidden" not in corpus
    assert store.sync_gets == []


@pytest.mark.asyncio
async def test_filters_are_prepared_once_instead_of_rebuilt_for_every_source():
    rows = [_row(f"s{number}", filename=f"doc{number}.txt") for number in range(300)]
    identifiers = CountedIds([row.id for row in rows])
    builder = CanonCorpusBuilder(
        source_repository=FakeSourceRepository(rows),
        knowledge_repository=FakeKnowledgeRepository(),
        object_store=FakeObjectStore({}),
    )
    result = await builder.build(tenant_id="t1", workspace_id="w1", filters=Filters(source_ids=identifiers))
    assert len(result) == 300
    assert identifiers.visits <= 3 * len(identifiers)


@pytest.mark.asyncio
async def test_empty_knowledge_resolution_never_becomes_unrestricted_source_selection():
    repository = SelectedSources([_row("s1")])
    builder = CanonCorpusBuilder(
        source_repository=repository,
        knowledge_repository=FakeKnowledgeRepository(),
        object_store=FakeObjectStore({}),
    )
    result = await builder.build(
        tenant_id="t1", workspace_id="w1", filters=Filters(knowledge_item_ids=["no-citations"])
    )
    assert len(result) == 0
    assert repository.batches == []


@pytest.mark.asyncio
async def test_selected_repository_read_keeps_scope_status_and_empty_selection(repositories, engine):
    from sqlalchemy import event

    repository = repositories["source"]
    for identifier, tenant, workspace, status in (
        ("allowed", "t1", "w1", "ready"),
        ("foreign-tenant", "t2", "w1", "ready"),
        ("foreign-workspace", "t1", "w2", "ready"),
        ("unfinished", "t1", "w1", "pending"),
    ):
        row = _row(identifier, status=status, content_sha256=identifier)
        row.tenant_id, row.workspace_id = tenant, workspace
        await repository.add(row)
    statements = []

    def observed(_conn, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement)

    event.listen(engine.sync_engine, "before_cursor_execute", observed)
    try:
        rows = await repository.get_many_scoped(
            ["allowed", "foreign-tenant", "foreign-workspace", "unfinished", "absent"],
            tenant_id="t1",
            workspace_id="w1",
            statuses=["ready"],
        )
        assert [row.id for row in rows] == ["allowed"]
        assert len(statements) == 1
        assert "count(" not in statements[0].lower()
        assert "offset" not in statements[0].lower()
        assert await repository.get_many_scoped([], tenant_id="t1", workspace_id="w1") == []
        assert len(statements) == 1
        with pytest.raises(ValueError):
            await repository.get_many_scoped([str(i) for i in range(201)], tenant_id="t1", workspace_id="w1")
        assert len(statements) == 1
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", observed)


@pytest.mark.asyncio
async def test_duplicate_filenames_do_not_repeat_all_previous_suffix_probes(monkeypatch):
    from flycanon.core.services.query.rlm import corpus as module

    class CountedSet(set):
        probes = 0

        def __contains__(self, value):
            type(self).probes += 1
            return super().__contains__(value)

    monkeypatch.setattr(module, "set", CountedSet, raising=False)
    rows = [_row(f"s{i}", filename="report.txt") for i in range(1000)]
    rows.insert(0, _row("literal", filename="report#2.txt"))
    builder = CanonCorpusBuilder(
        source_repository=FakeSourceRepository(rows),
        knowledge_repository=FakeKnowledgeRepository(),
        object_store=FakeObjectStore({}),
    )
    corpus = await builder.build(tenant_id="t1", workspace_id="w1")
    assert len(corpus) == len(rows)
    assert corpus.resolve("report#2").source_id == "literal"
    assert corpus.resolve("report#3").source_id == "s1"
    assert CountedSet.probes <= 4 * len(rows)


@pytest.mark.asyncio
async def test_selected_source_order_is_utc_stable_across_batches_and_host_timezones(monkeypatch):
    import os
    import time
    from datetime import UTC, datetime

    if not hasattr(time, "tzset"):
        pytest.skip("Host timezone changes require tzset")
    rows = [_row(f"s{i:04d}", filename="report.txt") for i in range(202)]
    for row in rows:
        row.created_at = datetime(2026, 3, 8, 2, 30)
    rows[0].created_at = datetime(2026, 3, 8, 3)
    rows[-1].created_at = datetime(2026, 3, 8, 3, tzinfo=UTC)
    builder = CanonCorpusBuilder(
        source_repository=SelectedSources(rows),
        knowledge_repository=FakeKnowledgeRepository(),
        object_store=FakeObjectStore({}),
    )
    previous = os.environ.get("TZ")
    try:
        for zone in ("UTC", "America/New_York"):
            monkeypatch.setenv("TZ", zone)
            time.tzset()
            corpus = await builder.build(
                tenant_id="t1", workspace_id="w1", filters=Filters(source_ids=[row.id for row in rows])
            )
            assert corpus.resolve("report").source_id == "s0201"
            assert corpus.resolve("report#2").source_id == "s0000"
            assert corpus.resolve("report#3").source_id == "s0200"
    finally:
        if previous is None:
            monkeypatch.delenv("TZ", raising=False)
        else:
            monkeypatch.setenv("TZ", previous)
        time.tzset()
