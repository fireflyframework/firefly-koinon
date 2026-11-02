# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Actual bounded native readers preserve original bytes and source coordinates."""

import asyncio
from hashlib import sha256
from tempfile import TemporaryFile

import pytest
from office_fixtures import office_original


@pytest.mark.parametrize("kind", ["docx", "pptx", "xlsx", "csv"])
async def test_real_office_documents_extract_text_and_preserve_original_bytes(tmp_path, kind, monkeypatch):
    from flycanon.core.services.ingestion.file_parser import DocumentFilePolicy, parse_document_file

    content = office_original(kind)
    if kind != "csv":
        assert content.startswith(b"PK\x03\x04")
    path = tmp_path / ("review." + kind)
    path.write_bytes(content)
    spawn = asyncio.create_subprocess_exec
    with TemporaryFile() as diagnostics:
        async def observed_spawn(*args, **kwargs):
            kwargs["stderr"] = diagnostics
            return await spawn(*args, **kwargs)

        monkeypatch.setattr(asyncio, "create_subprocess_exec", observed_spawn)
        try:
            parsed = await parse_document_file(path, filename=path.name, policy=DocumentFilePolicy())
        except ValueError:
            diagnostics.seek(0)
            pytest.fail(diagnostics.read(4096).decode(errors="replace"))
    assert parsed.kind == kind and parsed.raw_bytes == len(content)
    assert "North" in parsed.text and "125" in parsed.text
    assert path.read_bytes() == content
    if kind == "pptx":
        assert {section["page"] for section in parsed.sections} == {1, 2}
        assert parsed.metadata["page_basis"] == "slide_order"
    if kind == "docx":
        assert "Review header" in parsed.text
        assert all(section["page"] is None for section in parsed.sections)
    if kind in {"docx", "pptx"}:
        assert parsed.metadata["image_interpretation"] == "not_performed"


@pytest.mark.parametrize("kind", ["xlsx", "csv"])
async def test_real_dataset_readers_materialize_rows_with_exact_source_coordinates(tmp_path, kind):
    import pyarrow.parquet as parquet
    from flyquery.core.services.ingestion.reader import TableExtractionRules
    from flyquery.core.services.ingestion.reader_factory import get_reader

    content = office_original(kind)
    source = tmp_path / ("revenue." + kind)
    source.write_bytes(content)
    reader = get_reader(kind)
    tables = await reader.enumerate_tables(str(source), TableExtractionRules())
    assert len(tables) == 1
    target = tmp_path / "revenue.parquet"
    result = await reader.materialise(
        str(source), tables[0], str(target), workspace_locale="en-US", type_infer_sample_rows=100
    )
    assert result.n_rows_actual == 2
    assert parquet.read_table(target).to_pydict() == {"Region": ["North", "South"], "Revenue": [125, 250]}
    assert result.coordinates is not None and result.coordinates.complete
    assert result.coordinates.input_sha256 == sha256(content).hexdigest()
    assert (result.coordinates.row_count, result.coordinates.column_count) == (2, 2)
    assert result.coordinates.source_sheet == ("Revenue" if kind == "xlsx" else None)
    assert source.read_bytes() == content
