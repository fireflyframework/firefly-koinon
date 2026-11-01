# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Ingestion SQL and scratch have their own resource policy, independent of queries."""

from types import SimpleNamespace

import pytest


def settings(tmp_path, **overrides):
    return SimpleNamespace(
        **{
            "ingest_duckdb_memory_limit": "64MiB",
            "ingest_duckdb_threads": 1,
            "ingest_scratch_max_bytes": 1024 * 1024,
            "ingest_decompressed_max_bytes": 512 * 1024,
            "ingest_native_connections": 1,
            "ingest_scratch_root": str(tmp_path),
            **overrides,
        }
    )


def test_native_connection_enforces_actual_memory_threads_spill_and_process_admission(tmp_path):
    from flyquery.core.services.ingestion.resources import (
        IngestionResourceLimitError,
        connect,
        resource_scope,
    )

    with resource_scope(settings(tmp_path)):
        first = connect()
        try:
            memory, threads = first.execute(
                "SELECT current_setting('memory_limit'), current_setting('threads')"
            ).fetchone()
            assert memory == "64.0 MiB" and threads == 1
            with pytest.raises(IngestionResourceLimitError) as capacity:
                connect()
            assert capacity.value.code == "INGEST_RESOURCE_LIMIT"
        finally:
            first.close()
        second = connect()
        second.close()


def test_actual_duckdb_exhaustion_is_explicit_and_never_runs_an_unbounded_fallback(tmp_path):
    from flyquery.core.services.ingestion.resources import (
        IngestionResourceLimitError,
        connect,
        resource_scope,
    )

    with resource_scope(settings(tmp_path, ingest_duckdb_memory_limit="1MiB")):
        connection = connect()
        try:
            with pytest.raises(IngestionResourceLimitError) as exhausted:
                connection.execute(
                    "CREATE TABLE bounded AS SELECT i, md5(i::VARCHAR) AS text "
                    "FROM range(100000) AS source(i) ORDER BY text"
                )
            assert exhausted.value.code == "INGEST_RESOURCE_LIMIT"
        finally:
            connection.close()


async def test_configured_decompression_cap_rejects_before_writing_the_excess(tmp_path):
    import gzip

    from flyquery.core.services.ingestion.compression import decompress_to_temp
    from flyquery.core.services.ingestion.resources import IngestionResourceLimitError, resource_scope

    source = tmp_path / "bounded.csv.gz"
    original = gzip.compress(b"x" * 4096)
    source.write_bytes(original)
    with (
        resource_scope(settings(tmp_path, ingest_decompressed_max_bytes=1024)),
        pytest.raises(IngestionResourceLimitError),
    ):
        await decompress_to_temp(str(source), "gz")
    assert source.exists() and source.read_bytes() == original


async def test_csv_and_xlsx_native_connections_apply_policy_without_losing_rows(tmp_path, monkeypatch):
    from uuid import uuid4

    import duckdb
    import openpyxl
    import pyarrow as arrow
    import pyarrow.parquet as parquet

    from flyquery.core.services.ingestion.reader import TableExtractionRules
    from flyquery.core.services.ingestion.readers.csv_reader import CsvReader
    from flyquery.core.services.ingestion.readers.excel_reader import ExcelReader
    from flyquery.core.services.ingestion.readers.json_reader import JsonReader
    from flyquery.core.services.ingestion.resources import account_path, resource_scope
    from flyquery.core.services.ingestion.stages import parse, profile, sample

    observed = []
    original = duckdb.connect

    def inspect(*args, **kwargs):
        connection = original(*args, **kwargs)
        observed.append(
            connection.execute(
                "SELECT current_setting('memory_limit'), current_setting('threads')"
            ).fetchone()
        )
        return connection

    monkeypatch.setattr(duckdb, "connect", inspect)
    csv = tmp_path / "source.csv"
    csv.write_text("name,amount\nNorth,47\nSouth,99\n")
    workbook = openpyxl.Workbook()
    for row in (("name", "amount"), ("North", 47), ("South", 99)):
        workbook.active.append(row)
    xlsx = tmp_path / "source.xlsx"
    workbook.save(xlsx)
    json = tmp_path / "source.json"
    json.write_text('[{"name":"North","amount":47},{"name":"South","amount":99}]')
    with resource_scope(settings(tmp_path)):
        for reader, source in ((CsvReader(), csv), (ExcelReader(), xlsx), (JsonReader(), json)):
            tables = await reader.enumerate_tables(str(source), TableExtractionRules())
            target = tmp_path / (source.suffix[1:] + ".parquet")
            result = await reader.materialise(
                str(source), tables[0], str(target), workspace_locale="en-US", type_infer_sample_rows=32
            )
            assert result.n_rows_actual == 2
            if isinstance(reader, ExcelReader):
                decisions = dict(result.coordinates.parser_decisions)
                assert decisions["duckdb_memory_limit"] == "64.0 MiB"
                assert decisions["duckdb_threads"] == 1
            assert parquet.read_table(target).to_pylist() == [
                {"name": "North", "amount": 47},
                {"name": "South", "amount": 99},
            ]
        await parse._rename_parquet_columns(
            parquet_path=str(target), current_columns=["name", "amount"], proposed_columns=["name", "amount"]
        )
        assert await parse._read_parquet_sample(str(target), 2) == (
            ["name", "amount"],
            [["North", "South"], [47, 99]],
        )
        assert profile._profile_column_sync(str(target), "amount", "BIGINT", 2)["n_rows"] == 2
        organization = tmp_path / "organization.parquet"
        parquet.write_table(
            arrow.table(
                {
                    "person": [f"person-{i}" for i in range(100)],
                    "manager": [f"person-{i % 3}" for i in range(100)],
                }
            ),
            organization,
        )
        account_path(organization)
        assert profile._detect_self_references(
            str(organization),
            {
                "person": (uuid4(), "VARCHAR", {"distinct_estimate": 100}),
                "manager": (uuid4(), "VARCHAR", {"distinct_estimate": 3}),
            },
            100,
        ) == {"manager": "person"}
        assert sample._read_parquet_column(str(organization), "person", 2) == ["person-0", "person-1"]
    assert len(observed) == 8  # Excel owns its ninth native connection in the bounded child.
    assert all(row == ("64.0 MiB", 1) for row in observed)


def test_owned_native_output_excess_fails_before_it_can_become_a_successful_artifact(tmp_path):
    from flyquery.core.services.ingestion.resources import (
        IngestionResourceLimitError,
        account_path,
        connect,
        resource_scope,
    )

    output = tmp_path / "owned.parquet"
    with resource_scope(settings(tmp_path, ingest_scratch_max_bytes=1024, ingest_decompressed_max_bytes=512)):
        account_path(output)
        connection = connect()
        try:
            with pytest.raises(IngestionResourceLimitError):
                connection.execute(
                    "COPY (SELECT i, md5(i::VARCHAR) AS text FROM range(1000) AS src(i)) "
                    f"TO '{output}' (FORMAT PARQUET, USE_TMP_FILE false)"
                )
        finally:
            connection.close()


async def test_nested_stages_share_one_scratch_budget_and_never_reset_it(tmp_path):
    from flyquery.core.services.ingestion.resources import (
        IngestionResourceLimitError,
        ingestion_resources,
        resource_scope,
        write_bytes,
    )

    @ingestion_resources
    async def next_stage(*, settings):
        write_bytes(tmp_path / "second.bin", b"b" * 600)

    with resource_scope(settings(tmp_path, ingest_scratch_max_bytes=1024, ingest_decompressed_max_bytes=512)):
        write_bytes(tmp_path / "first.bin", b"a" * 600)
        with pytest.raises(IngestionResourceLimitError):
            await next_stage(settings=settings(tmp_path))
    assert (tmp_path / "first.bin").read_bytes() == b"a" * 600
    assert not (tmp_path / "second.bin").exists()


def test_profile_cannot_hide_native_resource_exhaustion_as_missing_statistics(tmp_path):
    from flyquery.core.services.ingestion.resources import (
        IngestionResourceLimitError,
        connect,
        resource_scope,
    )
    from flyquery.core.services.ingestion.stages.profile import _profile_column_sync

    with resource_scope(settings(tmp_path)):
        connection = connect()
        try:
            with pytest.raises(IngestionResourceLimitError):
                _profile_column_sync(str(tmp_path / "not-opened.parquet"), "amount", "BIGINT", 2)
        finally:
            connection.close()


@pytest.mark.parametrize(
    "values",
    [
        {"ingest_duckdb_threads": True},
        {"ingest_native_connections": 0},
        {"ingest_duckdb_memory_limit": "999999GiB"},
        {"ingest_scratch_max_bytes": 1024, "ingest_decompressed_max_bytes": 2048},
    ],
)
def test_operator_resource_configuration_rejects_unbounded_or_inconsistent_values(values):
    from flyquery.config import FlyquerySettings

    with pytest.raises(ValueError):
        FlyquerySettings(_env_file=None, **values)
