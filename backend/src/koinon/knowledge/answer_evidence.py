# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Private factual units from this native read, separate from model-authored analysis."""

import json
from dataclasses import dataclass
from hashlib import sha256
from math import isfinite
from typing import Literal

from pydantic import JsonValue

from koinon.evidence.dtos import SourceReference
from koinon.knowledge.capture_dtos import CapturedEvidence


@dataclass(frozen=True, slots=True)
class AnswerFact:
    id: str
    result_id: str
    kind: Literal["quote", "cell", "derived"]
    label: str
    source_refs: tuple[SourceReference, ...]
    text: str | None = None
    value: JsonValue = None
    lineage_sha256: str = ""

    def __post_init__(self):
        if self.kind == "quote":
            if not self.text or self.value is not None:
                raise ValueError("A quotation contains only its exact recorded source text")
        elif self.kind in {"cell", "derived"}:
            if self.text is not None or type(self.value) not in {str, int, float, bool, type(None)}:
                raise ValueError("A query fact contains only an immutable native scalar")
            if isinstance(self.value, float) and not isfinite(self.value):
                raise ValueError("A query fact must be finite")
        else:
            raise ValueError("Unknown native fact kind")


@dataclass(frozen=True, slots=True)
class QueryColumnEligibility:
    key: str
    label: str
    kind: Literal["cell", "derived"]
    source_columns: tuple[str, ...]
    lineage_sha256: str


def _digest(value) -> str:
    return sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()


def exact_document_quotes(capture: CapturedEvidence, result_id: str) -> tuple[AnswerFact, ...]:
    if not capture.complete:
        return ()
    facts = []
    for source in capture.sources:
        if not source.quote or not source.quote.strip():
            continue
        revision = source.used_revision or ""
        if source.kind == "document" and source.source_part_id:
            valid = bool(source.source_version_id and source.extraction_id and source.source_part_sha256)
        elif source.kind == "document" and source.chunk_id:
            valid = revision == "chunk-sha256:" + sha256(source.quote.encode()).hexdigest()
        elif source.kind == "knowledge_version":
            valid = revision == "knowledge-content-sha256:" + sha256(source.quote.encode()).hexdigest()
        else:
            valid = False
        if valid:
            facts.append(
                AnswerFact(
                    _digest([result_id, source.id, source.quote]),
                    result_id,
                    "quote",
                    source.title,
                    (source,),
                    text=source.quote,
                )
            )
    return tuple(facts)


def answer_facts(capture: CapturedEvidence, result_id: str) -> tuple[AnswerFact, ...]:
    return exact_document_quotes(capture, result_id) + query_evidence(capture, result_id)


def query_evidence(capture: CapturedEvidence, result_id: str) -> tuple[AnswerFact, ...]:
    from koinon.knowledge.query_eligibility import query_columns

    if not capture.complete:
        return ()
    facts = []
    for proof in capture.query_results:
        sources = tuple(
            source
            for source in capture.sources
            if source.kind == "dataset"
            and source.query_id == proof.query_id
            and source.snapshot_id in dict(proof.snapshot_pins).values()
        )
        if not sources or {source.snapshot_id for source in sources} != set(
            dict(proof.snapshot_pins).values()
        ):
            continue
        attempts = [
            attempt for attempt in capture.sql_attempts if attempt.statement_sha256 == proof.statement_sha256
        ]
        if not attempts:
            continue
        columns = query_columns(attempts[-1], proof)
        rows = json.loads(proof.preview_json)
        if not isinstance(rows, list) or len(rows) > 50:
            continue
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                continue
            for column in columns:
                if column.key not in row:
                    continue
                value = row[column.key]
                if (
                    type(value) not in {str, int, float, bool, type(None)}
                    or isinstance(value, float)
                    and not isfinite(value)
                ):
                    continue
                facts.append(
                    AnswerFact(
                        _digest([result_id, proof.query_id, column.lineage_sha256, index, value]),
                        result_id,
                        column.kind,
                        column.label,
                        sources,
                        value=value,
                        lineage_sha256=column.lineage_sha256,
                    )
                )
    return tuple(facts)
