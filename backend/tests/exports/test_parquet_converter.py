# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import csv
import io
import json
from decimal import Decimal

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from koinon.exports.data import convert_parquet


def parquet():
    table = pa.table(
        {
            "amount": pa.array(
                [Decimal("12345678901234567890.123400"), Decimal("-0.000100")], type=pa.decimal128(30, 6)
            ),
            "reference": ["=SUM(1,2)", "000123"],
        }
    )
    output = io.BytesIO()
    pq.write_table(table, output)
    return output.getvalue()


def test_jsonl_and_csv_keep_raw_decimal_precision_and_explicit_spreadsheet_transform():
    data = parquet()
    lines = convert_parquet(data, "jsonl", csv_mode="exact", max_bytes=100000).decode().splitlines()
    assert json.loads(lines[0])["amount"] == "12345678901234567890.123400"
    safe = list(
        csv.reader(
            io.StringIO(convert_parquet(data, "csv", csv_mode="spreadsheet_safe", max_bytes=100000).decode())
        )
    )
    exact = list(
        csv.reader(io.StringIO(convert_parquet(data, "csv", csv_mode="exact", max_bytes=100000).decode()))
    )
    assert safe[1][1] == "'=SUM(1,2)" and exact[1][1] == "=SUM(1,2)"
    assert exact[2][0] == "-0.000100" and exact[2][1] == "000123"


def test_output_and_decompressed_input_are_bounded_without_silent_truncation():
    with pytest.raises(ValueError, match="limit"):
        convert_parquet(parquet(), "jsonl", csv_mode="exact", max_bytes=10)
    table = pa.table({"text": ["x" * 10000] * 20})
    output = io.BytesIO()
    pq.write_table(table, output)
    with pytest.raises(ValueError, match="limit"):
        convert_parquet(output.getvalue(), "csv", csv_mode="exact", max_bytes=1000)


def test_empty_result_preserves_actual_column_headers_and_parquet_passthrough():
    output = io.BytesIO()
    pq.write_table(pa.table({"id": pa.array([], type=pa.int64())}), output)
    data = output.getvalue()
    assert convert_parquet(data, "jsonl", csv_mode="exact", max_bytes=10000) == b""
    assert convert_parquet(data, "csv", csv_mode="exact", max_bytes=10000) == b"id\r\n"
    assert convert_parquet(data, "parquet", csv_mode="exact", max_bytes=10000) == data


def test_jsonl_uses_portable_wire_strings_for_unsafe_integers_without_changing_booleans():
    output = io.BytesIO()
    pq.write_table(
        pa.table({"large": pa.array([2**63 - 1], type=pa.int64()), "small": [42], "enabled": [True]}), output
    )
    data = output.getvalue()
    row = json.loads(convert_parquet(data, "jsonl", csv_mode="exact", max_bytes=10000))
    assert row == {"large": str(2**63 - 1), "small": 42, "enabled": True}
    assert convert_parquet(data, "parquet", csv_mode="exact", max_bytes=10000) == data


def test_conversion_keeps_every_stored_row_beyond_the_preview_window_and_honors_cancellation():
    output = io.BytesIO()
    pq.write_table(pa.table({"id": list(range(137))}), output)
    data = output.getvalue()
    rows = [
        json.loads(line)
        for line in convert_parquet(data, "jsonl", csv_mode="exact", max_bytes=100000).splitlines()
    ]
    assert len(rows) == 137 and rows[-1] == {"id": 136}
    with pytest.raises(ValueError, match="execution limit"):
        convert_parquet(data, "csv", csv_mode="exact", max_bytes=100000, cancelled=lambda: True)


def test_spreadsheet_csv_escapes_only_formula_like_strings_and_preserves_numeric_negatives():
    output = io.BytesIO()
    pq.write_table(
        pa.table({"text": ["-3", " \t=1+1", "@SUM(A1)", "+123"], "number": [-3, -4, -5, -6]}), output
    )
    data = output.getvalue()
    safe = list(
        csv.DictReader(
            io.StringIO(convert_parquet(data, "csv", csv_mode="spreadsheet_safe", max_bytes=10000).decode())
        )
    )
    assert safe[0] == {"text": "'-3", "number": "-3"}
    assert all(row["text"].startswith("'") for row in safe)
    raw = [
        json.loads(line)
        for line in convert_parquet(data, "jsonl", csv_mode="exact", max_bytes=10000).splitlines()
    ]
    assert raw[0] == {"text": "-3", "number": -3}
    assert convert_parquet(data, "parquet", csv_mode="spreadsheet_safe", max_bytes=10000) == data
