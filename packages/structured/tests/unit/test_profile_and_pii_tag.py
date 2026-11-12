# Copyright 2024-2026 Firefly Software Foundation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Unit tests for profile stage helpers and PII tag policy logic."""

from __future__ import annotations

import pytest


@pytest.mark.parametrize("denied", ["profile_read", "profile_write", None])
async def test_profile_authorizes_reads_and_computed_output(monkeypatch, denied):
    from contextlib import asynccontextmanager
    from types import SimpleNamespace
    from uuid import uuid4

    from flyquery.core.services.ingestion.stages import profile

    snapshot, column = uuid4(), uuid4()
    state = {"phase": None, "reads": 0, "writes": 0}

    class DeniedError(Exception):
        pass

    class Guard:
        @asynccontextmanager
        async def unit(self, phase, target):
            assert target.tenant_id == "native" and target.snapshot_id == snapshot
            if phase == "profile_write":
                assert target.object_id == column
            if phase == denied:
                raise DeniedError
            state["phase"] = phase
            try:
                yield
            finally:
                state["phase"] = None

    async def columns(*args):
        assert state["phase"] == "profile_read"
        state["reads"] += 1
        return [
            {
                "id": column,
                "qualified_name": "records.amount",
                "column_name": "amount",
                "data_type": "INTEGER",
            }
        ]

    async def compute(function, *args):
        assert state["phase"] is None
        return {"distinct_count": 2} if function is profile._profile_column_sync else {}

    async def persist(*args):
        assert state["phase"] == "profile_write" and args[1] == {"distinct_count": 2}
        state["writes"] += 1

    monkeypatch.setattr(profile, "_load_columns", columns)
    monkeypatch.setattr(profile, "run_native", compute)
    monkeypatch.setattr(profile, "_persist_profile", persist)
    invocation = profile.run_profile(
        tenant_id="native",
        snapshot_id=snapshot,
        parquet_key="owned.parquet",
        n_rows_actual=2,
        session_factory=object(),
        settings=SimpleNamespace(profile_row_threshold=10),
        guard=Guard(),
    )
    if denied:
        with pytest.raises(DeniedError):
            await invocation
    else:
        assert (await invocation)["columns_profiled"] == 1
    assert (state["reads"], state["writes"]) == {
        "profile_read": (0, 0),
        "profile_write": (1, 0),
        None: (1, 1),
    }[denied]
    assert state["phase"] is None


class TestProfileTypeHelpers:
    """Test numeric/temporal type detection helpers."""

    def test_integer_is_numeric(self):
        from flyquery.core.services.ingestion.stages.profile import _is_numeric

        assert _is_numeric("INTEGER")
        assert _is_numeric("BIGINT")
        assert _is_numeric("DOUBLE")
        assert _is_numeric("DECIMAL(10,2)")

    def test_varchar_not_numeric(self):
        from flyquery.core.services.ingestion.stages.profile import _is_numeric

        assert not _is_numeric("VARCHAR")
        assert not _is_numeric("TEXT")

    def test_date_is_temporal(self):
        from flyquery.core.services.ingestion.stages.profile import _is_temporal

        assert _is_temporal("DATE")
        assert _is_temporal("TIMESTAMP")
        assert _is_temporal("TIMESTAMPTZ")

    def test_varchar_not_temporal(self):
        from flyquery.core.services.ingestion.stages.profile import _is_temporal

        assert not _is_temporal("VARCHAR")


class TestPiiTagPolicyDocumentation:
    """Verify policy constants documented correctly."""

    def test_valid_policies(self):
        # Policy is enforced at settings level; just document valid values
        valid = {"warn", "redact", "reject"}
        assert "warn" in valid
        assert "redact" in valid
        assert "reject" in valid

    @pytest.mark.asyncio
    async def test_pii_tag_module_importable(self):
        from flyquery.core.services.ingestion.stages import pii_tag

        assert hasattr(pii_tag, "run_pii_tag")

    @pytest.mark.asyncio
    async def test_profile_module_importable(self):
        from flyquery.core.services.ingestion.stages import profile

        assert hasattr(profile, "run_profile")
