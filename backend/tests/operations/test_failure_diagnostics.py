# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import json

from koinon.operations.failure_diagnostics import failure_metadata


def test_diagnostics_preserve_exception_locations_without_messages_or_locals():
    secret = "confidential-query-and-provider-token"
    try:
        try:
            raise ValueError(secret)
        except ValueError as cause:
            raise RuntimeError(secret) from cause
    except RuntimeError as error:
        records = failure_metadata(error)
    assert [row["error_type"] for row in records] == ["RuntimeError", "ValueError"]
    assert all(row["frames"] for row in records)
    assert secret not in json.dumps(records)


def test_diagnostics_bound_groups_cycles_and_reject_free_form_codes():
    error = RuntimeError("private body")
    error.code = "private body"  # type: ignore[attr-defined]
    error.__cause__ = error
    group = ExceptionGroup("private group", [error] * 20)
    records = failure_metadata(group)
    assert len(records) == 2
    assert all("code" not in row for row in records)
    assert "private" not in json.dumps(records)
    assert len(failure_metadata(ExceptionGroup("group", [ValueError(str(i)) for i in range(20)]))) == 8


def test_diagnostics_do_not_invoke_foreign_exception_properties():
    class ProviderFailure(Exception):
        @property
        def code(self):
            raise ValueError("private provider failure")

    records = failure_metadata(ProviderFailure("private message"))
    assert records == [{"error_type": "ProviderFailure", "frames": []}]
