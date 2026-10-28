# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime

import pytest
from starlette.requests import Request

from flyquery.web.conventions.glossary_revisions import expected_glossary_revision


def request(value=None):
    return Request(
        {
            "type": "http",
            "method": "PUT",
            "path": "/",
            "headers": [] if value is None else [(b"if-match", value.encode())],
        }
    )


def test_standalone_missing_condition_remains_optional_and_exact_timestamps_are_preserved():
    assert expected_glossary_revision(request()) is None
    assert expected_glossary_revision(request('"2026-10-27T12:00:00.123456Z"')) == datetime(
        2026, 10, 27, 12, 0, 0, 123456, UTC
    )


@pytest.mark.parametrize("value", ["*", 'W/"2026-10-27T12:00:00Z"', "2026-10-27T12:00:00", "not-a-date"])
def test_invalid_or_weak_revision_is_never_guessed(value):
    from flyquery.web.conventions import InvalidRequest

    with pytest.raises(InvalidRequest):
        expected_glossary_revision(request(value))
