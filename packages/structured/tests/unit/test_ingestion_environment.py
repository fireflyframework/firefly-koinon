# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Container environment limits retain strict direct-input validation."""

import pytest
from pydantic import ValidationError

from flyquery.config import FlyquerySettings


def test_container_environment_applies_bounded_numeric_ingestion_limits(monkeypatch):
    values = {
        "ingest_duckdb_threads": 1,
        "ingest_native_connections": 1,
        "ingest_scratch_max_bytes": 268435456,
        "ingest_decompressed_max_bytes": 67108864,
    }
    for field, value in values.items():
        monkeypatch.setenv("FLYQUERY_" + field.upper(), str(value))
    settings = FlyquerySettings(_env_file=None)
    assert {field: getattr(settings, field) for field in values} == values
    assert all(type(getattr(settings, field)) is int for field in values)


def test_dotenv_numeric_limits_use_the_same_conversion(tmp_path):
    path = tmp_path / "owned.env"
    path.write_text("FLYQUERY_INGEST_DUCKDB_THREADS=2\nFLYQUERY_INGEST_NATIVE_CONNECTIONS=1\n")
    assert FlyquerySettings(_env_file=path).ingest_duckdb_threads == 2


@pytest.mark.parametrize("value", [True, 1.5, "1"])
def test_direct_input_remains_strict(value):
    with pytest.raises(ValidationError):
        FlyquerySettings(_env_file=None, ingest_duckdb_threads=value)


@pytest.mark.parametrize("value", ["true", "1.5", " 1", "1e1", "0", "65"])
def test_environment_does_not_coerce_boolean_fractional_or_out_of_bounds_limits(monkeypatch, value):
    monkeypatch.setenv("FLYQUERY_INGEST_DUCKDB_THREADS", value)
    with pytest.raises(ValidationError):
        FlyquerySettings(_env_file=None)


def test_explicit_typed_limit_precedes_environment(monkeypatch):
    monkeypatch.setenv("FLYQUERY_INGEST_DUCKDB_THREADS", "3")
    assert FlyquerySettings(_env_file=None, ingest_duckdb_threads=2).ingest_duckdb_threads == 2
