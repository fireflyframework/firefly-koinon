# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from koinon.knowledge.bulk.upload_formats import upload_formats


def test_format_descriptors_are_deterministic_and_do_not_advertise_missing_parsers(monkeypatch):
    monkeypatch.setattr("koinon.knowledge.bulk.upload_formats.find_spec", lambda name: None)
    formats = upload_formats()
    assert formats == upload_formats()
    assert next(row for row in formats if row.extensions == [".pdf"]).available is False
    assert next(row for row in formats if row.extensions == [".txt", ".text"]).available is True
    assert not any(extension in {".mp3", ".mp4", ".zip"} for row in formats for extension in row.extensions)
    assert all(row.reason for row in formats if not row.available)


def test_available_formats_follow_registered_parsers_and_installed_dependencies(monkeypatch):
    monkeypatch.setattr("koinon.knowledge.bulk.upload_formats.find_spec", lambda name: object())
    formats = upload_formats()
    assert all(row.available for row in formats)
    assert any(row.mode == "document" and ".docx" in row.extensions for row in formats)
    assert any(row.mode == "dataset" and ".parquet" in row.extensions for row in formats)
    assert any(row.mode == "dataset" and ".ndjson" in row.extensions for row in formats)


def test_structured_compression_hints_preserve_existing_supported_wrappers(monkeypatch):
    monkeypatch.setattr("koinon.knowledge.bulk.upload_formats.find_spec", lambda name: object())
    formats = upload_formats()
    csv = next(row for row in formats if row.mode == "dataset" and ".csv" in row.extensions)
    assert {".csv.gz", ".csv.bz2", ".csv.zip"} <= set(csv.extensions)
