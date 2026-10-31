# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Exact whole-version projections, distinct from lexical retrieval results."""

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime
from hashlib import sha256
from importlib import import_module, util
from uuid import NAMESPACE_URL, uuid5

import pytest
from pyfly.kernel import ServiceUnavailableException

from koinon.knowledge.curated.authority import digest
from koinon.knowledge.curated.dtos import (
    KnowledgeContent,
    KnowledgeItemView,
    KnowledgeVersionView,
    UserStatementEvidence,
)


def _modules():
    assert util.find_spec("koinon.knowledge.curated.corpus_mappers") is not None, (
        "RLM requires a whole-version mapper; lexical matching parts cannot prove complete coverage"
    )
    return import_module("koinon.knowledge.curated.corpus_mappers"), import_module(
        "koinon.knowledge.curated.corpus_dtos"
    )


def _inputs(body="á🙂" * 2500 + "\nExact tail", publication="published", serving=True):
    mapper, dtos = _modules()
    content = KnowledgeContent(title="Approved operating threshold", body=body)
    now = datetime(2026, 10, 30, tzinfo=UTC)
    evidence = (
        UserStatementEvidence(
            text=body,
            sha256=sha256(body.encode()).hexdigest(),
            author_subject="issuer|curator",
            recorded_at=now,
        ),
    )
    version = KnowledgeVersionView(
        item_id="item",
        version=1,
        version_id="version-one",
        publication=publication,
        serving=serving,
        content=content,
        evidence=evidence,
        content_sha256=digest(content.model_dump(mode="json")),
        evidence_sha256=digest([v.model_dump(mode="json") for v in evidence]),
        operation_id="approved-operation",
        author_subject="issuer|curator",
        committed_at=now,
    )
    value = KnowledgeItemView(
        id="item",
        tenant_id="north",
        workspace_id="canonical-workspace",
        project_id="project",
        destination_id="collection",
        head_version=2,
        serving_version=1,
        selected_version=version,
    )
    selected = dtos.ServingVersion(
        "item", "canonical-workspace", "native-item", "native-workspace", "version-one", 1
    )
    meta = mapper.version_meta(value, selected, tenant_id="north", native_workspace_id="native-workspace")
    parts = tuple(
        dtos.CuratedPartRecord(
            id=str(uuid5(NAMESPACE_URL, f"koinon:knowledge:version-one:{ordinal}")),
            tenant_id="north",
            workspace_id="native-workspace",
            canonical_item_id="item",
            native_item_id="native-item",
            native_version_id="version-one",
            ordinal=ordinal,
            content=body[start : start + 4800],
            sha256=sha256(body[start : start + 4800].encode()).hexdigest(),
            char_start=start,
            char_end=min(start + 4800, len(body)),
        )
        for ordinal, start in enumerate(range(0, len(body), 4800))
    )
    return mapper, dtos, value, selected, meta, parts


def test_complete_unicode_body_keeps_exact_metadata_and_contiguous_parts():
    mapper, _, value, _, meta, parts = _inputs()
    view = mapper.whole_view(meta, value.selected_version.content.body, parts)
    assert view.text == value.selected_version.content.body
    assert view.meta.body_sha256 == sha256(view.text.encode()).hexdigest()
    assert view.meta.body_chars == len(view.text)
    assert view.meta.body_bytes == len(view.text.encode())
    assert view.meta.content_sha256 != view.meta.body_sha256
    assert view.meta.evidence_sha256 == value.selected_version.evidence_sha256
    assert view.meta.operation_id == "approved-operation"
    assert view.meta.author_subject == "issuer|curator"
    assert view.meta.committed_at == value.selected_version.committed_at.isoformat()
    assert view.parts[0].char_end == view.parts[1].char_start == 4800
    assert view.manifest_sha256 == mapper.manifest_digest(view.meta, view.parts)
    assert mapper.whole_view(meta, view.text, parts) == view
    with pytest.raises(FrozenInstanceError):
        view.parts[0].text = "changed"


@pytest.mark.parametrize(
    "mutation",
    [
        "missing",
        "reordered",
        "duplicate_id",
        "duplicate_ordinal",
        "gap",
        "overlap",
        "wrong_end",
        "wrong_hash",
        "wrong_text",
        "foreign_tenant",
        "foreign_workspace",
        "foreign_item",
        "foreign_native_item",
        "foreign_version",
        "unbound_part_id",
    ],
)
def test_projection_rejects_every_incomplete_or_foreign_partition_before_release(mutation):
    mapper, _, value, _, meta, original = _inputs()
    parts = list(original)
    changes = {
        "duplicate_id": dict(id=parts[0].id),
        "duplicate_ordinal": dict(ordinal=0),
        "gap": dict(char_start=4801),
        "overlap": dict(char_start=4799),
        "wrong_end": dict(char_end=parts[1].char_end + 1),
        "wrong_hash": dict(sha256="0" * 64),
        "wrong_text": dict(content="another body"),
        "foreign_tenant": dict(tenant_id="south"),
        "foreign_workspace": dict(workspace_id="other"),
        "foreign_item": dict(canonical_item_id="other"),
        "foreign_native_item": dict(native_item_id="other"),
        "foreign_version": dict(native_version_id="other"),
        "unbound_part_id": dict(id=str(uuid5(NAMESPACE_URL, "unrelated"))),
    }
    if mutation == "missing":
        parts.pop()
    elif mutation == "reordered":
        parts.reverse()
    else:
        parts[1] = replace(parts[1], **changes[mutation])
    with pytest.raises(Exception) as caught:
        mapper.whole_view(meta, value.selected_version.content.body, tuple(parts))
    assert getattr(caught.value, "code", None) == "KNOWLEDGE_PROJECTION_INVALID"


@pytest.mark.parametrize(
    ("publication", "serving"), [("draft", False), ("published", False), ("draft", True)]
)
def test_only_the_acknowledged_published_version_can_be_pinned(publication, serving):
    with pytest.raises(Exception) as caught:
        _inputs(publication=publication, serving=serving)
    assert getattr(caught.value, "code", None) == "KNOWLEDGE_VERSION_CONFLICT"


def test_metadata_and_body_hashes_are_not_guessed_or_interchanged():
    mapper, _, value, selected, meta, parts = _inputs()
    for name in ("content_sha256", "evidence_sha256"):
        tampered = value.model_copy(
            update={"selected_version": value.selected_version.model_copy(update={name: "0" * 64})}
        )
        with pytest.raises(Exception) as caught:
            mapper.version_meta(tampered, selected, tenant_id="north", native_workspace_id="native-workspace")
        assert getattr(caught.value, "code", None) == "KNOWLEDGE_PROJECTION_INVALID"
    with pytest.raises(ServiceUnavailableException):
        mapper.whole_view(meta, value.selected_version.content.body + "x", parts)


@pytest.mark.parametrize(
    "changes",
    [
        {"version": True},
        {"version": 0},
        {"version": 2147483648},
        {"operation_id": ""},
        {"author_subject": "x" * 513},
        {"committed_at": "2026-10-30"},
        {"title": ""},
        {"content_sha256": "not-a-digest"},
        {"evidence_sha256": "A" * 64},
        {"kind": "document"},
    ],
)
def test_whole_view_rejects_untyped_or_unbounded_immutable_metadata(changes):
    mapper, _, value, _, meta, parts = _inputs()
    with pytest.raises(ServiceUnavailableException):
        mapper.whole_view(replace(meta, **changes), value.selected_version.content.body, parts)
