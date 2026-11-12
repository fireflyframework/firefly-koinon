# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Queued preferences are bounded request intent, not authorization evidence."""

import json

import pytest
from pydantic import ValidationError
from pyfly.kernel import InvalidRequestException

from koinon.assistants.dtos import RunInput
from koinon.assistants.run_selection import RunSourceSelection, request_choices, stored_selection


@pytest.mark.parametrize(
    "value",
    [
        {"version": True, "mode": "local_only", "connections": []},
        {"mode": "saved", "revision": True, "connections": []},
        {"mode": "saved", "connections": []},
        {"mode": "explicit", "connections": []},
        {"mode": "local_only", "revision": 0, "connections": []},
        {"mode": "local_only", "connections": [], "grant": "forged"},
    ],
)
def test_snapshot_rejects_ambiguous_or_forged_intent(value):
    with pytest.raises(ValidationError):
        RunSourceSelection.model_validate(value)


def test_legacy_null_is_local_only_and_never_saved_defaults():
    value = stored_selection(None)
    assert value.mode == "local_only" and value.connections == ()
    assert value.snapshot().revision is None


def test_request_rejects_duplicate_account_pair_before_submission():
    choices = [
        {"provider": "google_drive", "connection_id": identifier} for identifier in ("first", "second")
    ]
    with pytest.raises(InvalidRequestException):
        request_choices({"reader_source_connections": choices})
    with pytest.raises(ValidationError):
        RunInput(
            agent_id="agent",
            message="Question",
            client_request_id="request",
            reader_source_connections=choices,
        )


def test_request_normalizes_explicit_order_without_merging_or_losing_empty():
    values = [
        {"provider": provider, "connection_id": provider} for provider in ("sharepoint", "google_drive")
    ]
    assert request_choices({}) is None
    assert request_choices({"reader_source_connections": []}) == ()
    first = request_choices({"reader_source_connections": values})
    assert first == request_choices({"reader_source_connections": list(reversed(values))})
    assert {item.connection_id for item in first} == {"sharepoint", "google_drive"}


def test_snapshot_bounds_encoded_unicode_size():
    choices = [
        {"provider": "sharepoint", "connection_id": str(index), "external_tenant": str(index) + "界" * 1000}
        for index in range(100)
    ]
    with pytest.raises(ValidationError):
        RunSourceSelection(mode="explicit", connections=choices)


def test_snapshot_bounds_the_database_json_encoding():
    choices = [
        {"provider": "sharepoint", "connection_id": str(index), "external_tenant": str(index) + "界" * 450}
        for index in range(50)
    ]
    value = {"version": 1, "mode": "explicit", "revision": None, "connections": choices}
    assert len(json.dumps(value, ensure_ascii=False).encode("utf-8")) < 131072
    assert len(json.dumps(value).encode("utf-8")) > 131072
    with pytest.raises(ValidationError, match="too large"):
        RunSourceSelection.model_validate(value)
