# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from decimal import Decimal
from hashlib import sha256

import pytest


def test_nested_parquet_preserves_top_level_schema_and_exact_record_field_origins(tmp_path):
    import pyarrow as pa
    import pyarrow.parquet as pq

    from flyquery.core.services.ingestion.readers.parquet_reader import ParquetReader

    table = pa.table({"id": [1, 2], "payload": [{"amount": Decimal("47.00")}, {"amount": Decimal("99.00")}]})
    source, target = tmp_path / "nested.parquet", tmp_path / "snapshot.parquet"
    pq.write_table(table, source, row_group_size=1)
    result = ParquetReader._materialise_sync(str(source), str(target))
    assert [column.name for column in result.columns] == ["id", "payload"]
    assert pq.read_table(target).to_pylist() == table.to_pylist()
    mapping = result.coordinates
    assert mapping.complete and mapping.source_format == "parquet" and mapping.source_variant == "parquet"
    assert mapping.input_sha256 == sha256(source.read_bytes()).hexdigest()
    assert [(span.output_start, span.count, span.source_start) for span in mapping.row_ranges] == [(0, 2, 0)]
    assert [
        (column.output_position, column.source_field_index, column.source_path) for column in mapping.columns
    ] == [(0, 0, ("id",)), (1, 1, ("payload",))]
    assert dict(mapping.dependencies)["pyarrow"] == pa.__version__
    assert len(mapping.digest()) == 64


def test_coordinate_coverage_never_promotes_gaps_or_duplicate_columns():
    from flyquery.core.services.ingestion.coordinates import (
        ColumnOrigin,
        MaterializationCoordinates,
        RowRange,
    )

    with pytest.raises(ValueError, match="cover"):
        MaterializationCoordinates(
            "parquet",
            "parquet",
            "record",
            "a" * 64,
            3,
            1,
            (RowRange(0, 1, 0), RowRange(2, 1, 2)),
            (ColumnOrigin(0, 0, ("id",)),),
        )
    with pytest.raises(ValueError, match="column"):
        MaterializationCoordinates(
            "parquet",
            "parquet",
            "record",
            "a" * 64,
            1,
            2,
            (RowRange(0, 1, 0),),
            (ColumnOrigin(0, 0, ("id",)), ColumnOrigin(0, 1, ("other",))),
        )


def test_nested_parquet_schema_uses_top_level_fields_without_changing_bytes(tmp_path):
    import pyarrow as pa
    import pyarrow.parquet as pq

    from flyquery.core.services.ingestion.reader import TableExtractionRules
    from flyquery.core.services.ingestion.readers.parquet_reader import ParquetReader

    table = pa.table({"id": [1], "payload": [{"amount": Decimal("47.00"), "unit": "USD"}]})
    source, target = tmp_path / "original.parquet", tmp_path / "copy.parquet"
    pq.write_table(table, source)
    enumerated = ParquetReader._enumerate_sync(str(source))
    assert enumerated[0].n_columns == 2
    result = ParquetReader._materialise_sync(str(source), str(target))
    assert [column.name for column in result.columns] == ["id", "payload"]
    assert "struct" in result.columns[1].data_type
    assert source.read_bytes() == target.read_bytes()


@pytest.mark.parametrize("variant", ["arrow_stream", "arrow_file", "orc", "avro"])
def test_ordered_binary_readers_emit_actual_record_origins_without_changing_values(tmp_path, variant):
    import pyarrow as pa
    import pyarrow.parquet as pq

    schema = pa.schema(
        [
            pa.field("id", pa.int64()),
            pa.field("payload", pa.struct([pa.field("amount", pa.decimal128(20, 2))])),
        ]
    )
    records = [{"id": 1, "payload": {"amount": Decimal("47.00")}}, {"id": 2, "payload": None}]
    table = pa.Table.from_pylist(records, schema=schema)
    target = tmp_path / "result.parquet"
    if variant.startswith("arrow"):
        import pyarrow.ipc as ipc

        source = tmp_path / "input.arrow"
        with (
            pa.OSFile(str(source), "wb") as stream,
            (
                ipc.new_stream(stream, schema) if variant == "arrow_stream" else ipc.new_file(stream, schema)
            ) as writer,
        ):
            writer.write_table(table)
        from flyquery.core.services.ingestion.readers.arrow_reader import ArrowReader

        reader = ArrowReader
    elif variant == "orc":
        import pyarrow.orc as orc

        source = tmp_path / "input.orc"
        orc.write_table(table, source)
        from flyquery.core.services.ingestion.readers.orc_reader import OrcReader

        reader = OrcReader
    else:
        import fastavro

        source = tmp_path / "input.avro"
        avro_schema = {
            "type": "record",
            "name": "Row",
            "fields": [
                {"name": "id", "type": "long"},
                {
                    "name": "payload",
                    "type": [
                        "null",
                        {
                            "type": "record",
                            "name": "Payload",
                            "fields": [
                                {
                                    "name": "amount",
                                    "type": {
                                        "type": "bytes",
                                        "logicalType": "decimal",
                                        "precision": 20,
                                        "scale": 2,
                                    },
                                }
                            ],
                        },
                    ],
                    "default": None,
                },
            ],
        }
        with source.open("wb") as stream:
            fastavro.writer(stream, avro_schema, records)
        from flyquery.core.services.ingestion.readers.avro_reader import AvroReader

        reader = AvroReader
    result = reader._materialise_sync(str(source), str(target))
    assert pq.read_table(target).to_pylist() == records
    coordinates = result.coordinates
    assert coordinates.complete and coordinates.row_count == 2 and coordinates.column_count == 2
    assert coordinates.input_sha256 == sha256(source.read_bytes()).hexdigest()
    assert coordinates.source_variant == {
        "arrow_stream": "arrow_ipc_stream",
        "arrow_file": "arrow_ipc_file",
    }.get(variant, variant)
    assert [
        (column.output_position, column.source_field_index, column.source_path)
        for column in coordinates.columns
    ] == [(0, 0, ("id",)), (1, 1, ("payload",))]


async def test_period_header_rename_preserves_emitted_source_coordinates(tmp_path):
    from types import SimpleNamespace

    import pyarrow as pa
    import pyarrow.parquet as pq

    from flyquery.core.services.ingestion.readers.parquet_reader import ParquetReader
    from flyquery.core.services.ingestion.stages import parse

    source, target = tmp_path / "original.parquet", tmp_path / "rewritten.parquet"
    pq.write_table(pa.table({"2024": [47, 99], "item": ["A", "B"]}), source, row_group_size=1)
    materialized = ParquetReader._materialise_sync(str(source), str(target))
    original_digest = materialized.coordinates.digest()
    renamed = await parse._propose_meaningful_column_names(
        section_label="Records",
        mat_result=materialized,
        parquet_path=str(target),
        settings=SimpleNamespace(),
        logger_=parse.logger,
    )
    assert [column.name for column in renamed.columns] == ["year_2024", "item"]
    assert renamed.coordinates is not None and renamed.coordinates.digest() == original_digest
    assert renamed.coordinates.columns[0].source_path == ("2024",)
    assert pq.read_table(target).to_pylist() == [
        {"year_2024": 47, "item": "A"},
        {"year_2024": 99, "item": "B"},
    ]


async def test_period_rename_preserves_quoted_source_field_names_and_data(tmp_path):
    from types import SimpleNamespace

    import pyarrow as pa
    import pyarrow.parquet as pq

    from flyquery.core.services.ingestion.readers.parquet_reader import ParquetReader
    from flyquery.core.services.ingestion.stages import parse

    source, target = tmp_path / "quoted.parquet", tmp_path / "renamed.parquet"
    pq.write_table(pa.table({"2024": [47], 'item "label"': ["A"]}), source)
    materialized = ParquetReader._materialise_sync(str(source), str(target))
    result = await parse._propose_meaningful_column_names(
        section_label="Records",
        mat_result=materialized,
        parquet_path=str(target),
        settings=SimpleNamespace(),
        logger_=parse.logger,
    )
    assert pq.read_table(target).to_pylist() == [{"year_2024": 47, 'item "label"': "A"}]
    assert result.coordinates.columns[1].source_path == ('item "label"',)


@pytest.mark.parametrize("variant", ["array", "named", "jsonl", "object", "scalar_array"])
def test_json_coordinates_follow_actual_selected_branch_and_nested_fields(tmp_path, variant):
    import json

    import pyarrow.parquet as pq

    from flyquery.core.services.ingestion.reader import ProposedTable
    from flyquery.core.services.ingestion.readers.json_reader import JsonReader

    rows = [{"id": 47, "nested": {"value": "a/b"}}, {"id": 99, "nested": None}]
    source = tmp_path / ("source.jsonl" if variant == "jsonl" else "source.json")
    values = {"array": rows, "named": {"a/b": rows}, "object": rows[0], "scalar_array": [47, 99]}
    source.write_text(
        "\n".join(json.dumps(row) for row in rows) if variant == "jsonl" else json.dumps(values[variant])
    )
    result = JsonReader._materialise_sync(
        str(source),
        ProposedTable("source", "a/b" if variant == "named" else None, 0, 0),
        str(tmp_path / "out.parquet"),
        20480,
    )
    actual = pq.read_table(result.target_parquet_key).to_pylist()
    mapping = result.coordinates
    assert mapping is not None and mapping.complete
    assert mapping.input_sha256 == sha256(source.read_bytes()).hexdigest()
    assert mapping.row_count == len(actual) == (1 if variant == "object" else 2)
    assert mapping.source_path == (("a/b",) if variant == "named" else ())
    assert (
        mapping.row_kind
        == {
            "array": "json_array",
            "named": "json_array",
            "jsonl": "jsonl_record",
            "object": "single_object",
            "scalar_array": "json_array",
        }[variant]
    )
    assert mapping.columns[0].source_path == (() if variant == "scalar_array" else ("id",))


@pytest.mark.parametrize("locale", ["en-US", "en-GB"])
def test_csv_multiline_record_mapping_uses_observed_header_and_date_parser(tmp_path, locale):
    import pyarrow.parquet as pq

    from flyquery.core.services.ingestion.readers.csv_reader import CsvReader

    source = tmp_path / "source.csv"
    source.write_text('id;note;day\n47;"first\nsecond";01/02/2026\n99;last;03/04/2026\n')
    result = CsvReader._materialise_sync(str(source), str(tmp_path / "result.parquet"), locale, 20480)
    assert pq.read_table(result.target_parquet_key).to_pylist()[0]["note"] == "first\nsecond"
    mapping = result.coordinates
    assert mapping is not None and mapping.complete
    assert mapping.row_kind == "record" and mapping.index_base == 0
    assert [(r.output_start, r.count, r.source_start) for r in mapping.row_ranges] == [(0, 2, 1)]
    assert dict(mapping.parser_decisions)["delimiter"] == ";"
    assert dict(mapping.parser_decisions)["header"] is True
    assert dict(mapping.parser_decisions)["date_format"] == "%d/%m/%Y"
    assert pq.read_table(result.target_parquet_key).to_pylist()[0]["day"].day == 1


def test_xlsx_sparse_absolute_sheet_coordinates_and_inherited_header(tmp_path):
    import pyarrow.parquet as pq
    from openpyxl import Workbook

    from flyquery.core.services.ingestion.reader import ProposedTable
    from flyquery.core.services.ingestion.readers.excel_reader import ExcelReader

    source = tmp_path / "source.xlsx"
    wb = Workbook()
    sheet = wb.active
    sheet.title = "Facts"
    for cell, value in {"D4": "Item", "G4": "Amount", "D7": "A", "G7": 47, "D8": "B", "G8": 99}.items():
        sheet[cell] = value
    wb.save(source)
    result = ExcelReader._materialise_sync(
        str(source),
        ProposedTable("Facts", "Facts#section[0:3:5]", 2, 2),
        str(tmp_path / "out.parquet"),
        "en-US",
        20480,
        3,
    )
    assert pq.read_table(result.target_parquet_key).to_pylist() == [
        {"Item": "A", "Amount": 47},
        {"Item": "B", "Amount": 99},
    ]
    mapping = result.coordinates
    assert mapping is not None and mapping.complete and mapping.source_sheet == "Facts"
    assert [(r.output_start, r.count, r.source_start) for r in mapping.row_ranges] == [(0, 2, 6)]
    assert [(c.source_field_index, c.header_cells) for c in mapping.columns] == [
        (3, ((3, 3),)),
        (6, ((3, 6),)),
    ]
    assert dict(mapping.parser_decisions)["newline_normalization"] == "crlf_to_space"
    from importlib.metadata import version

    assert dict(mapping.dependencies)["python-calamine"] == version("python-calamine")


def test_delimited_receipt_excludes_actual_same_scan_rejection_without_shifting_origins(tmp_path):
    import duckdb
    import pyarrow.parquet as pq

    from flyquery.core.services.ingestion.readers.delimited import materialize

    source = tmp_path / "input.csv"
    source.write_text("id,value\n" + "".join(f"{i},{'bad' if i == 4000 else i}\n" for i in range(5000)))
    conn = duckdb.connect()
    try:
        receipt = materialize(conn, str(source), str(tmp_path / "out.parquet"), sample_rows=2048, excel=True)
    finally:
        conn.close()
    assert receipt.complete
    assert dict(receipt.decisions)["rejected_lines"] == 1
    assert 4001 not in receipt.record_indices
    assert receipt.record_indices[3999:4002] == (4000, 4002, 4003)
    assert pq.read_table(tmp_path / "out.parquet").num_rows == 4999


def test_csv_duplicate_header_paths_preserve_original_names_and_field_positions(tmp_path):
    from flyquery.core.services.ingestion.readers.csv_reader import CsvReader

    source = tmp_path / "source.csv"
    source.write_text("amount,amount\n47,99\n")
    result = CsvReader._materialise_sync(str(source), str(tmp_path / "out.parquet"), "en-US", 20480)
    assert [column.name for column in result.columns] == ["amount", "amount_1"]
    assert [column.source_path for column in result.coordinates.columns] == [("amount",), ("amount",)]
    assert [column.source_field_index for column in result.coordinates.columns] == [0, 1]


def test_sheet_coordinate_receipt_retains_actual_rejected_absolute_rows(tmp_path):
    from openpyxl import Workbook

    from flyquery.core.services.ingestion.reader import ProposedTable
    from flyquery.core.services.ingestion.readers.excel_reader import ExcelReader

    source = tmp_path / "rejected.xlsx"
    book = Workbook()
    sheet = book.active
    sheet.title = "Facts"
    sheet.append(["id", "value"])
    for i in range(5000):
        sheet.append([i, "bad" if i == 4000 else i])
    book.save(source)
    result = ExcelReader._materialise_sync(
        str(source),
        ProposedTable("Facts", "Facts#section[0:5001]", 2, 5000),
        str(tmp_path / "out.parquet"),
        "en-US",
        2048,
        3,
    )
    assert result.n_rows_actual == 4999
    assert result.coordinates.complete
    assert result.coordinates.rejected_source_rows == (4001,)


def test_json_object_keys_are_paths_not_invented_per_record_field_ordinals(tmp_path):
    from flyquery.core.services.ingestion.reader import ProposedTable
    from flyquery.core.services.ingestion.readers.json_reader import JsonReader

    source = tmp_path / "object.json"
    source.write_text('[{"a":47,"b":99},{"b":12,"a":31}]')
    result = JsonReader._materialise_sync(
        str(source), ProposedTable("records", None, 2, 2), str(tmp_path / "out.parquet"), 20480
    )
    assert result.coordinates.complete
    assert [
        (column.source_field_index, column.source_path, column.source_type)
        for column in result.coordinates.columns
    ] == [(None, ("a",), None), (None, ("b",), None)]


def test_csv_skipped_preamble_keeps_original_record_indices(tmp_path):
    import pyarrow.parquet as pq

    from flyquery.core.services.ingestion.readers.csv_reader import CsvReader

    source = tmp_path / "source.csv"
    source.write_text("report metadata\nid,value\n47,one\n99,two\n")
    result = CsvReader._materialise_sync(str(source), str(tmp_path / "out.parquet"), "en-US", 20480)
    assert result.coordinates.complete
    assert dict(result.coordinates.parser_decisions)["skip_rows"] == 1
    assert result.coordinates.row_ranges[0].source_start == 2
    assert pq.read_table(result.target_parquet_key).to_pylist() == [
        {"id": 47, "value": "one"},
        {"id": 99, "value": "two"},
    ]
