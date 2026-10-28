# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import base64
import csv
import io
import json
import time
from datetime import date, datetime
from datetime import time as datetime_time
from decimal import Decimal


def _value(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime, datetime_time)):
        return value.isoformat()
    if isinstance(value, bytes):
        return base64.b64encode(value).decode("ascii")
    return value


def _json_value(value):
    if isinstance(value, int) and not isinstance(value, bool) and abs(value) > 9007199254740991:
        return str(value)
    return _value(value)


def _csv_value(value, mode):
    if (
        mode == "spreadsheet_safe"
        and isinstance(value, str)
        and (value.startswith(("\t", "\r", "\n")) or value.lstrip().startswith(("=", "+", "-", "@")))
    ):
        return "'" + value
    return _value(value)


def convert_parquet(
    content: bytes,
    format: str,
    *,
    csv_mode: str,
    max_bytes: int,
    timeout_seconds=120,
    cancelled=lambda: False,
) -> bytes:
    import pyarrow as pa
    import pyarrow.parquet as pq

    if format not in {"parquet", "csv", "jsonl"} or csv_mode not in {"spreadsheet_safe", "exact"}:
        raise ValueError("Choose a supported data export format and CSV mode")
    if len(content) > max_bytes:
        raise ValueError("Stored result exceeds the byte limit")
    deadline = time.monotonic() + timeout_seconds
    file = pq.ParquetFile(io.BytesIO(content))
    metadata = file.metadata
    if format == "parquet":
        return content
    if sum(metadata.row_group(i).total_byte_size for i in range(metadata.num_row_groups)) > max_bytes:
        raise ValueError("Decoded result exceeds the byte limit")
    if any(pa.types.is_nested(field.type) for field in file.schema_arrow):
        raise ValueError("Nested results are available as Parquet; CSV and JSONL require scalar columns")
    output = bytearray()

    def append(value):
        if cancelled() or time.monotonic() >= deadline:
            raise ValueError("Data export exceeded its execution limit")
        encoded = value.encode("utf-8")
        if len(output) + len(encoded) > max_bytes:
            raise ValueError("Converted result exceeds the byte limit")
        output.extend(encoded)

    def csv_row(values):
        row = io.StringIO(newline="")
        csv.writer(row).writerow(values)
        return row.getvalue()

    if format == "csv":
        append(csv_row([_csv_value(name, csv_mode) for name in file.schema_arrow.names]))
    # One scalar row bounds dictionary expansion before converting Arrow values to Python.
    for batch in file.iter_batches(batch_size=1):
        if cancelled() or time.monotonic() >= deadline:
            raise ValueError("Data export exceeded its execution limit")
        if batch.nbytes > max_bytes:
            raise ValueError("Decoded row exceeds the byte limit")
        row = batch.to_pylist()[0]
        if format == "jsonl":
            append(
                json.dumps(
                    {key: _json_value(value) for key, value in row.items()},
                    ensure_ascii=False,
                    allow_nan=False,
                )
                + "\n"
            )
        else:
            append(csv_row([_csv_value(row[name], csv_mode) for name in file.schema_arrow.names]))
    return bytes(output)
