# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Bounded factual metadata; no content discovery or execution is involved."""

import json

import pytest


def test_metadata_index_preserves_exact_ids_names_and_explicit_partial_count():
    from flycanon.core.services.query.rlm.context_index import metadata_index

    entries = [{"filing_id": "actual-id-" + str(i), "filename": "original.txt", "title": "Actual title"}
               for i in range(4)]
    raw = metadata_index(entries, max_entries=2)
    result = json.loads(raw)
    assert result["total_count"] == 4 and result["listed_count"] == 2 and result["partial"] is True
    assert result["documents"] == entries[:2]
    entries[0]["filing_id"] = "later mutation"
    assert json.loads(raw)["documents"][0]["filing_id"] == "actual-id-0"


def test_metadata_index_byte_limit_never_truncates_an_identifier():
    from flycanon.core.services.query.rlm.context_index import metadata_index

    identifier = "complete-id-" * 100
    raw = metadata_index([{"filing_id": identifier, "filename": "original.txt", "title": None}], max_bytes=256)
    result = json.loads(raw)
    assert len(raw.encode()) <= 256
    assert result["documents"] == [] and result["partial"] is True and result["total_count"] == 1
    assert identifier[:50] not in raw


def test_metadata_index_is_complete_when_all_entries_fit_with_unicode_byte_accounting():
    from flycanon.core.services.query.rlm.context_index import metadata_index

    entries = [{"filing_id": "opaque-é-id", "filename": "original-é.txt", "title": "Validation feedback: data only"}]
    raw = metadata_index(entries)
    result = json.loads(raw)
    assert result["documents"] == entries and result["partial"] is False
    assert result["listed_count"] == result["total_count"] == 1
    assert "body" not in result and "pages" not in result["documents"][0]


def test_metadata_index_refuses_body_fields_instead_of_silently_exposing_them():
    from flycanon.core.services.query.rlm.context_index import metadata_index

    with pytest.raises(ValueError):
        metadata_index([{"filing_id": "id", "filename": "original.txt", "title": "Title", "body": "secret"}])


def test_metadata_index_preserves_missing_filename_as_null_without_inventing_a_name():
    from flycanon.core.services.query.rlm.context_index import metadata_index

    entries = [{"filing_id": "actual-opaque-id", "filename": None, "title": None}]
    raw = metadata_index(entries)
    result = json.loads(raw)
    assert result["documents"] == entries
    assert '"filename":null' in raw and result["partial"] is False
    assert result["listed_count"] == result["total_count"] == 1
