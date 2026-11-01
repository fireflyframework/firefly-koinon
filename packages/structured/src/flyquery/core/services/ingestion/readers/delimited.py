# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""One captured dialect drives the actual scan and its source-record receipt."""

import csv
from bisect import bisect_right
from collections.abc import Iterator, Sequence
from dataclasses import dataclass

from flyquery.core.services.ingestion.coordinates import RowRange
from flyquery.core.services.ingestion.resources import IngestionResourceLimitError


class RecordPositions(Sequence[int]):
    """Source positions stored as runs, with a bounded coordinate receipt."""

    def __init__(self):
        self.spans: list[RowRange] = []
        self.starts: list[int] = []
        self._length = 0

    @property
    def span_count(self):
        return len(self.spans)

    def append(self, source: int):
        if self.spans and self.spans[-1].source_start + self.spans[-1].count == source:
            previous = self.spans[-1]
            self.spans[-1] = RowRange(previous.output_start, previous.count + 1, previous.source_start)
        else:
            if len(self.spans) >= 65536:
                raise IngestionResourceLimitError("Source coordinate receipt exceeds its range budget")
            self.starts.append(self._length)
            self.spans.append(RowRange(self._length, 1, source))
        self._length += 1

    def __len__(self):
        return self._length

    def __getitem__(self, index):
        if isinstance(index, slice):
            return tuple(self[i] for i in range(*index.indices(self._length)))
        if index < 0:
            index += self._length
        if not 0 <= index < self._length:
            raise IndexError(index)
        span = self.spans[bisect_right(self.starts, index) - 1]
        return span.source_start + index - span.output_start

    def __iter__(self) -> Iterator[int]:
        for span in self.spans:
            yield from range(span.source_start, span.source_start + span.count)


class _PhysicalLines:
    def __init__(self, stream):
        self.stream = iter(stream)
        self.first = None

    def __iter__(self):
        return self

    def __next__(self):
        line = next(self.stream)
        if self.first is None:
            self.first = line
        return line


@dataclass(frozen=True)
class DelimitedReceipt:
    record_indices: Sequence[int]
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
    if excel and conn.execute("SELECT count(*) FROM mapping_rejects").fetchone()[0] > 65536:
        raise IngestionResourceLimitError("Rejected source rows exceed the coordinate receipt budget")
    rejects = (
        set(row[0] for row in conn.execute("SELECT DISTINCT line FROM mapping_rejects").fetchall())
        if excel
        else set()
    )
    conn.execute(
        "COPY mapped_input TO '"
        + target.replace("'", "''")
        + "' (FORMAT PARQUET,COMPRESSION 'snappy',ROW_GROUP_SIZE 2048,USE_TMP_FILE false)"
    )
    row_count = conn.execute("SELECT count(*) FROM mapped_input").fetchone()[0]
    indices, header_record, header_fields = RecordPositions(), None, ()
    record_index = 0
    lexical_complete = True
    rejected_records, matched_rejects = [], set()
    with open(source, encoding="utf-8-sig", newline="") as stream:
        physical = _PhysicalLines(stream)
        reader = csv.reader(
            physical,
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
                first_line, physical.first = physical.first, None
                ordinal = record_index
                record_index += 1
                if end_line <= observed["SkipRows"]:
                    continue
                if start_line <= observed["SkipRows"]:
                    lexical_complete = False
                if comment and first_line is not None and first_line.startswith(comment):
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
        indices = RecordPositions()
    memory_limit, threads = conn.execute(
        "SELECT current_setting('memory_limit'), current_setting('threads')"
    ).fetchone()
    decisions = (
        ("duckdb_memory_limit", memory_limit),
        ("duckdb_threads", threads),
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
        indices,
        header_record,
        decisions,
        lexical_complete and len(indices) == row_count,
        header_fields,
        tuple(rejected_records),
    )
