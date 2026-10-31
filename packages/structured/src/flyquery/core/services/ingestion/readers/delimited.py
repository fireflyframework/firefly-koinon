# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""One captured dialect drives the actual scan and its source-record receipt."""

import csv
from dataclasses import dataclass

from flyquery.core.services.ingestion.coordinates import RowRange


@dataclass(frozen=True)
class DelimitedReceipt:
    record_indices: tuple[int, ...]
    header_record: int | None
    decisions: tuple
    complete: bool
    header_fields: tuple[str, ...] = ()
    rejected_records: tuple[int, ...] = ()


def ranges(indices):
    result = []
    for output, source in enumerate(indices):
        if result and result[-1].source_start + result[-1].count == source:
            previous = result[-1]
            result[-1] = RowRange(previous.output_start, previous.count + 1, previous.source_start)
        else:
            result.append(RowRange(output, 1, source))
    return tuple(result)


def materialize(conn, source, target, *, sample_rows, date_format=None, excel=False):
    """Capture a dialect once, apply it explicitly, and retain same-scan rejects."""
    sniff_options = "sample_size=?"
    arguments = [source, sample_rows]
    if date_format:
        sniff_options += ",dateformat=?"
        arguments.append(date_format)
    if excel:
        sniff_options += ",delim=',',quote='\"',escape='\"',null_padding=true,max_line_size=10000000"
    cursor = conn.execute(f"SELECT * FROM sniff_csv(?,{sniff_options})", arguments)
    observed = dict(zip((column[0] for column in cursor.description), cursor.fetchone(), strict=True))

    def empty(value):
        return "" if value in (None, "(empty)") else value

    delimiter, quote, escape, comment = (
        empty(observed[key]) for key in ("Delimiter", "Quote", "Escape", "Comment")
    )
    options = "auto_detect=false,header=?,columns=?,delim=?,quote=?,escape=?,skip=?,new_line=?,comment=?,ignore_errors=?"
    params = [
        source,
        observed["HasHeader"],
        {item["name"]: item["type"] for item in observed["Columns"]},
        delimiter,
        quote,
        escape,
        observed["SkipRows"],
        observed["NewLineDelimiter"],
        comment,
        excel,
    ]
    actual_date = date_format or observed["DateFormat"]
    if actual_date:
        options += ",dateformat=?"
        params.append(actual_date)
    if observed["TimestampFormat"]:
        options += ",timestampformat=?"
        params.append(observed["TimestampFormat"])
    if excel:
        options += ",null_padding=true,max_line_size=10000000,store_rejects=true,rejects_table='mapping_rejects',rejects_scan='mapping_scans'"
    conn.execute("SET preserve_insertion_order=true")
    conn.execute(f"CREATE TEMP TABLE mapped_input AS SELECT * FROM read_csv(?,{options})", params)
    rejects = (
        set(row[0] for row in conn.execute("SELECT DISTINCT line FROM mapping_rejects").fetchall())
        if excel
        else set()
    )
    conn.execute(
        "COPY mapped_input TO '" + target.replace("'", "''")
        + "' (FORMAT PARQUET,COMPRESSION 'snappy',USE_TMP_FILE false)"
    )
    row_count = conn.execute("SELECT count(*) FROM mapped_input").fetchone()[0]
    indices, header_record, header_fields = [], None, ()
    record_index = 0
    lexical_complete = True
    rejected_records, matched_rejects = [], set()
    with open(source, encoding="utf-8-sig", newline="") as stream:
        lines = stream.readlines()
    reader = csv.reader(
        lines,
        delimiter=delimiter,
        quotechar=quote or None,
        quoting=csv.QUOTE_MINIMAL if quote else csv.QUOTE_NONE,
        doublequote=not escape or escape == quote,
        escapechar=escape if escape and escape != quote else None,
        strict=True,
    )
    previous_line = 0
    try:
        for record in reader:
            start_line, end_line = previous_line + 1, reader.line_num
            previous_line = end_line
            ordinal = record_index
            record_index += 1
            if end_line <= observed["SkipRows"]:
                continue
            if start_line <= observed["SkipRows"]:
                lexical_complete = False
            if comment and lines[start_line - 1].startswith(comment):
                continue
            if not record and len(observed["Columns"]) > 1:
                continue
            if observed["HasHeader"] and header_record is None:
                header_record, header_fields = ordinal, tuple(record)
                continue
            matched = {line for line in rejects if start_line <= line <= end_line}
            if matched:
                rejected_records.append(ordinal)
                matched_rejects.update(matched)
            else:
                indices.append(ordinal)
    except csv.Error:
        lexical_complete = False
    lexical_complete = lexical_complete and matched_rejects == rejects
    if not lexical_complete or len(indices) != row_count:
        indices = []
    decisions = (
        ("delimiter", delimiter),
        ("quote", quote),
        ("escape", escape),
        ("comment", comment),
        ("skip_rows", observed["SkipRows"]),
        ("header", observed["HasHeader"]),
        ("date_format", actual_date),
        ("timestamp_format", observed["TimestampFormat"]),
        ("sample_rows", sample_rows),
        ("input_records", record_index),
        ("output_records", row_count),
        ("rejected_lines", len(rejects)),
        ("ignore_errors", excel),
        ("null_padding", excel),
        ("row_order", "source_record_order"),
    )
    return DelimitedReceipt(
        tuple(indices),
        header_record,
        decisions,
        lexical_complete and len(indices) == row_count,
        header_fields,
        tuple(rejected_records),
    )
