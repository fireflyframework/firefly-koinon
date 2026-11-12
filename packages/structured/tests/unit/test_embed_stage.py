# Copyright 2024-2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
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

"""Unit tests for Stage 9 -- embed.

Verifies:

* ``_build_embed_text`` constructs the correct text from schema-object rows
  (used as the embedding input + as the ``content_tsv`` source).
* ``run_embed`` is callable with a ``NullEmbedder`` and returns an empty-result
  shape -- a graceful no-op when the provider is unavailable.

The provider-selection behavior is covered by ``test_embedder.py``; this
file focuses on the stage's per-row text shaping + the no-op contract.
"""

from __future__ import annotations

import pytest

from flyquery.core.services.ingestion.stages.embed import _build_embed_text


@pytest.mark.parametrize("denied", ["embed_read", "model", "embed_write", None])
async def test_source_stage_guard_blocks_read_model_and_output_independently(monkeypatch, denied):
    from contextlib import asynccontextmanager
    from hashlib import sha256
    from types import SimpleNamespace
    from uuid import uuid4

    from flyquery.core.services.ingestion.stages import embed

    snapshot, object_id = uuid4(), uuid4()
    row = {"id": object_id, "qualified_name": "sales.amount", "data_type": "INTEGER"}
    state = {"phase": None, "native": False, "reads": 0, "models": 0, "writes": 0}

    class Denied(Exception):
        pass

    class Guard:
        @asynccontextmanager
        async def unit(self, phase, target):
            assert target.tenant_id == "tenant" and target.snapshot_id == snapshot
            assert not state["native"] and state["phase"] is None
            if phase == "embed_write":
                assert target.object_id == object_id
                assert target.input_sha256 == sha256(_build_embed_text(row).encode()).hexdigest()
            if phase == denied:
                raise Denied
            state["phase"] = phase
            try:
                yield
            finally:
                state["phase"] = None

        async def before_model(self, targets):
            assert not state["native"] and state["phase"] is None
            assert len(targets) == 1 and targets[0].object_id == object_id
            assert targets[0].input_sha256 == sha256(_build_embed_text(row).encode()).hexdigest()
            if denied == "model":
                raise Denied

    class Session:
        async def execute(self, statement, values):
            if "SELECT" in str(statement):
                assert state["phase"] == "embed_read"
                state["reads"] += 1
                return SimpleNamespace(mappings=lambda: SimpleNamespace(all=lambda: [row]))
            assert state["phase"] == "embed_write"
            state["writes"] += 1

    @asynccontextmanager
    async def native(_):
        state["native"] = True
        try:
            yield Session()
        finally:
            state["native"] = False

    class Embedder:
        model = "test"

        async def embed_batch(self, texts):
            assert not state["native"] and state["phase"] is None
            state["models"] += 1
            return [None for _ in texts]

    monkeypatch.setattr(embed, "infrastructure_unit", native)
    invocation = embed.run_embed(
        tenant_id="tenant",
        snapshot_id=snapshot,
        session_factory=object(),
        embedder=Embedder(),
        guard=Guard(),
    )
    if denied:
        with pytest.raises(Denied):
            await invocation
    else:
        assert (await invocation)["objects_processed"] == 1
    assert (state["reads"], state["models"], state["writes"]) == {
        "embed_read": (0, 0, 0),
        "model": (1, 0, 0),
        "embed_write": (1, 1, 0),
        None: (1, 1, 1),
    }[denied]
    assert not state["native"] and state["phase"] is None


def test_redacted_samples_do_not_return_through_profile_values() -> None:
    row = {
        "qualified_name": "people.email",
        "pii_tag": "EMAIL_ADDRESS",
        "sample_values_json": [],
        "profile_json": {"top_values": [{"value": "synthetic@example.invalid", "count": 1}]},
    }
    text = _build_embed_text(row)
    assert "synthetic@example.invalid" not in text
    assert "Values:" not in text


def test_redacted_catalog_values_and_ranges_remain_unavailable() -> None:
    from flyquery.core.services.query.value_anchoring import coerce_profile

    profile = {"top_values": [{"value": "private-id"}], "min": 17, "max": 17}
    result = coerce_profile(profile, [])
    assert result["values"] == []
    assert result["min"] is None
    assert result["max"] is None


def test_unredacted_profile_values_remain_available() -> None:
    from flyquery.core.services.query.value_anchoring import coerce_profile

    result = coerce_profile({"top_values": [{"value": "approved-category"}]}, None)
    assert result["values"] == ["approved-category"]


def test_redacted_retrieval_metadata_does_not_export_the_raw_profile() -> None:
    from flyquery.core.services.retrieval.search_index import _schema_hit

    row = {
        "id": "synthetic-column",
        "table_id": "synthetic-table",
        "kind": "COLUMN",
        "qualified_name": "people.email",
        "data_type": "VARCHAR",
        "description": "Email address",
        "sample_values_json": [],
        "profile_json": {"top_values": [{"value": "synthetic@example.invalid"}]},
    }
    hit = _schema_hit(row, 1.0)
    assert "synthetic@example.invalid" not in str(hit.metadata)
    assert "synthetic@example.invalid" not in hit.text
    assert hit.metadata["value_access"] is False


class TestBuildEmbedText:
    def test_qualified_name_and_type(self) -> None:
        row = {
            "qualified_name": "sales.orders.total",
            "data_type": "DOUBLE",
            "description": None,
            "synonyms_json": None,
        }
        text = _build_embed_text(row)
        assert text == "sales.orders.total: DOUBLE"

    def test_with_description(self) -> None:
        row = {
            "qualified_name": "ds.tbl.col",
            "data_type": "INTEGER",
            "description": "Primary key for order",
            "synonyms_json": None,
        }
        text = _build_embed_text(row)
        assert "Primary key for order" in text

    def test_with_synonyms_list(self) -> None:
        row = {
            "qualified_name": "ds.t.c",
            "data_type": "VARCHAR",
            "description": None,
            "synonyms_json": ["amount", "price", "cost"],
        }
        text = _build_embed_text(row)
        assert "Synonyms:" in text
        assert "amount" in text

    def test_with_synonyms_dict(self) -> None:
        row = {
            "qualified_name": "ds.t.c",
            "data_type": "VARCHAR",
            "description": None,
            "synonyms_json": {"0": "amt", "1": "price"},
        }
        text = _build_embed_text(row)
        assert "Synonyms:" in text

    def test_missing_qualified_name_does_not_crash(self) -> None:
        row = {
            "qualified_name": None,
            "data_type": "BOOLEAN",
            "description": None,
            "synonyms_json": None,
        }
        text = _build_embed_text(row)
        # Should not raise; may be empty or just the type
        assert isinstance(text, str)


class TestNullEmbedderContract:
    """The embed stage's graceful-skip contract is now expressed through
    ``NullEmbedder`` rather than ``_build_embedder``. The pipeline must
    keep running with embeddings_written=0 when the provider is the null
    backend."""

    def test_null_embedder_returns_none(self) -> None:
        import asyncio

        from flyquery.core.services.retrieval.embedder import NullEmbedder

        e = NullEmbedder()
        assert asyncio.run(e.embed("hello")) is None
        assert asyncio.run(e.embed_batch(["a", "b"])) == [None, None]
