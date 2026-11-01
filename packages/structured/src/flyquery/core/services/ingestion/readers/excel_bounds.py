# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Bound native spreadsheet shapes and retain rows in private accounted scratch."""

import datetime
import json
import re
import sqlite3
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any, overload
from xml.parsers.expat import ParserCreate
from zipfile import ZipFile

from flyquery.core.services.ingestion.resources import (
    IngestionResourceLimitError,
    account_path,
    current_scope,
)

_CELL = re.compile(r"\$?([A-Z]{1,3})\$?([1-9][0-9]{0,6})\Z")


def shape(height, width):
    policy = current_scope().policy
    if height < 0 or width < 0:
        raise IngestionResourceLimitError("Spreadsheet contains an invalid used shape")
    if (
        height > policy.excel_max_rows
        or width > policy.excel_max_columns
        or height * width > policy.excel_max_cells
    ):
        raise IngestionResourceLimitError("Spreadsheet used shape exceeds the configured cell budget")


def _coordinate(value):
    match = _CELL.fullmatch(value)
    if match is None:
        raise IngestionResourceLimitError("Spreadsheet contains an invalid cell coordinate")
    column = 0
    for char in match[1]:
        column = column * 26 + ord(char) - 64
    row = int(match[2])
    policy = current_scope().policy
    if row > policy.excel_max_rows or column > policy.excel_max_columns:
        raise IngestionResourceLimitError("Spreadsheet cell shape exceeds configured axis bounds")
    return row, column


def _xml_parser(start=None):
    parser = ParserCreate(namespace_separator="}")

    def reject_entity(*args):
        raise IngestionResourceLimitError("Spreadsheet XML entity declarations are unsupported")

    parser.StartDoctypeDeclHandler = reject_entity
    parser.EntityDeclHandler = reject_entity
    parser.ExternalEntityRefHandler = reject_entity
    if start is not None:
        parser.StartElementHandler = start
    return parser


def preflight(path):
    if Path(path).suffix.lower() not in {".xlsx", ".ods"}:
        return
    cap = current_scope().policy.decompressed_max_bytes
    with ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) > 4096 or len(set(names)) != len(names):
            raise IngestionResourceLimitError("Spreadsheet archive has too many or duplicate members")
        worksheet_parts, shared_string_parts = set(), set()

        def content_type(name, attributes):
            if name.rsplit("}", 1)[-1] != "Override":
                return
            kind = attributes.get("ContentType", "")
            part = attributes.get("PartName", "").lstrip("/")
            if kind.endswith(".worksheet+xml"):
                worksheet_parts.add(part)
            if kind.endswith(".sharedStrings+xml"):
                shared_string_parts.add(part)
            if len(worksheet_parts) + len(shared_string_parts) > 4096:
                raise IngestionResourceLimitError("Spreadsheet has too many declared parser parts")

        if "[Content_Types].xml" in names:
            info = archive.getinfo("[Content_Types].xml")
            if info.file_size > cap:
                raise IngestionResourceLimitError("Spreadsheet expanded content exceeds its byte budget")
            parser, count = _xml_parser(content_type), 0
            with archive.open(info) as source:
                while chunk := source.read(64 * 1024):
                    count += len(chunk)
                    if count > cap:
                        raise IngestionResourceLimitError(
                            "Spreadsheet expanded content exceeds its byte budget"
                        )
                    parser.Parse(chunk, False)
                parser.Parse(b"", True)
        total = 0
        for info in archive.infolist():
            if info.flag_bits & 1:
                raise IngestionResourceLimitError("Encrypted spreadsheet archives are unsupported")
            limit = (
                min(cap, current_scope().policy.shared_strings_max_bytes)
                if info.filename == "xl/sharedStrings.xml" or info.filename in shared_string_parts
                else cap
            )
            if info.file_size > limit or total + info.file_size > cap:
                raise IngestionResourceLimitError("Spreadsheet expanded content exceeds its byte budget")
            actual = 0
            is_xml = (
                info.filename.lower().endswith((".xml", ".rels"))
                or info.filename in worksheet_parts
                or info.filename in shared_string_parts
            )
            minimum, maximum, worksheet, depth = None, (0, 0), False, 0

            def start_element(name, attributes):
                nonlocal minimum, maximum, worksheet, depth
                tag = name.rsplit("}", 1)[-1]
                if depth == 0:
                    worksheet = tag == "worksheet"
                depth += 1
                if not worksheet:
                    return
                if tag == "dimension" and attributes.get("ref"):
                    pieces = attributes["ref"].split(":")
                    first, last = _coordinate(pieces[0]), _coordinate(pieces[-1])
                    shape(last[0] - first[0] + 1, last[1] - first[1] + 1)
                if tag == "c" and attributes.get("r"):
                    row, column = _coordinate(attributes["r"])
                    minimum = (
                        (row, column) if minimum is None else (min(minimum[0], row), min(minimum[1], column))
                    )
                    maximum = max(maximum[0], row), max(maximum[1], column)
                    shape(maximum[0] - minimum[0] + 1, maximum[1] - minimum[1] + 1)

            def end_element(name):
                nonlocal depth
                depth -= 1

            xml = _xml_parser(start_element) if is_xml else None
            if xml is not None:
                xml.EndElementHandler = end_element
            with archive.open(info) as source:
                while chunk := source.read(64 * 1024):
                    actual += len(chunk)
                    total += len(chunk)
                    if actual > limit or total > cap:
                        raise IngestionResourceLimitError(
                            "Spreadsheet expanded content exceeds its byte budget"
                        )
                    if xml is not None:
                        xml.Parse(chunk, False)
                if xml is not None:
                    xml.Parse(b"", True)
            if actual != info.file_size:
                raise IngestionResourceLimitError("Spreadsheet archive member size changed")


def _encode(value):
    if isinstance(value, datetime.datetime):
        return ["datetime", value.isoformat()]
    if isinstance(value, datetime.date):
        return ["date", value.isoformat()]
    if isinstance(value, datetime.time):
        return ["time", value.isoformat()]
    if isinstance(value, datetime.timedelta):
        return ["timedelta", value.days, value.seconds, value.microseconds]
    return value


def _decode(value):
    if not isinstance(value, list):
        return value
    if value[0] == "timedelta":
        return datetime.timedelta(days=value[1], seconds=value[2], microseconds=value[3])
    return getattr(datetime, value[0]).fromisoformat(value[1])


class RowView(Sequence[Any]):
    def __init__(self, source: Sequence[Any], positions: Sequence[int]):
        self.source, self.positions = source, positions

    def __len__(self):
        return len(self.positions)

    def __getitem__(self, index) -> Any:
        if isinstance(index, slice):
            return RowView(self.source, self.positions[index])
        return self.source[self.positions[index]]


class DiskRows(Sequence[list[Any]]):
    def __init__(self, rows):
        self.directory = tempfile.TemporaryDirectory(
            prefix="flyquery-rows-", dir=current_scope().policy.scratch_root
        )
        self.path = Path(self.directory.name) / "rows.sqlite"
        self.connection = sqlite3.connect(self.path)
        self._length, self.leading_empty = 0, 0
        try:
            self.connection.execute("PRAGMA journal_mode=OFF")
            self.connection.execute("PRAGMA cache_size=-1024")
            self.connection.execute("CREATE TABLE rows(position INTEGER PRIMARY KEY,payload TEXT NOT NULL)")
            for row in rows:
                if self._length == 0 and not any(value not in (None, "") for value in row):
                    self.leading_empty += 1
                    continue
                shape(self._length + 1, len(row))
                payload = json.dumps(
                    [_encode(value) for value in row], ensure_ascii=False, separators=(",", ":")
                )
                self.connection.execute("INSERT INTO rows VALUES(?,?)", (self._length, payload))
                self._length += 1
                if self._length % 256 == 0:
                    self.connection.commit()
                    account_path(self.path)
            self.connection.commit()
            account_path(self.path)
        except BaseException:
            self.close()
            raise

    def __len__(self):
        return self._length

    @overload
    def __getitem__(self, index: int) -> list[Any]: ...

    @overload
    def __getitem__(self, index: slice) -> RowView: ...

    def __getitem__(self, index):
        if isinstance(index, slice):
            return RowView(self, range(self._length)[index])
        if index < 0:
            index += self._length
        if not 0 <= index < self._length:
            raise IndexError(index)
        payload = self.connection.execute("SELECT payload FROM rows WHERE position=?", (index,)).fetchone()[0]
        return [_decode(value) for value in json.loads(payload)]

    def close(self):
        self.connection.close()
        self.directory.cleanup()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class SectionPositions(Sequence):
    def __init__(self, header, start, end):
        self.header, self.start, self.end = header, start, end

    def __len__(self):
        return 1 + max(0, self.end - self.start)

    def __getitem__(self, index):
        if isinstance(index, slice):
            return RowView(self, range(len(self))[index])
        if index < 0:
            index += len(self)
        if not 0 <= index < len(self):
            raise IndexError(index)
        return self.header if index == 0 else self.start + index - 1
