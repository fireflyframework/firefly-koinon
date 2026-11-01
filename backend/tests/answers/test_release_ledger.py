# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import pytest
from sqlalchemy import JSON, Column, MetaData, String, Table, create_engine, delete, update
from sqlalchemy.exc import IntegrityError


@pytest.fixture
def ledger(tmp_path):
    from koinon.answers.guards import release_guards

    engine = create_engine(f"sqlite:///{tmp_path / 'answer-ledger.db'}")
    table = Table(
        "koinon_chat_tool_results",
        MetaData(),
        Column("id", String, primary_key=True),
        Column("run_id", String, nullable=False),
        Column("kind", String, nullable=False),
        Column("payload", JSON, nullable=False),
    )
    table.metadata.create_all(engine)
    with engine.begin() as connection:
        for statement in release_guards("sqlite"):
            connection.exec_driver_sql(statement)
        connection.execute(
            table.insert(),
            [
                {
                    "id": "release",
                    "run_id": "run",
                    "kind": "answer_release",
                    "payload": {"generation_id": "generation", "release": {"text_sha256": "original"}},
                },
                {"id": "ordinary", "run_id": "run", "kind": "proposal", "payload": {"status": "pending"}},
            ],
        )
    yield engine, table
    engine.dispose()


@pytest.mark.parametrize(
    "values", [{"payload": {"forged": True}}, {"kind": "ordinary"}, {"id": "renamed"}, {"run_id": "other"}]
)
def test_existing_release_is_immutable_even_if_renamed_or_retargeted(ledger, values):
    engine, table = ledger
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(update(table).where(table.c.id == "release").values(**values))
    with engine.connect() as connection:
        row = connection.execute(table.select().where(table.c.id == "release")).mappings().one()
        assert row["kind"] == "answer_release" and row["payload"]["release"]["text_sha256"] == "original"


def test_delete_and_reclassifying_an_existing_tool_as_a_release_are_denied(ledger):
    engine, table = ledger
    for statement in (
        delete(table).where(table.c.id == "release"),
        update(table).where(table.c.id == "ordinary").values(kind="answer_release"),
    ):
        with pytest.raises(IntegrityError), engine.begin() as connection:
            connection.execute(statement)


@pytest.mark.parametrize("generation", ["generation", None])
def test_at_most_one_release_per_run_generation_including_no_generation(ledger, generation):
    engine, table = ledger
    if generation is None:
        with engine.begin() as connection:
            connection.execute(
                table.insert().values(
                    id="first-none", run_id="run", kind="answer_release", payload={"generation_id": None}
                )
            )
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(
            table.insert().values(
                id="duplicate", run_id="run", kind="answer_release", payload={"generation_id": generation}
            )
        )
    # A retry keeps the earlier receipt and can append a separately bound generation.
    with engine.begin() as connection:
        connection.execute(
            table.insert().values(
                id="retry", run_id="run", kind="answer_release", payload={"generation_id": "new-generation"}
            )
        )


def test_ordinary_proposal_updates_and_cleanup_still_work(ledger):
    engine, table = ledger
    with engine.begin() as connection:
        connection.execute(
            update(table).where(table.c.id == "ordinary").values(payload={"status": "applied"})
        )
        connection.execute(delete(table).where(table.c.id == "ordinary"))
    with engine.connect() as connection:
        assert [row.id for row in connection.execute(table.select())] == ["release"]
