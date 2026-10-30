# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""The immutable reader budgets UTF-8 payloads before materializing them."""

from contextlib import asynccontextmanager
from hashlib import sha256
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pyfly.kernel import ServiceUnavailableException
from sqlalchemy import insert, update
from test_document_rag_parts import SCOPE, selected
from test_source_lineage_admission import lineage as lineage

from flycanon.core.services.sources.lineage.ingestion_parts import chunk_records, validate_chunk
from flycanon.core.services.sources.lineage.whole_read import WholeDocumentReader
from flycanon.models.entities.source_lineage import source_events, source_extractions, source_parts


@pytest.fixture
async def bounded_parts(lineage, repositories, monkeypatch):
    _, source, head, _, _ = await selected(lineage, repositories)
    first = dict((await lineage.parts(SCOPE, source.id, head["extraction_id"], kind="chunk")).items[0])
    second_id = str(uuid4())
    async with lineage.sources.session() as session:
        await session.execute(
            update(source_extractions)
            .where(
                source_extractions.c.id == head["extraction_id"],
            )
            .values(projection={})
        )
        await session.execute(
            update(source_parts)
            .where(source_parts.c.id == first["parent_id"])
            .values(
                text="éé",
                sha256=sha256("éé".encode()).hexdigest(),
            )
        )
        await session.execute(
            update(source_parts)
            .where(source_parts.c.id == first["id"])
            .values(
                text="éé",
                sha256=sha256("éé".encode()).hexdigest(),
                section_path=None,
            )
        )
        await session.execute(
            insert(source_parts).values(
                **{
                    **first,
                    "id": second_id,
                    "projection_chunk_id": "second-projection",
                    "ordinal": 99,
                    "text": "é",
                    "sha256": sha256("é".encode()).hexdigest(),
                    "section_path": None,
                }
            )
        )
    reads = []
    session_factory = lineage.sources.session

    @asynccontextmanager
    async def traced_session():
        async with session_factory() as session:

            class TracedSession:
                def __getattr__(self, name):
                    return getattr(session, name)

                async def execute(self, statement, *args, **kwargs):
                    result = await session.execute(statement, *args, **kwargs)
                    columns = {column.key for column in getattr(statement, "selected_columns", ())}
                    if columns & {"text", "parent_text"}:
                        rows = result.mappings().all()
                        reads.extend(dict(row) for row in rows)
                        return SimpleNamespace(mappings=lambda: SimpleNamespace(all=lambda: rows))
                    return result

            yield TracedSession()

    monkeypatch.setattr(lineage.sources, "session", traced_session)
    return SimpleNamespace(
        lineage=lineage,
        source=source,
        head=head,
        parent=first["parent_id"],
        ids=(first["id"], second_id),
        reads=reads,
    )


async def test_utf8_aggregate_bound_rejects_before_fetching_any_text(bounded_parts):
    value = bounded_parts
    # Child text 4+2, shared parent4, two JSON null paths4+4, one JSON projection2 =20 bytes.
    with pytest.raises(ServiceUnavailableException):
        await chunk_records(value.lineage, SCOPE, source_parts.c.id.in_(value.ids), max_bytes=19)
    assert value.reads == []


async def test_shared_parent_is_fetched_once_and_not_charged_per_child(bounded_parts):
    value = bounded_parts
    rows = await chunk_records(value.lineage, SCOPE, source_parts.c.id.in_(value.ids))
    assert {row["id"] for row in rows} == set(value.ids)
    for row in rows:
        validate_chunk(row)
    parent_bytes = sum(
        len(row["parent_text"].encode())
        if row.get("parent_text")
        else len(row["text"].encode())
        if row.get("id") == value.parent
        else 0
        for row in value.reads
    )
    assert parent_bytes == 4
    assert rows[0]["parent_text"] is rows[1]["parent_text"]


async def test_exact_utf8_budget_accepts_unique_payloads(bounded_parts):
    value = bounded_parts
    rows = await chunk_records(value.lineage, SCOPE, source_parts.c.id.in_(value.ids), max_bytes=20)
    assert {row["id"] for row in rows} == set(value.ids)


async def test_join_duplicate_row_cap_is_checked_before_text_fetch(bounded_parts):
    value = bounded_parts
    async with value.lineage.sources.session() as session:
        await session.execute(
            insert(source_events).values(
                id=str(uuid4()),
                tenant_id="t",
                workspace_id="w",
                source_id=value.source.id,
                version_id=value.head["version_id"],
                extraction_id=value.head["extraction_id"],
                status="committed",
            )
        )
    with pytest.raises(ServiceUnavailableException):
        await chunk_records(value.lineage, SCOPE, source_parts.c.id == value.ids[0], max_rows=1)
    assert value.reads == []


async def test_cached_parent_still_rejects_corrupted_content(bounded_parts):
    value = bounded_parts
    async with value.lineage.sources.session() as session:
        await session.execute(update(source_parts).where(source_parts.c.id == value.parent).values(text="zz"))
    with pytest.raises(ServiceUnavailableException):
        for row in await chunk_records(value.lineage, SCOPE, source_parts.c.id.in_(value.ids)):
            validate_chunk(row)


async def test_exact_reader_propagates_aggregate_bound_before_payload_reads(bounded_parts):
    value = bounded_parts
    with pytest.raises(ServiceUnavailableException):
        await WholeDocumentReader(value.lineage, max_bytes=19).resolve_parts(
            SCOPE,
            source_id=value.source.id,
            source_version_id=value.head["version_id"],
            extraction_id=value.head["extraction_id"],
            part_ids=value.ids,
        )
    assert value.reads == []
